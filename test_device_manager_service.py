import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import device_manager_service as service
import generador_csv as app


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class ServiceTests(unittest.TestCase):
    def client(self):
        with patch.object(service.ServiceClient, "_identity", return_value={"id": "a" * 64, "jwk": {}}):
            return service.ServiceClient(service.SERVICE_URL)

    def test_https_and_origin_are_required(self):
        for url in ("http://example.test", "https://user:pass@example.test", "https://example.test/path", "https://example.test?token=x"):
            with self.subTest(url=url), self.assertRaises(ValueError): service.ServiceClient(url)

    def test_no_github_credential_loaded_or_saved(self):
        with patch.object(app, "_resource", side_effect=AssertionError("No token resource may be opened")):
            self.assertEqual(app._load_embedded_serial_token(), "")
        settings = {"token": "fixture credential that must not be saved"}
        with tempfile.TemporaryDirectory() as folder, patch.object(app, "_serial_settings_path", return_value=str(Path(folder) / "settings.json")):
            result = app._save_serial_settings(settings)
            self.assertNotIn("token", result)
            self.assertNotIn("token", json.loads((Path(folder) / "settings.json").read_text()))

    def test_revision_survives_normalization(self):
        registry = app._default_serial_registry()
        registry["_service_revision"] = "b" * 40
        self.assertEqual(app._normalize_serial_registry(registry)["_service_revision"], "b" * 40)

    def test_signed_request_has_no_authorization_token(self):
        client = self.client()
        captured = {}
        class Opener:
            def open(self, request, timeout):
                captured["request"] = request
                return Response(b'{"ok":true}')
        with patch.object(client, "_identity", return_value={"id": "a" * 64, "signature": "signature"}), \
                patch.object(service.request, "build_opener", return_value=Opener()):
            self.assertEqual(client.call("GET", "/v1/registry"), {"ok": True})
        self.assertIsNone(captured["request"].get_header("Authorization"))
        self.assertEqual(captured["request"].get_header("X-device-id"), "a" * 64)
        self.assertTrue(captured["request"].get_header("User-agent").startswith("Tecnidro-Device-Manager"))

    def test_pending_device_does_not_fetch_registry(self):
        client = self.client()
        responses = [service.ServiceFailure("device_not_approved"), {"status": "pending"}]
        with patch.object(client, "call", side_effect=responses) as called, self.assertRaises(service.ServiceFailure):
            client.fetch()
        self.assertEqual([call.args for call in called.call_args_list],
                         [("GET", "/v1/registry"), ("POST", "/v1/enroll", {"jwk": {}, "label": service.os.environ.get("COMPUTERNAME", "Device Manager PC")})])
        self.assertFalse(client.approved)

    def test_existing_approval_fetches_without_enrolling(self):
        client = self.client()
        with patch.object(client, "call", return_value={"families": {}}) as called:
            self.assertEqual(client.fetch(), {"families": {}})
        called.assert_called_once_with("GET", "/v1/registry")
        self.assertTrue(client.approved)

    def test_admin_list_confirms_role_without_enrolling(self):
        client = self.client()
        with patch.object(client, "call", return_value={"devices": []}) as called:
            self.assertEqual(client.devices(), [])
        called.assert_called_once_with("GET", "/v1/admin/devices")
        self.assertTrue(client.admin)

    def test_existing_identity_probe_never_requests_creation(self):
        with patch.object(service.ServiceClient, "_identity", return_value={"id": "a" * 64}) as helper:
            service.ServiceClient(existing_only=True)
        helper.assert_called_once_with("identity-existing")

    def test_approval_is_cached_but_requests_remain_signed(self):
        client = self.client()
        with patch.object(client, "call", return_value={"status": "approved", "admin": True}) as called:
            client.enroll()
            client.enroll()
        self.assertEqual(called.call_count, 1)
        self.assertTrue(client.admin)

    def test_redirect_is_never_followed(self):
        self.assertIsNone(service.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))

    def test_missing_revision_prevents_write(self):
        client = self.client()
        with patch.object(client, "call") as called, self.assertRaises(service.ServiceFailure):
            client.save({"families": {}})
        called.assert_not_called()

    def test_error_body_is_not_exposed(self):
        client = self.client()
        class Opener:
            def open(self, *args, **kwargs):
                raise HTTPError(service.SERVICE_URL, 403, "Forbidden", {}, io.BytesIO(b"internal sensitive text"))
        with patch.object(client, "_identity", return_value={"id": "a" * 64, "signature": "signature"}), \
                patch.object(service.request, "build_opener", return_value=Opener()), self.assertRaises(service.ServiceFailure) as result:
            client.call("GET", "/v1/registry")
        self.assertNotIn("internal sensitive text", str(result.exception))

    def test_windows_helper_only_returns_public_material(self):
        client = service.ServiceClient("https://device-manager-tests.invalid")
        signed = client._identity("sign", message="signed fixture")
        self.assertEqual(client.identity["id"], signed["id"])
        self.assertEqual(set(client.identity["jwk"]), {"kty", "n", "e"})
        self.assertEqual(len(signed["signature"]), 342)
