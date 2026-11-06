"""Opt-in offline check used to benchmark the actual packaged interface."""

import json
import os
from pathlib import Path
import tempfile


def run(api):
    marker = Path(os.environ.get("DEVICE_MANAGER_UPDATE_READY_FILE", "")).resolve()
    if (marker.name != "ready.json" or marker.parent.parent != Path(tempfile.gettempdir()).resolve()
            or not marker.parent.name.startswith("device-manager-update-")):
        raise ValueError("A private updater test directory is required for the startup probe.")
    api._load_update_settings = lambda: {"auto_check": False}
    api.App.start_sync = lambda self: None
    root = api.ctk.CTk()
    root.withdraw()
    app = api.App(root)

    def ready():
        api.notify_update_ready()
        result = {"version": api.APP_VERSION, "offline": True}
        try:
            from reportlab.pdfgen.canvas import Canvas
            from device_manager_preview import render_pdf
            with tempfile.TemporaryDirectory(prefix="DeviceManager_probe_") as folder:
                path = Path(folder) / "preview.pdf"
                canvas = Canvas(str(path))
                canvas.drawString(20, 100, "Device Manager packaging check")
                canvas.save()
                image, pages = render_pdf(path, width=320)
                result["pdf_preview"] = pages == 1 and image.width == 320
            result["products"] = len(app.product_buttons)
            result["runtime_dir"] = api._runtime_dir()
        except Exception as exc:
            result["error"] = str(exc)
        (marker.parent / "checks.json").write_text(json.dumps(result), encoding="utf-8")
        app.closed = True
        root.after(100, root.destroy)

    # CTk's first mainloop call performs its own update; finish that setup before closing.
    root.update()
    root.after_idle(ready)
    root.mainloop()
