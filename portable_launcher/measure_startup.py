"""Measure the packaged first-idle signal; --probe is offline and closes itself."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


executable = Path(sys.argv[1]).resolve(strict=True)
folder = Path(tempfile.mkdtemp(prefix="device-manager-update-"))
marker = folder / "ready.json"
environment = dict(os.environ, DEVICE_MANAGER_UPDATE_READY_FILE=str(marker))
probe = "--probe" in sys.argv[2:]
started = time.perf_counter()
process = subprocess.Popen([str(executable)] + (["--startup-probe"] if probe else []),
                           cwd=executable.parent, env=environment)
while time.perf_counter() - started < 90:
    if marker.is_file():
        elapsed = time.perf_counter() - started
        signal = json.loads(marker.read_text(encoding="utf-8"))
        if Path(signal["executable"]).resolve() != executable:
            raise RuntimeError("Unexpected executable in readiness signal")
        result = {"exe": executable.name, "seconds_to_first_idle": round(elapsed, 3), "pid": signal["pid"]}
        if probe:
            if process.wait(timeout=30) != 0:
                raise RuntimeError("Startup probe failed")
            checks = json.loads((folder / "checks.json").read_text(encoding="utf-8"))
            if not checks.get("pdf_preview") or checks.get("products") != 6 or "error" in checks:
                raise RuntimeError("Packaged interface/PDF check failed")
            result["checks"] = checks
            (folder / "checks.json").unlink()
        print(json.dumps(result), flush=True)
        marker.unlink()
        folder.rmdir()
        break
    if process.poll() is not None:
        raise RuntimeError("Application exited before its first-idle signal")
    time.sleep(0.02)
else:
    raise TimeoutError("Application did not confirm readiness in 90 seconds; it was left running")
