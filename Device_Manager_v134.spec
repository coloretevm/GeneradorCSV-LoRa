# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import re
import subprocess
import sys
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

workspace = Path(SPECPATH)
pdf_runtime = workspace / ".build-tools" / "pdf-runtime"
sys.path.append(str(pdf_runtime))
source = workspace / "generador_csv.py"
version = re.search(r'^APP_VERSION = "([^\"]+)"', source.read_text(encoding="utf-8-sig"), re.MULTILINE)
if not version or version.group(1) != "1.134":
    raise SystemExit("The v134 build requires APP_VERSION 1.134.")

identity = workspace / ".build-tools" / "bin" / "DeviceIdentity.exe"
identity.parent.mkdir(parents=True, exist_ok=True)
subprocess.run([r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe", "/nologo", "/target:exe",
                "/platform:x64", "/optimize+", "/reference:System.Security.dll",
                "/reference:System.Web.Extensions.dll", "/out:" + str(identity),
                str(workspace / "serial_service" / "DeviceIdentity.cs")], check=True)

checked_out = (workspace / "fw").is_dir() and (workspace / "Hyperterminal.zip").is_file()
original = workspace if checked_out else Path(r"C:\Users\manuel\Documents\Programa CSV y Etichettas")
logos = workspace if checked_out else Path(r"C:\Users\manuel\Documents\GitHub\GeneradorCSV-LoRa")
datas = [(str(logos / name), ".") for name in ("logo.png", "gw_logo_tecnidro.png", "gw_logo_lorawan.jpeg")]
datas += [(str(original / name), ".") for name in ("Hyperterminal.zip", "APP_BLE_SERIAL__22_06_2026_wx.zip")]
datas += [(str(workspace / "tecnidro_app_icon.png"), "."), (str(identity), ".")]
datas += [(str(workspace / "label_assets"), "label_assets"),
          (str(workspace / "Manuali" / "Fogli adesivi"), "Manuali/Fogli adesivi"),
          (str(workspace / "assets" / "guided"), "assets/guided")]
for package in ("pypdfium2", "pypdfium2_raw", "pypdfium2_cfg"):
    datas += collect_data_files(package)
datas += copy_metadata("pypdfium2")
for path in sorted((original / "fw").rglob("*.hex")):
    if path.is_file() and not path.name.startswith(("CONTATORE_REL.1.0.0", "CONTATORE_REL.1.0.5")):
        datas.append((str(path), str(Path("fw") / path.relative_to(original / "fw").parent)))
manual_root = original / "Manuali"
for folder in ("ITIC", "LoraCont", "Piattaforma Hydronet"):
    for path in sorted((manual_root / folder).glob("*.pdf")):
        datas.append((str(path), "Manuali/" + folder))
if checked_out:
    manual = manual_root / "TIC12" / "Centralina-Controlavaggio-TIC12-Istruzioni-operative-e-connessioni-rev-0.3c-ITA-ENG-tuv-nord.pdf"
    datas.append((str(manual), "Manuali/TIC12"))
else:
    for release in ("v123", "v124", "v128", "v134"):
        for path in sorted((workspace / "release_assets" / release).rglob("*")):
            if path.is_file():
                datas.append((str(path), str(path.relative_to(workspace / "release_assets" / release).parent)))
for path, _ in datas:
    if Path(path).name.casefold() in ("serial_token.txt", "token.txt", "github_token.txt", "serial_registry_settings.json"):
        raise SystemExit("Credential files must not be embedded.")

OPTIONAL_MODULES = ["numpy", "PIL.AvifImagePlugin", "PIL._avif", "PIL.WebPImagePlugin", "PIL._webp"]
a = Analysis([str(source)], pathex=[str(pdf_runtime)], binaries=[], datas=datas,
             hiddenimports=["pypdfium2", "pypdfium2_raw", "pypdfium2_cfg"],
             hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=OPTIONAL_MODULES,
             noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Device_Manager_Core",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          disable_windowed_traceback=False, icon=[str(workspace / "tecnidro_app_icon.ico")])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Device_Manager_Core")
