"""Download validated updates and hand them over after the current app exits."""

import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import time
from urllib import parse, request


def read_manifest(url, user_agent):
    parts = parse.urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("The update manifest must use HTTPS.")
    if parts.hostname == "raw.githubusercontent.com":
        query = parse.parse_qsl(parts.query, keep_blank_values=True)
        query.append(("_dm_check", str(time.time_ns())))
        url = parse.urlunsplit(parts._replace(query=parse.urlencode(query)))
    req = request.Request(url, headers={"User-Agent": user_agent, "Cache-Control": "no-cache"})
    with request.urlopen(req, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Invalid update manifest.")
    version = str(data.get("version", "")).strip().removeprefix("v")
    if not re.fullmatch(r"\d+(?:\.\d+)+", version):
        raise ValueError("Invalid update version.")
    url = str(data.get("url", "")).strip()
    if parse.urlsplit(url).scheme != "https":
        raise ValueError("The update download must use HTTPS.")
    checksum = str(data.get("sha256", "")).strip().lower()
    if checksum and not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("Invalid update checksum.")
    size = int(data.get("size", 0))
    if size < 0:
        raise ValueError("Invalid update size.")
    return {**data, "version": version, "url": url, "sha256": checksum, "size": size}


def update_filename(manifest):
    name = parse.unquote(parse.urlsplit(manifest["url"]).path.rsplit("/", 1)[-1])
    if re.fullmatch(r"Device_Manager_v[0-9_.-]+\.exe", name, re.IGNORECASE):
        return name
    return "Device_Manager_v" + manifest["version"].replace(".", "_") + ".exe"


def file_sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_executable(path):
    with open(path, "rb") as stream:
        header = stream.read(64)
        if len(header) != 64 or header[:2] != b"MZ":
            raise ValueError("The downloaded file is not a Windows executable.")
        offset = struct.unpack_from("<I", header, 60)[0]
        if offset < 64 or offset + 4 > os.path.getsize(path):
            raise ValueError("The executable header is incomplete.")
        stream.seek(offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError("The executable header is invalid.")


def download_update(manifest, target_path, user_agent, progress=None):
    target = Path(target_path).resolve()
    if target.suffix.lower() != ".exe":
        raise ValueError("The update filename must end in .exe.")
    if target == Path(sys.executable).resolve():
        raise ValueError("Cannot overwrite the running application.")
    descriptor, temporary = tempfile.mkstemp(prefix=".device-manager-", suffix=".download", dir=target.parent)
    try:
        req = request.Request(manifest["url"], headers={"User-Agent": user_agent})
        checksum = hashlib.sha256()
        received = 0
        with os.fdopen(descriptor, "wb") as output:
            with request.urlopen(req, timeout=60) as response:
                length = int(response.headers.get("Content-Length", 0))
                total = manifest.get("size", 0) or length
                last_percent = -1
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    checksum.update(chunk)
                    received += len(chunk)
                    percent = min(100, received * 100 // total) if total else 0
                    if progress and percent != last_percent:
                        progress(percent)
                        last_percent = percent
        if not received or (length and received != length):
            raise ValueError("The update download is incomplete.")
        if manifest.get("size") and received != manifest["size"]:
            raise ValueError("The update size does not match the manifest.")
        digest = checksum.hexdigest()
        if manifest.get("sha256") and digest != manifest["sha256"]:
            raise ValueError("The update checksum does not match the manifest.")
        _validate_executable(temporary)
        os.replace(temporary, target)
        return digest
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


WINDOWS_HANDOFF_SCRIPT = r'''
param([Parameter(Mandatory=$true)][string]$PlanPath)
$ErrorActionPreference = 'Stop'
$plan = Get-Content -LiteralPath $PlanPath -Raw -Encoding UTF8 | ConvertFrom-Json
$completed = $false
try {
    $oldProcess = Get-Process -Id $plan.old_pid -ErrorAction SilentlyContinue
    if ($oldProcess) { Wait-Process -Id $plan.old_pid -Timeout 120 -ErrorAction Stop }
    $oldPath = [IO.Path]::GetFullPath($plan.old_exe)
    $newPath = (Resolve-Path -LiteralPath $plan.new_exe).ProviderPath
    if ([string]::Equals($oldPath, $newPath, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($oldPath) -ine '.exe' -or
        [IO.Path]::GetExtension($newPath) -ine '.exe') {
        throw 'Invalid update paths.'
    }
    if ((Get-FileHash -LiteralPath $newPath -Algorithm SHA256).Hash -ine $plan.new_sha256) {
        throw 'The downloaded executable has changed.'
    }
    $env:DEVICE_MANAGER_UPDATE_READY_FILE = $plan.ready_file
    try {
        $newProcess = Start-Process -FilePath $newPath -WorkingDirectory ([IO.Path]::GetDirectoryName($newPath)) -PassThru
    } finally {
        Remove-Item Env:\DEVICE_MANAGER_UPDATE_READY_FILE -ErrorAction SilentlyContinue
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $plan.ready_file) {
            $signal = Get-Content -LiteralPath $plan.ready_file -Raw -Encoding UTF8 | ConvertFrom-Json
            $readyProcess = Get-Process -Id $signal.pid -ErrorAction SilentlyContinue
            if ($readyProcess -and
                [string]::Equals([IO.Path]::GetFullPath($signal.executable), $newPath, [StringComparison]::OrdinalIgnoreCase) -and
                [string]::Equals($readyProcess.Path, $newPath, [StringComparison]::OrdinalIgnoreCase)) {
                Start-Sleep -Seconds 2
                if (Get-Process -Id $signal.pid -ErrorAction SilentlyContinue) { $ready = $true; break }
            }
        }
        $newProcess.Refresh()
        if ($newProcess.HasExited) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'The new application did not confirm a successful start.' }
    if (Test-Path -LiteralPath $oldPath) {
        $resolvedOldPath = (Resolve-Path -LiteralPath $oldPath).ProviderPath
        if (-not [string]::Equals($resolvedOldPath, $oldPath, [StringComparison]::OrdinalIgnoreCase) -or
            (Get-FileHash -LiteralPath $oldPath -Algorithm SHA256).Hash -ine $plan.old_sha256) {
            throw 'The previous executable has changed; it was kept.'
        }
        $removed = $false
        for ($attempt = 0; $attempt -lt 80; $attempt++) {
            try {
                Remove-Item -LiteralPath $oldPath -Force -ErrorAction Stop
                $removed = $true
                break
            } catch { Start-Sleep -Milliseconds 250 }
        }
        if (-not $removed) { throw 'The previous executable could not be removed.' }
    }
    $completed = $true
} catch {
    $_.Exception.Message | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'error.log') -Encoding UTF8
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show($plan.error_message, 'Device Manager') | Out-Null
} finally {
    if ($completed) {
        foreach ($filename in @('ready.json', 'plan.json', 'apply_update.ps1')) {
            $cleanupPath = Join-Path $PSScriptRoot $filename
            Remove-Item -LiteralPath $cleanupPath -Force -ErrorAction SilentlyContinue
        }
    }
}
'''


def launch_windows_handoff(downloaded_exe, digest, error_message):
    if os.name != "nt" or not getattr(sys, "frozen", False):
        raise OSError("Automatic installation requires the Windows executable.")
    old = Path(sys.executable).resolve()
    new = Path(downloaded_exe).resolve()
    if old == new or old.suffix.lower() != ".exe" or new.suffix.lower() != ".exe":
        raise ValueError("Invalid update paths.")
    if file_sha256(new) != digest:
        raise ValueError("The downloaded executable has changed.")
    folder = Path(tempfile.mkdtemp(prefix="device-manager-update-"))
    script = folder / "apply_update.ps1"
    plan = folder / "plan.json"
    script.write_text(WINDOWS_HANDOFF_SCRIPT, encoding="utf-8-sig")
    plan.write_text(json.dumps({
        "old_exe": str(old), "new_exe": str(new), "old_pid": os.getpid(),
        "old_sha256": file_sha256(old), "new_sha256": digest,
        "ready_file": str(folder / "ready.json"), "error_message": error_message,
    }), encoding="utf-8")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    return subprocess.Popen(
        [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-File", str(script), "-PlanPath", str(plan)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def notify_update_ready():
    marker = os.environ.pop("DEVICE_MANAGER_UPDATE_READY_FILE", "")
    if not marker:
        return
    path = Path(marker).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (path.name != "ready.json" or path.parent.parent != temp_root
            or not path.parent.name.startswith("device-manager-update-")):
        return
    try:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"pid": os.getpid(), "executable": sys.executable}), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        pass
