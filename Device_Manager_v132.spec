# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import re
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

workspace = Path(SPECPATH)
pdf_runtime = workspace / ".build-tools" / "pdf-runtime"
sys.path.append(str(pdf_runtime))
source = workspace / "generador_csv.py"
version = re.search(r'^APP_VERSION = "([^\"]+)"', source.read_text(encoding="utf-8-sig"), re.MULTILINE)
if not version or version.group(1) != "1.132":
    raise SystemExit("The v132 build requires APP_VERSION 1.132.")

original = Path(r"C:\Users\manuel\Documents\Programa CSV y Etichettas")
logos = Path(r"C:\Users\manuel\Documents\GitHub\GeneradorCSV-LoRa")
datas = [(str(logos / name), ".") for name in ("logo.png", "gw_logo_tecnidro.png", "gw_logo_lorawan.jpeg")]
datas += [(str(original / name), ".") for name in ("Hyperterminal.zip", "APP_BLE_SERIAL__22_06_2026_wx.zip")]
datas += [(str(workspace / name), ".") for name in ("serial_token.txt", "tecnidro_app_icon.png")]
datas += [(str(workspace / "label_assets"), "label_assets"),
          (str(workspace / "Manuali" / "Fogli adesivi"), "Manuali/Fogli adesivi"),
          (str(workspace / "assets" / "guided"), "assets/guided")]
for package in ("pypdfium2", "pypdfium2_raw", "pypdfium2_cfg"):
    datas += collect_data_files(package)
datas += copy_metadata("pypdfium2")
for path in sorted((original / "fw").rglob("*")):
    if path.is_file() and not path.name.startswith("CONTATORE_REL.1.0.5"):
        datas.append((str(path), str(Path("fw") / path.relative_to(original / "fw").parent)))
for path in sorted((original / "Manuali").rglob("*")):
    if path.is_file() and path.relative_to(original / "Manuali").parts[0].casefold() not in ("tic12", "fogli adesivi"):
        datas.append((str(path), str(Path("Manuali") / path.relative_to(original / "Manuali").parent)))
for release in ("v123", "v124", "v128"):
    for path in sorted((workspace / "release_assets" / release).rglob("*")):
        if path.is_file():
            datas.append((str(path), str(path.relative_to(workspace / "release_assets" / release).parent)))

OPTIONAL_MODULES = ["numpy", "PIL.AvifImagePlugin", "PIL._avif", "PIL.WebPImagePlugin", "PIL._webp"]
a = Analysis([str(source)], pathex=[str(pdf_runtime)], binaries=[], datas=datas,
             hiddenimports=["pypdfium2", "pypdfium2_raw", "pypdfium2_cfg"],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=OPTIONAL_MODULES,
             noarchive=False, optimize=0)
pyz = PYZ(a.pure)
# This directory is build input only; build_portable.py embeds it in the one user-facing EXE.
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name="Device_Manager_Core", debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False,
          icon=[str(workspace / "tecnidro_app_icon.ico")])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Device_Manager_Core")
