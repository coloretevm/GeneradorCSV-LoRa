"""The updater must replace the visible EXE, not the cached application core."""

import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import device_manager_runtime as runtime
import device_manager_updater as updater


class PortableRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="DeviceManager_runtime_")
        self.addCleanup(self.folder.cleanup)
        self.outer = Path(self.folder.name) / "Device_Manager_v132.exe"
        self.core = Path(self.folder.name) / "cache/Device_Manager_Core.exe"
        self.outer.write_bytes(b"fixture outer")
        self.core.parent.mkdir()
        self.core.write_bytes(b"fixture core")
        runtime._verified_launcher.cache_clear()

    def context(self):
        return patch.dict(os.environ, {"DEVICE_MANAGER_PORTABLE_EXE": str(self.outer),
                                       "DEVICE_MANAGER_PORTABLE_PID": "123"})

    def test_source_ignores_portable_environment(self):
        with self.context(), patch.object(runtime.sys, "frozen", False, create=True):
            self.assertEqual(runtime.application_executable(), Path(runtime.sys.executable).resolve())

    @unittest.skipUnless(os.name == "nt", "Windows portable process verification")
    def test_verified_parent_is_the_visible_executable(self):
        with self.context(), patch.object(runtime.sys, "frozen", True, create=True), \
                patch.object(runtime.sys, "executable", str(self.core)), \
                patch.object(runtime, "_parent_image", return_value=(123, self.outer)):
            self.assertEqual(runtime.application_context(), (self.outer, 123))

    @unittest.skipUnless(os.name == "nt", "Windows portable process verification")
    def test_forged_parent_context_is_rejected(self):
        for parent, image in ((124, self.outer), (123, self.core)):
            with self.subTest(parent=parent, image=image), self.context(), \
                    patch.object(runtime.sys, "frozen", True, create=True), \
                    patch.object(runtime, "_parent_image", return_value=(parent, image)), self.assertRaises(OSError):
                runtime.application_context()

    def test_download_cannot_overwrite_visible_launcher(self):
        with patch.object(updater, "application_executable", return_value=self.outer), self.assertRaises(ValueError):
            updater.download_update({}, self.outer, "test")

    def test_update_plan_targets_original_exe_and_parent_pid(self):
        target = Path(self.folder.name) / "Device_Manager_v133.exe"
        target.write_bytes(b"fixture next version")
        digest = updater.file_sha256(target)
        plan_dir = Path(self.folder.name) / "handoff"
        plan_dir.mkdir()
        with patch.object(updater, "application_context", return_value=(self.outer, 123)), \
                patch.object(updater.sys, "frozen", True, create=True), \
                patch.object(updater.tempfile, "mkdtemp", return_value=str(plan_dir)), \
                patch.object(updater.subprocess, "Popen") as spawned:
            updater.launch_windows_handoff(target, digest, "test failure")
        plan = json.loads((plan_dir / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["old_exe"], str(self.outer))
        self.assertEqual(plan["old_pid"], 123)
        self.assertEqual(plan["old_sha256"], updater.file_sha256(self.outer))
        self.assertTrue(self.core.exists())
        spawned.assert_called_once()

    def test_readiness_signal_identifies_visible_parent(self):
        with tempfile.TemporaryDirectory(prefix="device-manager-update-") as folder:
            marker = Path(folder) / "ready.json"
            with patch.dict(os.environ, {"DEVICE_MANAGER_UPDATE_READY_FILE": str(marker)}), \
                    patch.object(updater, "application_context", return_value=(self.outer, 123)):
                updater.notify_update_ready()
            self.assertEqual(json.loads(marker.read_text()), {"pid": 123, "executable": str(self.outer)})

    def test_startup_probe_closes_after_tk_initialization(self):
        with tempfile.TemporaryDirectory(prefix="device-manager-update-") as folder:
            marker = Path(folder) / "ready.json"
            environment = dict(os.environ, DEVICE_MANAGER_UPDATE_READY_FILE=str(marker),
                               TMP=str(marker.parent.parent), TEMP=str(marker.parent.parent),
                               PYTHONPATH=os.pathsep.join(path for path in sys.path if path))
            command = "import sys; import generador_csv as app; sys.argv=['generador_csv.py','--startup-probe']; app.main()"
            result = subprocess.run([sys.executable, "-c", command], cwd=Path(__file__).resolve().parent,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(marker.exists())
            self.assertTrue(json.loads((Path(folder) / "checks.json").read_text())["pdf_preview"])
