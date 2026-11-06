"""Create the single portable EXE from a tested PyInstaller directory build."""

import hashlib
from pathlib import Path
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def build(core, output):
    core = Path(core).resolve(strict=True)
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    intermediate = ROOT / "build/portable_v132"
    intermediate.mkdir(parents=True, exist_ok=True)
    payload = intermediate / "payload.zip"
    manifest = intermediate / "cache.manifest"
    lines = []
    names = set()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(core.rglob("*")):
            if not path.is_file():
                continue
            if path.is_symlink():
                raise ValueError("Symbolic links are not supported in the portable payload")
            relative = path.relative_to(core).as_posix()
            if relative.casefold() in names or "\t" in relative or "\n" in relative:
                raise ValueError("Unsafe or duplicate portable resource name")
            names.add(relative.casefold())
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            lines.append(f"{digest}\t{path.stat().st_size}\t{relative}\n")
            archive.write(path, relative)
    manifest.write_text("".join(lines), encoding="utf-8", newline="\n")
    compiler = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
    subprocess.run([
        str(compiler), "/nologo", "/target:winexe", "/platform:x64", "/optimize+",
        "/reference:System.IO.Compression.dll", "/reference:System.Windows.Forms.dll",
        "/win32icon:" + str(ROOT / "tecnidro_app_icon.ico"),
        "/win32manifest:" + str(ROOT / "portable_launcher/app.manifest"),
        "/resource:" + str(payload) + ",DM.Payload",
        "/resource:" + str(manifest) + ",DM.Manifest",
        "/out:" + str(output), str(ROOT / "portable_launcher/Launcher.cs"),
    ], check=True)
    print(f"Portable executable created: {output.name}; {len(lines)} verified resources; {output.stat().st_size} bytes")


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
