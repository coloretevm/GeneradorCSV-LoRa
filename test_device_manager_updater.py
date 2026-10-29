import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import device_manager_updater as updater


class Response(io.BytesIO):
    def __init__(self, body, length=None):
        super().__init__(body)
        self.headers = {"Content-Length": str(len(body) if length is None else length)}


def executable_bytes():
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    return bytes(data)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name) / "Device_Manager_v126.exe"
        self.data = executable_bytes()
        self.manifest = {
            "version": "1.126", "url": "https://example.test/Device_Manager_v126.exe",
            "sha256": hashlib.sha256(self.data).hexdigest(), "size": len(self.data),
        }

    def test_bom_manifest_and_no_cache(self):
        body = b"\xef\xbb\xbf" + json.dumps(self.manifest).encode()
        with patch.object(updater.request, "urlopen", return_value=Response(body)) as opened:
            manifest = updater.read_manifest("https://example.test/manifest.json", "test")
        self.assertEqual(manifest["version"], "1.126")
        self.assertEqual(opened.call_args.args[0].get_header("Cache-control"), "no-cache")

    def test_invalid_manifest_rejected(self):
        for data in ([], {**self.manifest, "version": "oops"},
                     {**self.manifest, "url": "http://example.test/app.exe"},
                     {**self.manifest, "sha256": "wrong"}):
            with self.subTest(data=data), patch.object(
                updater.request, "urlopen", return_value=Response(json.dumps(data).encode())
            ), self.assertRaises((ValueError, TypeError)):
                updater.read_manifest("https://example.test/manifest.json", "test")

    def test_github_checks_bypass_stale_cdn_manifest(self):
        body = json.dumps(self.manifest).encode()
        with patch.object(updater.request, "urlopen", return_value=Response(body)) as opened:
            updater.read_manifest("https://raw.githubusercontent.com/owner/repo/main/update_manifest.json", "test")
        self.assertIn("?_dm_check=", opened.call_args.args[0].full_url)

    def test_atomic_download_and_progress(self):
        self.target.write_bytes(b"previous download")
        progress = []
        with patch.object(updater.request, "urlopen", return_value=Response(self.data)):
            digest = updater.download_update(self.manifest, self.target, "test", progress.append)
        self.assertEqual(self.target.read_bytes(), self.data)
        self.assertEqual(digest, self.manifest["sha256"])
        self.assertEqual(progress[-1], 100)
        self.assertEqual(list(Path(self.folder.name).glob("*.download")), [])

    def test_failed_download_preserves_existing_target(self):
        for body, length, checksum in (
            (self.data[:-10], len(self.data), self.manifest["sha256"]),
            (self.data, len(self.data), "0" * 64),
            (b"<html>Download error</html>", 27, ""),
        ):
            with self.subTest(body=body[:10]):
                self.target.write_bytes(b"existing executable")
                manifest = {**self.manifest, "sha256": checksum, "size": 0}
                with patch.object(updater.request, "urlopen", return_value=Response(body, length)), self.assertRaises(ValueError):
                    updater.download_update(manifest, self.target, "test")
                self.assertEqual(self.target.read_bytes(), b"existing executable")
                self.assertEqual(list(Path(self.folder.name).glob("*.download")), [])

    def test_running_executable_cannot_be_overwritten(self):
        with patch.object(updater.sys, "executable", str(self.target)), self.assertRaises(ValueError):
            updater.download_update(self.manifest, self.target, "test")

    def test_filename_cannot_escape_download_folder(self):
        manifest = {**self.manifest, "url": "https://example.test/%2e%2e%2fsecret.exe"}
        name = updater.update_filename(manifest)
        self.assertEqual(Path(name).name, name)
        self.assertTrue(name.startswith("Device_Manager_v"))

    def test_ready_marker_only_written_to_updater_directory(self):
        marker = Path(self.folder.name) / "unrelated.json"
        with patch.dict(updater.os.environ, {"DEVICE_MANAGER_UPDATE_READY_FILE": str(marker)}):
            updater.notify_update_ready()
        self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
