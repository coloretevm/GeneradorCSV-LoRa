"""Signed requests to the private serial service. No GitHub credential on the PC."""

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
from urllib import error, parse, request


SERVICE_URL = "https://tecnidro-serial-service.tecnidro-device-manager.workers.dev"


class ServiceFailure(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

    def __str__(self):
        application = sys.modules.get("generador_csv") or sys.modules.get("__main__")
        language = getattr(application, "_cur_lang", ["it"])[0]
        return error_message(self.code, language)


def error_message(code, language="it"):
    messages = {
        "device_pending_approval": ("Questo PC e in attesa di autorizzazione dall'amministratore.",
                                    "Este PC espera la autorizacion del administrador.", "This PC is waiting for administrator approval."),
        "device_not_approved": ("Questo PC non e autorizzato.", "Este PC no esta autorizado.", "This PC is not approved."),
        "device_revoked": ("L'autorizzazione di questo PC e stata revocata.", "La autorizacion de este PC fue revocada.", "This PC's approval was revoked."),
        "administrator_required": ("Solo il PC amministratore puo autorizzare altri computer.",
                                   "Solo el PC administrador puede autorizar otros equipos.", "Only the administrator PC can approve other computers."),
        "registry_changed": ("Registro modificato da un altro PC. Sincronizza e riprova.",
                             "Otro PC modifico el registro. Sincroniza y vuelve a intentarlo.", "Another PC changed the registry. Synchronize and retry."),
        "clock_out_of_sync": ("Controlla data e ora di Windows.", "Comprueba la fecha y hora de Windows.", "Check the Windows date and time."),
        "github_credentials_rejected": ("L'amministratore deve aggiornare la credenziale GitHub nel servizio.",
                                        "El administrador debe actualizar la credencial GitHub del servicio.", "The administrator must update the service's GitHub credential."),
    }
    fallback = ("Servizio seriali non disponibile. Riprova. (" + code + ")",
                "Servicio de seriales no disponible. Vuelve a intentarlo. (" + code + ")",
                "Serial service unavailable. Please retry. (" + code + ")")
    return messages.get(code, fallback)[{"it": 0, "es": 1, "en": 2}.get(language, 0)]


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class ServiceClient:
    def __init__(self, origin=SERVICE_URL, helper=None, *, existing_only=False):
        parts = parse.urlsplit(origin)
        if (parts.scheme != "https" or not parts.hostname or parts.path not in ("", "/")
                or parts.username or parts.password or parts.query or parts.fragment):
            raise ValueError("Invalid private service URL")
        self.origin = origin.rstrip("/")
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self.helper = (Path(helper) if helper else root / ("DeviceIdentity.exe" if getattr(sys, "frozen", False)
                                                         else ".build-tools/bin/DeviceIdentity.exe")).resolve()
        self.local_appdata = os.environ.get("LOCALAPPDATA")
        self.identity = self._identity("identity-existing" if existing_only else "identity")
        self.admin = False
        self.approved = False

    def _identity(self, operation, **kwargs):
        payload = {"origin": self.origin, "operation": operation, **kwargs}
        if self.local_appdata:
            payload["local_appdata"] = self.local_appdata
        process = subprocess.run([str(self.helper)], input=json.dumps(payload),
                                 cwd=self.helper.parent, text=True, capture_output=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=40)
        if process.returncode != 0:
            raise ServiceFailure("device_identity_unavailable")
        return json.loads(process.stdout)

    def call(self, method, path, data=None):
        if not path.startswith("/v1/") or "?" in path or "#" in path:
            raise ValueError("Invalid service path")
        body = b"" if data is None else json.dumps(data, ensure_ascii=True, sort_keys=True,
                                                 separators=(",", ":")).encode("utf-8")
        timestamp, nonce = str(int(time.time())), secrets.token_hex(16)
        message = "\n".join((self.origin, method, path, timestamp, nonce, hashlib.sha256(body).hexdigest()))
        signed = self._identity("sign", message=message)
        if signed["id"] != self.identity["id"]:
            raise ServiceFailure("device_identity_changed")
        headers = {"Content-Type": "application/json", "User-Agent": "Tecnidro-Device-Manager/1.135",
                   "X-Device-ID": self.identity["id"],
                   "X-Device-Time": timestamp, "X-Device-Nonce": nonce, "X-Device-Signature": signed["signature"]}
        req = request.Request(self.origin + path, data=body if data is not None else None,
                              headers=headers, method=method)
        try:
            with request.build_opener(NoRedirect).open(req, timeout=25) as response:
                return json.loads(response.read(131072).decode("utf-8"))
        except error.HTTPError as exc:
            try: code = json.loads(exc.read(4096).decode("utf-8"))["error"]
            except (ValueError, KeyError): code = "service_unavailable"
            raise ServiceFailure(code) from None

    def enroll(self):
        if self.approved:
            return
        result = self.call("POST", "/v1/enroll", {"jwk": self.identity["jwk"],
                           "label": os.environ.get("COMPUTERNAME", "Device Manager PC")})
        self.admin = bool(result.get("admin"))
        if result.get("status") != "approved":
            raise ServiceFailure("device_pending_approval")
        self.approved = True

    def fetch(self):
        if not self.approved:
            try:
                registry = self.call("GET", "/v1/registry")
            except ServiceFailure as exc:
                if exc.code != "device_not_approved":
                    raise
                self.enroll()
            else:
                self.approved = True
                return registry
        return self.call("GET", "/v1/registry")

    def save(self, registry):
        revision = registry.get("_service_revision", "")
        if not revision:
            raise ServiceFailure("registry_changed")
        body = {"revision": revision, "registry": registry, "operation_id": str(uuid.uuid4())}
        for attempt in range(2):
            try: return self.call("PUT", "/v1/registry", body)
            except error.URLError:
                if attempt: raise

    def devices(self):
        devices = self.call("GET", "/v1/admin/devices")["devices"]
        self.admin = self.approved = True
        return devices

    def approve(self, device_id):
        return self.call("POST", "/v1/admin/devices", {"id": device_id, "status": "approved"})
