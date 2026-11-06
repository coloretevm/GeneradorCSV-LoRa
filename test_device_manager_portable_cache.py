"""Exercise the production Windows launcher against harmless embedded fixtures."""

import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parent
COMPILER = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


@unittest.skipUnless(os.name == "nt" and COMPILER.exists(), "Windows .NET compiler is required")
class PortableCacheTests(unittest.TestCase):
    def test_production_launcher_cache_lifecycle(self):
        with tempfile.TemporaryDirectory(prefix="DeviceManager_cache_tests_") as folder:
            folder = Path(folder)
            fixture = folder / "fixture.exe"
            payload = folder / "payload.zip"
            manifest = folder / "cache.manifest"
            files = {"Device_Manager_Core.exe": b"harmless test fixture, never executed",
                     "_internal/sample.txt": b"original fixture"}
            with zipfile.ZipFile(payload, "w") as archive:
                for name, data in files.items():
                    archive.writestr(name, data)
            manifest.write_text("".join(f"{hashlib.sha256(data).hexdigest()}\t{len(data)}\t{name}\n"
                                        for name, data in files.items()), encoding="utf-8")
            compiled = subprocess.run([
                str(COMPILER), "/nologo", "/target:winexe", "/reference:System.IO.Compression.dll",
                "/reference:System.Windows.Forms.dll", "/resource:" + str(payload) + ",DM.Payload",
                "/resource:" + str(manifest) + ",DM.Manifest", "/out:" + str(fixture),
                str(ROOT / "portable_launcher/Launcher.cs"),
            ], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            harness = folder / "cache_tests.exe"
            compiled = subprocess.run([str(COMPILER), "/nologo", "/target:exe", "/out:" + str(harness),
                                       str(ROOT / "portable_launcher/CacheTests.cs")], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(harness), str(fixture), str(folder / "cache")],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS:", result.stdout)
