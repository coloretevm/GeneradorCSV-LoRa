import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import customtkinter as ctk
import base64
import csv
import json
import copy
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from urllib import error as urlerror
from urllib import request as urlrequest
from PIL import Image

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_VERSION = "1.114"
APP_BUILD_NAME = "Device_Manager_v114"
SERIAL_ADMIN_PASSWORD = "Tecnidro2024!"
UPDATE_SETTINGS_FILE = "update_settings.json"
SERIAL_SETTINGS_FILE = "serial_registry_settings.json"
DEFAULT_UPDATE_SETTINGS = {
    "manifest_url": "https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/update_manifest.json",
    "auto_check": True,
}
DEFAULT_SERIAL_SETTINGS = {
    "registry_url": "https://raw.githubusercontent.com/coloretevm/GeneradorCSV-LoRa/main/serial_registry.json",
    "api_url": "https://api.github.com/repos/coloretevm/GeneradorCSV-LoRa/contents/serial_registry.json",
    "branch": "main",
    "token": "",
    "station_name": os.environ.get("COMPUTERNAME", "PC"),
}
SERIAL_FAMILY_ORDER = ("RTU", "GW", "I-TIC", "TIC12")
SERIAL_FAMILY_SETTINGS = {
    "RTU": {"entry_key": "serial_family_rtu", "number_width": 5},
    "GW": {"entry_key": "serial_family_gw", "number_width": 1},
    "I-TIC": {"entry_key": "serial_family_itic", "number_width": 4},
    "TIC12": {"entry_key": "serial_family_tic12", "number_width": 4},
}
_serial_registry_cache = None
_serial_refresh_callbacks = []

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _resource(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _desktop_dir():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    return desktop if os.path.isdir(desktop) else os.path.expanduser("~")


def _safe_filename(text):
    cleaned = str(text or "").strip()
    for ch in '<>:"/\\|?*':
        cleaned = cleaned.replace(ch, "-")
    return " ".join(cleaned.split()) or "output"


def _default_label_pdf_path(label_name, start_value, end_value):
    filename = f"Etichette {_safe_filename(label_name)} {_safe_filename(start_value)}-{_safe_filename(end_value)}.pdf"
    return os.path.join(_desktop_dir(), filename)


def _register_serial_refresh_callback(callback):
    if callback and callback not in _serial_refresh_callbacks:
        _serial_refresh_callbacks.append(callback)


def _notify_serial_registry_changed():
    for callback in list(_serial_refresh_callbacks):
        try:
            callback()
        except Exception:
            continue


def _load_embedded_serial_token():
    for path in (
        _resource("serial_token.txt"),
        os.path.join(_runtime_dir(), "serial_token.txt"),
    ):
        try:
            if os.path.isfile(path):
                with open(path, "r", encoding="utf-8") as fh:
                    return fh.read().strip()
        except Exception:
            continue
    return ""


def _update_settings_path():
    return os.path.join(_runtime_dir(), UPDATE_SETTINGS_FILE)


def _serial_settings_path():
    return os.path.join(_runtime_dir(), SERIAL_SETTINGS_FILE)


def _load_update_settings():
    settings = dict(DEFAULT_UPDATE_SETTINGS)
    path = _update_settings_path()
    if not os.path.isfile(path):
        try:
            _save_update_settings(settings)
        except Exception:
            pass
        return settings
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            settings.update(data)
        if not str(settings.get("manifest_url", "")).strip():
            settings["manifest_url"] = DEFAULT_UPDATE_SETTINGS["manifest_url"]
    except Exception:
        pass
    return settings


def _save_update_settings(settings):
    path = _update_settings_path()
    merged = dict(DEFAULT_UPDATE_SETTINGS)
    merged.update(settings or {})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)


def _load_serial_settings():
    settings = dict(DEFAULT_SERIAL_SETTINGS)
    settings["station_name"] = os.environ.get("COMPUTERNAME", settings["station_name"])
    settings["token"] = (
        os.environ.get("DEVICE_MANAGER_GITHUB_TOKEN", "").strip()
        or _load_embedded_serial_token()
        or str(settings.get("token", "")).strip()
    )
    return settings


def _save_serial_settings(settings):
    merged = dict(DEFAULT_SERIAL_SETTINGS)
    merged.update(settings or {})
    return merged


def _default_serial_registry():
    families = {}
    for family in SERIAL_FAMILY_ORDER:
        families[family] = {
            "last_serial": 0,
            "updated_at": "",
            "updated_by": "",
            "last_count": 0,
            "last_range": "",
            "last_year": "",
        }
    return {
        "version": 1,
        "updated_at": "",
        "families": families,
    }


def _normalize_serial_registry(data):
    registry = _default_serial_registry()
    if not isinstance(data, dict):
        return registry
    families = data.get("families", {})
    registry["updated_at"] = str(data.get("updated_at", "") or "")
    for family in SERIAL_FAMILY_ORDER:
        entry = {}
        if isinstance(families, dict):
            raw_entry = families.get(family, {})
            if isinstance(raw_entry, dict):
                entry = raw_entry
        registry["families"][family].update({
            "last_serial": int(entry.get("last_serial", registry["families"][family]["last_serial"]) or 0),
            "updated_at": str(entry.get("updated_at", "") or ""),
            "updated_by": str(entry.get("updated_by", "") or ""),
            "last_count": int(entry.get("last_count", 0) or 0),
            "last_range": str(entry.get("last_range", "") or ""),
            "last_year": str(entry.get("last_year", "") or ""),
        })
    return registry


def _git_run(repo_path, *args):
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.run(
        ["git", "-C", repo_path, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(detail or "Git command failed.")
    return proc.stdout.strip()


def _serial_registry_full_path(settings):
    repo_path = str(settings.get("repo_path", "")).strip()
    rel_path = str(settings.get("registry_file", "serial_registry.json")).strip() or "serial_registry.json"
    if not repo_path:
        raise ValueError(t("serial_repo_error_missing_path"))
    if not os.path.isdir(repo_path):
        raise ValueError(t("serial_repo_error_missing_repo").format(path=repo_path))
    return repo_path, rel_path, os.path.join(repo_path, rel_path)


def _serial_registry_read_local(registry_path):
    if not os.path.isfile(registry_path):
        return _default_serial_registry()
    with open(registry_path, "r", encoding="utf-8") as fh:
        return _normalize_serial_registry(json.load(fh))


def _serial_registry_write_local(registry_path, registry):
    folder = os.path.dirname(registry_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as fh:
        json.dump(_normalize_serial_registry(registry), fh, indent=2, ensure_ascii=False)


def _serial_registry_pull(settings):
    api_url = str(settings.get("api_url", "")).strip()
    branch = str(settings.get("branch", "main")).strip() or "main"
    token = str(settings.get("token", "")).strip() or os.environ.get("DEVICE_MANAGER_GITHUB_TOKEN", "").strip()
    if api_url.lower().startswith(("http://", "https://")):
        headers = _github_api_headers(token)
        payload = _request_json(f"{api_url}?ref={branch}", headers=headers)
        if isinstance(payload, dict) and payload.get("content"):
            content = str(payload.get("content", "")).replace("\n", "")
            decoded = base64.b64decode(content).decode("utf-8")
            return _set_serial_registry_cache(json.loads(decoded))
    registry_url = str(settings.get("registry_url", "")).strip()
    if registry_url.lower().startswith(("http://", "https://")):
        return _set_serial_registry_cache(_download_json(registry_url))

    repo_path, _, registry_path = _serial_registry_full_path(settings)
    _git_run(repo_path, "pull", "--rebase", "origin", branch)
    return _set_serial_registry_cache(_serial_registry_read_local(registry_path))


def _serial_registry_push(settings, registry, message):
    registry = _normalize_serial_registry(registry)
    registry["updated_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    api_url = str(settings.get("api_url", "")).strip()
    branch = str(settings.get("branch", "main")).strip() or "main"
    token = str(settings.get("token", "")).strip() or os.environ.get("DEVICE_MANAGER_GITHUB_TOKEN", "").strip()

    if api_url.lower().startswith(("http://", "https://")):
        if not token:
            raise ValueError(t("serial_repo_error_missing_token"))

        content_bytes = json.dumps(registry, indent=2, ensure_ascii=False).encode("utf-8")
        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        try:
            current = _request_json(
                f"{api_url}?ref={branch}",
                headers=_github_api_headers(token),
            )
            if isinstance(current, dict) and current.get("sha"):
                payload["sha"] = current["sha"]
        except urlerror.HTTPError as exc:
            if exc.code != 404:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(detail or str(exc))

        _request_json(
            api_url,
            headers={
                **_github_api_headers(token),
                "Content-Type": "application/json",
            },
            data=json.dumps(payload).encode("utf-8"),
            method="PUT",
        )
        return _set_serial_registry_cache(registry)

    repo_path, rel_path, registry_path = _serial_registry_full_path(settings)
    _serial_registry_write_local(registry_path, registry)
    _git_run(repo_path, "add", rel_path)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    commit = subprocess.run(
        ["git", "-C", repo_path, "commit", "-m", message],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creation_flags,
    )
    if commit.returncode != 0:
        detail = (commit.stderr or commit.stdout or "").strip().lower()
        if "nothing to commit" not in detail and "nothing added to commit" not in detail:
            raise RuntimeError((commit.stderr or commit.stdout or "").strip() or "Git commit failed.")
    _git_run(repo_path, "push", "origin", branch)
    return _set_serial_registry_cache(registry)


def _serial_registry_fetch(settings):
    return _serial_registry_pull(settings)


def _serial_registry_update_last(settings, family, start, end, year, count):
    if family not in SERIAL_FAMILY_ORDER:
        raise ValueError(f"Unknown family: {family}")
    registry = _serial_registry_pull(settings)
    entry = registry["families"][family]
    current_last = int(entry.get("last_serial", 0) or 0)
    if start <= current_last:
        raise ValueError(
            t("serial_repo_error_overlap").format(
                family=family,
                current=current_last,
                requested=start,
            )
        )
    station = str(settings.get("station_name", "")).strip() or DEFAULT_SERIAL_SETTINGS["station_name"]
    width = SERIAL_FAMILY_SETTINGS[family]["number_width"]
    entry.update({
        "last_serial": int(end),
        "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "updated_by": station,
        "last_count": int(count),
        "last_range": f"{start:0{width}d}-{end:0{width}d}",
        "last_year": str(year),
    })
    registry["families"][family] = entry
    return _serial_registry_push(
        settings,
        registry,
        f"Update serial registry: {family} {entry['last_range']}/{year}",
    )


def _serial_registry_update_gateways(settings, serial_values, year):
    if "GW" not in SERIAL_FAMILY_ORDER:
        raise ValueError("Unknown family: GW")
    if not serial_values:
        raise ValueError("No gateway serials provided.")

    cleaned = [int(value) for value in serial_values]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(t("gw_error_serial_duplicate"))

    registry = _serial_registry_pull(settings)
    entry = registry["families"]["GW"]
    current_last = int(entry.get("last_serial", 0) or 0)
    lowest = min(cleaned)
    highest = max(cleaned)
    if lowest <= current_last:
        raise ValueError(
            t("serial_repo_error_overlap").format(
                family=_serial_family_name("GW"),
                current=current_last,
                requested=lowest,
            )
        )

    station = str(settings.get("station_name", "")).strip() or DEFAULT_SERIAL_SETTINGS["station_name"]
    width = max(SERIAL_FAMILY_SETTINGS["GW"]["number_width"], len(str(highest)))
    entry.update({
        "last_serial": int(highest),
        "updated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "updated_by": station,
        "last_count": len(cleaned),
        "last_range": f"{lowest:0{width}d}-{highest:0{width}d}",
        "last_year": str(year),
    })
    registry["families"]["GW"] = entry
    return _serial_registry_push(
        settings,
        registry,
        f"Update serial registry: GW {entry['last_range']}/{year}",
    )


def _parse_version(value):
    parts = []
    for chunk in str(value).strip().replace("-", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def _request_json(url, headers=None, data=None, method=None):
    req_headers = {"User-Agent": f"{APP_BUILD_NAME}/{APP_VERSION}"}
    if headers:
        req_headers.update(headers)
    req = urlrequest.Request(url, headers=req_headers, data=data, method=method)
    with urlrequest.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_json(url, headers=None):
    return _request_json(url, headers=headers)


def _github_api_headers(token=""):
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _download_binary(url, target_path):
    req = urlrequest.Request(url, headers={"User-Agent": f"{APP_BUILD_NAME}/{APP_VERSION}"})
    with urlrequest.urlopen(req, timeout=60) as response, open(target_path, "wb") as fh:
        shutil.copyfileobj(response, fh)


def _launch_windows_downloaded_app(downloaded_exe):
    bat_path = os.path.join(tempfile.gettempdir(), "generadorcsv_launch_update.bat")
    script = (
        "@echo off\n"
        "setlocal EnableExtensions\n"
        "ping 127.0.0.1 -n 3 > nul\n"
        f'start "" "{downloaded_exe}"\n'
        'del "%~f0"\n'
    )
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(script)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=creation_flags)

def _make_logo_images(display_h=52):
    """Carga logo.png a alta resoluciÃ³n y devuelve (img_light, img_dark).
    Trabaja en 2Ã— para HiDPI y usa LANCZOS para suavizado Ã³ptimo.
    Light: fondo blanco removido, colores originales.
    Dark:  mismos pixels recoloreados a blanco puro, fondo transparente.
    """
    try:
        src = Image.open(_resource("logo.png")).convert("RGBA")
        # Escalar a 2Ã— resoluciÃ³n interna para HiDPI (CTkImage lo gestiona)
        w, h = src.size
        render_h = display_h * 2
        render_w = int(w * render_h / h)
        src = src.resize((render_w, render_h), Image.LANCZOS)

        pixels = list(src.getdata())
        light_px, dark_px = [], []
        for r, g, b, a in pixels:
            lum = 0.299*r + 0.587*g + 0.114*b   # luminancia perceptual
            if lum > 220 and a > 200:            # fondo blanco â†’ transparente
                light_px.append((255, 255, 255, 0))
                dark_px.append((0, 0, 0, 0))
            else:
                light_px.append((r, g, b, a))          # color original
                dark_px.append((255, 255, 255, a))      # blanco para dark

        img_light = Image.new("RGBA", src.size)
        img_light.putdata(light_px)
        img_dark = Image.new("RGBA", src.size)
        img_dark.putdata(dark_px)
        # display_size en pÃ­xeles lÃ³gicos (CTkImage usarÃ¡ el doble en HiDPI)
        dw = int(w * display_h / h)
        return img_light, img_dark, dw, display_h
    except Exception:
        return None, None, 0, 0


def _make_black_logo_reader():
    try:
        from reportlab.lib.utils import ImageReader
    except Exception:
        return None

    import io

    logo_path = _resource("logo.png")
    if not os.path.isfile(logo_path):
        return None

    try:
        src = Image.open(logo_path).convert("RGBA")
        black_pixels = []
        for r, g, b, a in src.getdata():
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            if lum > 210 or a < 30:
                black_pixels.append((255, 255, 255, 0))
            else:
                black_pixels.append((0, 0, 0, a))
        black_img = Image.new("RGBA", src.size)
        black_img.putdata(black_pixels)
        buf = io.BytesIO()
        black_img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        return None

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Traducciones
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
TRANSLATIONS = {
    'es': {
        'csv_title':     'Generador de CSV - Dispositivos LoRa',
        'sec_name':      'Nombre del dispositivo',
        'lbl_prefix':    'Prefijo:',
        'lbl_from':      'Desde:',
        'lbl_to':        'Hasta:',
        'prev_error':    "['hasta' debe ser â‰¥ 'desde']",
        'prev_fmt':      '-> {n} dispositivos:  {a}  ...  {b}',
        'sec_lora':      'ConfiguraciÃ³n de red LoRa',
        'lbl_model':     'Modelo (Model):',
        'lbl_deveui':    'DevEUI inicial (16 hex):',
        'lbl_devaddr_i': 'DevAddr: extraÃ­do automÃ¡ticamente de los Ãºltimos 8 caracteres del DevEUI',
        'lbl_newskey':   'NewSKey (32 hex):',
        'lbl_appskey':   'AppSKey (32 hex):',
        'sec_coords':    'Coordenadas (mismas para todos)',
        'lbl_lat':       'Latitud:',
        'lbl_lon':       'Longitud:',
        'sec_extra':     'ParÃ¡metros adicionales',
        'lbl_childnumber': 'Cantidad valvulas / childnumber:',
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'Archivo de salida:',
        'btn_gen_csv':   'Generar CSV',
        'lbl_ready':     'Listo.',
        'labels_title':  'Generador de Etichette - PDF A4',
        'sec_opt1':      'Opcion 1 - Cargar desde CSV generado',
        'lbl_csv_file':  'Archivo CSV:',
        'btn_load':      'Cargar',
        'sec_opt2':      'Opcion 2 - Ingresar datos manualmente',
        'lbl_name_pfx':  'Prefijo nombre:',
        'lbl_deveui_m':  'DevEUI inicial (16 hex):',
        'sec_serial':    'Serial number',
        'lbl_ser_start': 'Serial inicio:',
        'lbl_year':      'AÃ±o:',
        'lbl_ser_fmt':   'Formato en la etiqueta: 04906/2026  ->  04907/2026  ->  ...',
        'sec_opts':      'Opciones de la etiqueta',
        'chk_bt':        'Incluir fila BLUETOOTH  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'Etichetta RTU in tubo  (header TECNIDRO / HYDRONET-RTU, sin Bluetooth)',
        'chk_lc':        'Etichetta RTU LORACONT  (23mm Ã— 87mm, header TECNIDRO / LORACONT-RTU)',
        'lbl_pdf_out':   'Archivo PDF de salida:',
        'btn_gen_pdf':   'Generar PDF Etichette',
        'lang_title':    'Seleccionar idioma',
        'lang_sub':      'Idioma de la interfaz:',
        'theme_label':   'Tema de la aplicaciÃ³n:',
        'theme_dark':    'Oscuro',
        'theme_light':   'Claro',
        'upd_title':     'Actualizaciones',
        'upd_version':   'VersiÃ³n actual:',
        'upd_source':    'URL del manifiesto:',
        'upd_auto':      'Buscar actualizaciones al abrir',
        'upd_save':      'Guardar configuraciÃ³n',
        'upd_check':     'Buscar actualizaciones',
        'upd_saved':     'ConfiguraciÃ³n de actualizaciÃ³n guardada.',
        'upd_status_idle':'Configura una URL de manifiesto para activar las actualizaciones online.',
        'upd_status_checking':'Comprobando actualizaciones...',
        'upd_status_latest':'Ya tienes la versiÃ³n mÃ¡s reciente.',
        'upd_status_available':'Nueva versiÃ³n disponible: {version}',
        'upd_status_disabled':'Las actualizaciones online estÃ¡n desactivadas.',
        'upd_error_title':'ActualizaciÃ³n',
        'upd_error_no_url':'Escribe la URL del manifiesto de actualizaciÃ³n.',
        'upd_error_bad_manifest':'El manifiesto no es vÃ¡lido o le faltan datos.',
        'upd_error_network':'No se pudo comprobar la actualizaciÃ³n.\n{error}',
        'upd_error_download':'No se pudo descargar la actualizaciÃ³n.\n{error}',
        'upd_confirm_title':'Nueva versiÃ³n disponible',
        'upd_confirm_body':'VersiÃ³n actual: {current}\nNueva versiÃ³n: {latest}\n\nÂ¿Quieres descargarla e instalarla ahora?',
        'upd_download_title':'Guardar actualizaciÃ³n como...',
        'upd_success_restart':'La actualizaciÃ³n se descargÃ³. El programa se cerrarÃ¡ para instalar la nueva versiÃ³n.',
        'json_title':    'Generador de archivos JSON',
        'sec_json_model':'Modelo dispositivo',
        'json_model_rtu':'RTU',
        'json_model_loracont':'LORACONT',
        'sec_json_config':'Configuracion dispositivo',
        'lbl_json_adc':'ADC:',
        'lbl_json_counters':'Counters:',
        'lbl_json_valves':'Valves:',
        'sec_valve':     'Tipo de vÃ¡lvula',
        'sec_allarme':   'Allarme Sportello',
        'sec_adc':       'ADC',
        'sec_deveui_j':  'ParÃ¡metros de radio',
        'lbl_deveui_j':  'DevEUI inicial (16 hex):',
        'lbl_devaddr_j': 'DevAddr: extraÃ­do automÃ¡ticamente de los Ãºltimos 8 caracteres del DevEUI',
        'sec_send_params': 'ParÃ¡metros de envÃ­o',
        'lbl_sendinterval':'Send Interval (ms):',
        'sec_out_json':  'Carpeta de salida',
        'lbl_out_folder':'Carpeta:',
        'btn_gen_json':  'Generar archivos JSON',
        'tic12_title':  'Generador de Etiquetas TIC12',
        'itic_title':   'Generador de Etiquetas I-TIC',
        'itic_solenoid_title': 'Conexion solenoide biestable 12v DC.',
        'itic_solenoid_red': 'Cable rojo   - V1_C',
        'itic_solenoid_black': 'Cable negro  - V1_O',
        'sec_tic_dev':  'Dispositivos',
        'lbl_tic_from': 'Desde (nÃºmero):',
        'lbl_tic_to':   'Hasta (nÃºmero):',
        'lbl_tic_yr':   'AÃ±o:',
        'lbl_tic_fw':   'VersiÃ³n FW:',
        'sec_tic_out':  'Archivo de salida',
        'lbl_tic_pdf':  'PDF de salida:',
        'btn_tic_gen':  'Generar PDF',
        'proj_title':   'Generador de Proyecto Completo',
        'sec_proj_loc': 'UbicaciÃ³n del proyecto',
        'lbl_root_fld': 'Carpeta raÃ­z:',
        'lbl_proj_nm':  'Nombre del proyecto:',
        'sec_proj_dev': 'Dispositivos',
        'sec_proj_csv': 'ParÃ¡metros CSV',
        'sec_proj_lbl': 'Tipo de etiqueta',
        'sec_proj_ser': 'Serial (para PDF)',
        'sec_proj_jsn': 'ParÃ¡metros JSON',
        'btn_gen_all':  'GENERAR TODO - CSV + JSON + Etichette',
        'proj_struct':  'Se crearÃ¡ la estructura:',
        'gw_title': 'Gateway',
        'gw_desc': 'Genera etiquetas GW en formato A4 replicando el modelo del archivo Excel. Cada pagina coloca hasta 5 gateways y cada gateway pide sus datos manualmente.',
        'gw_section_list': 'Gateways',
        'gw_add': 'Anadir gateway',
        'gw_edit': 'Editar seleccionado',
        'gw_delete': 'Eliminar seleccionado',
        'gw_count': '{total} gateways cargados. {pages} hoja(s) A4 estimadas.',
        'gw_year': 'Ano para serial:',
        'gw_output': 'Archivo PDF de salida:',
        'gw_generate': 'Generar PDF Gateway',
        'gw_ready': 'Listo para generar etiquetas GW.',
        'gw_section_tools': 'Comandos Gateway',
        'gw_shutdown_title': 'X4S LTE - Comando de apagado',
        'gw_shutdown_desc': 'Copia el comando para spegnere los gateway X4S LTE.',
        'gw_shutdown_copy': 'Copiar comando',
        'gw_shutdown_copied': 'Comando X4S LTE copiado.',
        'gw_dialog_title': 'Gateway',
        'gw_field_model': 'MODEL',
        'gw_field_alias': 'Nombre Gateway / Alias',
        'gw_field_serial': 'Serial N.',
        'gw_field_mac': 'MAC',
        'gw_field_deveui': 'DevEUI',
        'gw_cancel': 'Cancelar',
        'gw_accept': 'Aceptar',
        'gw_error_complete': 'Completa todos los campos del gateway.',
        'gw_error_select_edit': 'Selecciona un gateway para editar.',
        'gw_error_select_delete': 'Selecciona un gateway para eliminar.',
        'gw_error_output': 'Selecciona un archivo PDF de salida.',
        'gw_error_need_gateway': 'Anade al menos un gateway antes de generar el PDF.',
        'gw_error_need_year': 'Escribe el ano para el serial.',
        'gw_status_generating': 'Generando PDF Gateway...',
        'gw_status_done': 'OK  {total} etiquetas GW -> {name}',
        'gw_status_error': 'Error al generar el PDF Gateway.',
        'gw_error_serial_numeric': 'El serial del gateway #{index} debe ser numerico para actualizar el registro GitHub. Valor actual: {value}',
        'gw_error_serial_duplicate': 'Hay seriales GW repetidos en la lista. Revisa los valores antes de generar el PDF.',
        'gw_pdf_ok': 'PDF Gateway generado correctamente.\n\nEtiquetas: {total}\nHojas A4: {pages}\n\nArchivo:\n{path}',
        'fw_title': 'FW Version',
        'fw_desc': 'Boton PIC: copia el nombre del microcontrolador. Boton firmware: guarda el archivo HEX donde quieras.',
        'fw_status_ready': 'Pulsa un PIC para copiarlo o un firmware para guardarlo.',
        'fw_status_pic_copied': 'PIC copiado: {value}',
        'fw_status_saved': 'Firmware guardado: {value}',
        'fw_error_missing_title': 'Error',
        'fw_error_missing_hex': 'No se encontro el firmware:\n{filename}',
        'fw_save_title': 'Guardar firmware como...',
        'fw_no_hex': 'Sin HEX cargado',
        'fw_section_rtu': 'RTU',
        'fw_section_tic12': 'TIC12',
        'fw_section_fungi': 'FUNGHI',
        'fw_section_instantanei': 'INSTANTANEI',
        'fw_item_3c1s_4c': 'RTU 3C1S o 4C Singola Scheda',
        'fw_item_1v1c_k40': 'RTU 1V1C C/RESET REV4',
        'fw_item_8v_rev4_blte': 'RTU 8V BLUETOOTH',
        'fw_item_loracont': 'RTU LORACONT',
        'fw_item_rn2483': 'RN2483',
        'fw_item_external_protection': 'EXTERNAL PROTECTION (Caramella)',
        'fw_item_tic12_control_unit': 'CENTRALINA TIC12',
        'fw_item_expansion_acdc': 'MODULI DI ESPANSIONE',
        'fw_item_rev6': 'FUNGHO REV6',
        'fw_item_rev4': 'FUNGHO REV4',
        'fw_item_new': 'INSTANTANEO NUOVO',
        'fw_item_old_100l': 'INSTANTANEO VECCHIO 100L',
        'fw_item_old_1000l': 'INSTANTANEO VECCHIO 1000L',
        'serial_title': 'Serial',
        'serial_desc': 'Herramientas y archivos utiles para trabajo por serial.',
        'serial_section_tools': 'Herramientas Serial',
        'serial_hyperterminal_title': 'Hyperterminal',
        'serial_hyperterminal_desc': 'Guarda el paquete ZIP de Hyperterminal donde quieras.',
        'serial_hyperterminal_button': 'Guardar Hyperterminal',
        'serial_terminal_antonio_title': 'Terminal Antonio (RTU Bluetooth e LORACONT)',
        'serial_terminal_antonio_desc': 'Guarda el paquete ZIP de Terminal Antonio donde quieras.',
        'serial_terminal_antonio_button': 'Guardar Terminal Antonio',
        'serial_status': 'Pestana Serial lista.',
        'serial_status_saved': 'Archivo guardado: {value}',
        'serial_error_title': 'Error',
        'serial_error_missing': 'No se encontro el archivo:\n{filename}',
        'serial_save_title': 'Guardar Hyperterminal como...',
        'serial_repo_title': 'Registro serial GitHub',
        'serial_repo_desc': 'Sincroniza el ultimo serial usado entre los PC de la oficina directamente por internet usando GitHub.',
        'serial_repo_path': 'URL registro RAW:',
        'serial_repo_branch': 'Branch:',
        'serial_repo_file': 'URL API GitHub:',
        'serial_repo_token': 'GitHub token:',
        'serial_repo_station': 'Nombre PC / usuario:',
        'serial_repo_save': 'Guardar configuracion',
        'serial_repo_sync': 'Sincronizar desde GitHub',
        'serial_repo_publish': 'Guardar contadores en GitHub',
        'serial_repo_save_value': 'Salva valore {family}',
        'serial_repo_save_all': 'Salva tutti i valori',
        'serial_repo_ready': 'Configura las URL de GitHub, el token y sincroniza el registro serial.',
        'serial_repo_saved': 'Configuracion serial guardada.',
        'serial_repo_synced': 'Registro serial sincronizado desde GitHub.',
        'serial_repo_published': 'Contadores serial actualizados en GitHub.',
        'serial_repo_value_saved': 'Valor guardado en GitHub para {family}: {value}',
        'serial_repo_all_saved': 'Todos los valores se guardaron en GitHub.',
        'serial_repo_saved_title': 'GitHub actualizado',
        'serial_repo_sync_after_generate': 'Actualizando ultimo serial en GitHub...',
        'serial_repo_update_failed_title': 'Etiquetas generadas, GitHub no actualizado',
        'serial_repo_update_failed_body': 'Los archivos se generaron correctamente, pero no se pudo actualizar GitHub.\n\n{error}\n\nGuarda el valor manualmente en la pestana Serial.',
        'serial_repo_status_format': '{family}: ultimo {serial}  |  lote {batch}  |  {who}',
        'serial_repo_status_empty': 'Sin datos',
        'serial_repo_error_missing_path': 'Escribe la URL RAW del registro serial en GitHub.',
        'serial_repo_error_missing_repo': 'La configuracion del repositorio GitHub no es valida:\n{path}',
        'serial_repo_error_missing_token': 'Falta el GitHub token. Configuralo en la pestana Serial para poder guardar los nuevos seriales.',
        'serial_repo_error_overlap': '{family} ya llega hasta {current}. El serial solicitado ({requested}) repetiria codigos.',
        'serial_password_title': 'Contrasena',
        'serial_password_prompt': 'Escribe la contrasena para guardar el valor en GitHub:',
        'serial_password_error': 'Contrasena incorrecta.',
        'serial_next_button': 'Usar siguiente serial GitHub',
        'serial_next_status': '{family}: siguiente serial sugerido {value}',
        'serial_repo_reserved': 'Registro GitHub actualizado para {family}: {start} - {end}/{year}',
        'serial_family_rtu': 'RTU',
        'serial_family_gw': 'GW',
        'serial_family_itic': 'I-TIC',
        'serial_family_tic12': 'TIC12',
        'manuals_title': 'Manuales',
        'manuals_desc': 'Zona dedicada a manuales, guias y documentacion tecnica del programa y de los dispositivos.',
        'manuals_section_library': 'Biblioteca manuales',
        'manuals_group_itic': 'I-TIC',
        'manuals_group_loracont': 'LoraCont',
        'manuals_group_hydronet': 'Piattaforma Hydronet',
        'manuals_group_tic12': 'TIC12',
        'manuals_button_save': 'Guardar PDF',
        'manuals_save_title': 'Guardar manual',
        'manuals_saved': 'Manual guardado: {name}',
        'manuals_missing': 'No se encontro el manual embebido: {name}',
        'nav_manuals': 'Manuales',
        'nav_language': 'Idiomas',
        'header_manuals_title': 'Manuales',
        'header_manuals_subtitle': 'Area dedicada a manuales, guias y documentacion tecnica.',
        'header_language_title': 'Preferencias',
        'header_language_subtitle': 'Idioma, tema y actualizaciones de la aplicacion.',
    },
    'en': {
        'csv_title':     'CSV Generator - LoRa Devices',
        'sec_name':      'Device name',
        'lbl_prefix':    'Prefix:',
        'lbl_from':      'From:',
        'lbl_to':        'To:',
        'prev_error':    "['to' must be â‰¥ 'from']",
        'prev_fmt':      '-> {n} devices:  {a}  ...  {b}',
        'sec_lora':      'LoRa network configuration',
        'lbl_model':     'Model:',
        'lbl_deveui':    'Initial DevEUI (16 hex):',
        'lbl_devaddr_i': 'DevAddr: automatically extracted from last 8 characters of DevEUI',
        'lbl_newskey':   'NewSKey (32 hex):',
        'lbl_appskey':   'AppSKey (32 hex):',
        'sec_coords':    'Coordinates (same for all)',
        'lbl_lat':       'Latitude:',
        'lbl_lon':       'Longitude:',
        'sec_extra':     'Additional parameters',
        'lbl_childnumber': 'Valve count / childnumber:',
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'Output file:',
        'btn_gen_csv':   'Generate CSV',
        'lbl_ready':     'Ready.',
        'labels_title':  'Label Generator - PDF A4',
        'sec_opt1':      'Option 1 - Load from generated CSV',
        'lbl_csv_file':  'CSV file:',
        'btn_load':      'Load',
        'sec_opt2':      'Option 2 - Enter data manually',
        'lbl_name_pfx':  'Name prefix:',
        'lbl_deveui_m':  'Initial DevEUI (16 hex):',
        'sec_serial':    'Serial number',
        'lbl_ser_start': 'Serial start:',
        'lbl_year':      'Year:',
        'lbl_ser_fmt':   'Label format: 04906/2026  ->  04907/2026  ->  ...',
        'sec_opts':      'Label options',
        'chk_bt':        'Include BLUETOOTH row  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'RTU tube label  (TECNIDRO / HYDRONET-RTU header, no Bluetooth)',
        'chk_lc':        'RTU LORACONT label  (23mm Ã— 87mm, TECNIDRO / LORACONT-RTU header)',
        'lbl_pdf_out':   'Output PDF file:',
        'btn_gen_pdf':   'Generate PDF Labels',
        'lang_title':    'Select language',
        'lang_sub':      'Interface language:',
        'theme_label':   'Application theme:',
        'theme_dark':    'Dark',
        'theme_light':   'Light',
        'upd_title':     'Updates',
        'upd_version':   'Current version:',
        'upd_source':    'Manifest URL:',
        'upd_auto':      'Check for updates on startup',
        'upd_save':      'Save settings',
        'upd_check':     'Check for updates',
        'upd_saved':     'Update settings saved.',
        'upd_status_idle':'Set a manifest URL to enable online updates.',
        'upd_status_checking':'Checking for updates...',
        'upd_status_latest':'You already have the latest version.',
        'upd_status_available':'New version available: {version}',
        'upd_status_disabled':'Online updates are disabled.',
        'upd_error_title':'Update',
        'upd_error_no_url':'Enter the update manifest URL.',
        'upd_error_bad_manifest':'The manifest is invalid or missing data.',
        'upd_error_network':'Unable to check for updates.\n{error}',
        'upd_error_download':'Unable to download the update.\n{error}',
        'upd_confirm_title':'New version available',
        'upd_confirm_body':'Current version: {current}\nNew version: {latest}\n\nDo you want to download and install it now?',
        'upd_download_title':'Save update as...',
        'upd_success_restart':'The update was downloaded. The program will close to install the new version.',
        'json_title':    'JSON File Generator',
        'sec_json_model':'Device model',
        'json_model_rtu':'RTU',
        'json_model_loracont':'LORACONT',
        'sec_json_config':'Device configuration',
        'lbl_json_adc':'ADC:',
        'lbl_json_counters':'Counters:',
        'lbl_json_valves':'Valves:',
        'sec_valve':     'Valve type',
        'sec_allarme':   'Door Alarm',
        'sec_adc':       'ADC',
        'gw_title': 'Gateway',
        'gw_desc': 'Generate GW labels in A4 format following the Excel sample. Each page fits up to 5 gateways and every gateway asks for its own manual data.',
        'gw_section_list': 'Gateways',
        'gw_add': 'Add gateway',
        'gw_edit': 'Edit selected',
        'gw_delete': 'Delete selected',
        'gw_count': '{total} gateways loaded. Estimated A4 page(s): {pages}.',
        'gw_year': 'Year for serial:',
        'gw_output': 'Output PDF file:',
        'gw_generate': 'Generate Gateway PDF',
        'gw_ready': 'Ready to generate GW labels.',
        'gw_section_tools': 'Gateway Commands',
        'gw_shutdown_title': 'X4S LTE - Shutdown command',
        'gw_shutdown_desc': 'Copy the command used to power off X4S LTE gateways.',
        'gw_shutdown_copy': 'Copy command',
        'gw_shutdown_copied': 'X4S LTE command copied.',
        'gw_dialog_title': 'Gateway',
        'gw_field_model': 'MODEL',
        'gw_field_alias': 'Gateway name / Alias',
        'gw_field_serial': 'Serial N.',
        'gw_field_mac': 'MAC',
        'gw_field_deveui': 'DevEUI',
        'gw_cancel': 'Cancel',
        'gw_accept': 'Accept',
        'gw_error_complete': 'Complete all gateway fields.',
        'gw_error_select_edit': 'Select a gateway to edit.',
        'gw_error_select_delete': 'Select a gateway to delete.',
        'gw_error_output': 'Select an output PDF file.',
        'gw_error_need_gateway': 'Add at least one gateway before generating the PDF.',
        'gw_error_need_year': 'Enter the year for the serial.',
        'gw_status_generating': 'Generating Gateway PDF...',
        'gw_status_done': 'OK  {total} GW labels -> {name}',
        'gw_status_error': 'Error while generating the Gateway PDF.',
        'gw_error_serial_numeric': 'Gateway serial #{index} must be numeric to update the GitHub registry. Current value: {value}',
        'gw_error_serial_duplicate': 'There are duplicated GW serials in the list. Review the values before generating the PDF.',
        'gw_pdf_ok': 'Gateway PDF generated successfully.\n\nLabels: {total}\nA4 pages: {pages}\n\nFile:\n{path}',
        'fw_title': 'FW Version',
        'fw_desc': 'PIC button: copies the microcontroller name. Firmware button: saves the HEX file wherever you want.',
        'fw_status_ready': 'Click a PIC to copy it or a firmware button to save it.',
        'fw_status_pic_copied': 'PIC copied: {value}',
        'fw_status_saved': 'Firmware saved: {value}',
        'fw_error_missing_title': 'Error',
        'fw_error_missing_hex': 'Firmware file not found:\n{filename}',
        'fw_save_title': 'Save firmware as...',
        'fw_no_hex': 'No HEX loaded',
        'fw_section_rtu': 'RTU',
        'fw_section_tic12': 'TIC12',
        'fw_section_fungi': 'FUNGHI',
        'fw_section_instantanei': 'INSTANTANEI',
        'fw_item_3c1s_4c': 'RTU 3C1S o 4C Singola Scheda',
        'fw_item_1v1c_k40': 'RTU 1V1C C/RESET REV4',
        'fw_item_8v_rev4_blte': 'RTU 8V BLUETOOTH',
        'fw_item_loracont': 'RTU LORACONT',
        'fw_item_rn2483': 'RN2483',
        'fw_item_external_protection': 'EXTERNAL PROTECTION (Caramella)',
        'fw_item_tic12_control_unit': 'CENTRALINA TIC12',
        'fw_item_expansion_acdc': 'MODULI DI ESPANSIONE',
        'fw_item_rev6': 'FUNGHO REV6',
        'fw_item_rev4': 'FUNGHO REV4',
        'fw_item_new': 'INSTANTANEO NUOVO',
        'fw_item_old_100l': 'INSTANTANEO VECCHIO 100L',
        'fw_item_old_1000l': 'INSTANTANEO VECCHIO 1000L',
        'serial_title': 'Serial',
        'serial_desc': 'Tools and useful files for serial work.',
        'serial_section_tools': 'Serial Tools',
        'serial_hyperterminal_title': 'Hyperterminal',
        'serial_hyperterminal_desc': 'Save the Hyperterminal ZIP package wherever you want.',
        'serial_hyperterminal_button': 'Save Hyperterminal',
        'serial_terminal_antonio_title': 'Terminal Antonio (RTU Bluetooth and LORACONT)',
        'serial_terminal_antonio_desc': 'Save the Terminal Antonio ZIP package wherever you want.',
        'serial_terminal_antonio_button': 'Save Terminal Antonio',
        'serial_status': 'Serial tab ready.',
        'serial_status_saved': 'File saved: {value}',
        'serial_error_title': 'Error',
        'serial_error_missing': 'File not found:\n{filename}',
        'serial_save_title': 'Save Hyperterminal as...',
        'serial_repo_title': 'GitHub serial registry',
        'serial_repo_desc': 'Sync the last used serial across office PCs directly over the internet using GitHub.',
        'serial_repo_path': 'Registry RAW URL:',
        'serial_repo_branch': 'Branch:',
        'serial_repo_file': 'GitHub API URL:',
        'serial_repo_token': 'GitHub token:',
        'serial_repo_station': 'PC / user name:',
        'serial_repo_save': 'Save settings',
        'serial_repo_sync': 'Sync from GitHub',
        'serial_repo_publish': 'Save counters to GitHub',
        'serial_repo_save_value': 'Save value {family}',
        'serial_repo_save_all': 'Save all values',
        'serial_repo_ready': 'Configure the GitHub URLs, token, and sync the serial registry.',
        'serial_repo_saved': 'Serial settings saved.',
        'serial_repo_synced': 'Serial registry synced from GitHub.',
        'serial_repo_published': 'Serial counters updated on GitHub.',
        'serial_repo_value_saved': 'Value saved on GitHub for {family}: {value}',
        'serial_repo_all_saved': 'All values were saved to GitHub.',
        'serial_repo_saved_title': 'GitHub updated',
        'serial_repo_sync_after_generate': 'Updating last serial on GitHub...',
        'serial_repo_update_failed_title': 'Files generated, GitHub not updated',
        'serial_repo_update_failed_body': 'The files were generated successfully, but GitHub could not be updated.\n\n{error}\n\nSave the value manually from the Serial tab.',
        'serial_repo_status_format': '{family}: last {serial}  |  batch {batch}  |  {who}',
        'serial_repo_status_empty': 'No data',
        'serial_repo_error_missing_path': 'Enter the GitHub RAW URL for the serial registry.',
        'serial_repo_error_missing_repo': 'The GitHub repository configuration is not valid:\n{path}',
        'serial_repo_error_missing_token': 'The GitHub token is missing. Configure it in the Serial tab to save new serials.',
        'serial_repo_error_overlap': '{family} already reaches {current}. Requested serial {requested} would duplicate codes.',
        'serial_password_title': 'Password',
        'serial_password_prompt': 'Enter the password to save the value to GitHub:',
        'serial_password_error': 'Incorrect password.',
        'serial_next_button': 'Use next GitHub serial',
        'serial_next_status': '{family}: next suggested serial {value}',
        'serial_repo_reserved': 'GitHub registry updated for {family}: {start} - {end}/{year}',
        'serial_family_rtu': 'RTU',
        'serial_family_gw': 'GW',
        'serial_family_itic': 'I-TIC',
        'serial_family_tic12': 'TIC12',
        'tic12_title':  'TIC12 Label Generator',
        'itic_title':   'I-TIC Label Generator',
        'itic_solenoid_title': '12v DC bistable solenoid wiring.',
        'itic_solenoid_red': 'Red wire    - V1_C',
        'itic_solenoid_black': 'Black wire  - V1_O',
        'sec_tic_dev':  'Devices',
        'lbl_tic_from': 'From (number):',
        'lbl_tic_to':   'To (number):',
        'lbl_tic_yr':   'Year:',
        'lbl_tic_fw':   'FW version:',
        'sec_tic_out':  'Output file',
        'lbl_tic_pdf':  'Output PDF:',
        'btn_tic_gen':  'Generate PDF',
        'manuals_title': 'Manuals',
        'manuals_desc': 'Area dedicated to manuals, guides, and technical documentation for the app and devices.',
        'manuals_section_library': 'Manual library',
        'manuals_group_itic': 'I-TIC',
        'manuals_group_loracont': 'LoraCont',
        'manuals_group_hydronet': 'Hydronet Platform',
        'manuals_group_tic12': 'TIC12',
        'manuals_button_save': 'Save PDF',
        'manuals_save_title': 'Save manual',
        'manuals_saved': 'Manual saved: {name}',
        'manuals_missing': 'Embedded manual not found: {name}',
        'nav_manuals': 'Manuals',
        'nav_language': 'Languages',
        'header_manuals_title': 'Manuals',
        'header_manuals_subtitle': 'Area dedicated to manuals, guides, and technical documentation.',
        'header_language_title': 'Preferences',
        'header_language_subtitle': 'Language, theme, and application updates.',
    },
    'it': {
        'csv_title':     'Generatore CSV - Dispositivi LoRa',
        'sec_name':      'Nome del dispositivo',
        'lbl_prefix':    'Prefisso:',
        'lbl_from':      'Da:',
        'lbl_to':        'A:',
        'prev_error':    "['a' deve essere â‰¥ 'da']",
        'prev_fmt':      '-> {n} dispositivi:  {a}  ...  {b}',
        'sec_lora':      'Configurazione rete LoRa',
        'lbl_model':     'Modello (Model):',
        'lbl_deveui':    'DevEUI iniziale (16 hex):',
        'lbl_devaddr_i': 'DevAddr: estratto automaticamente dagli ultimi 8 caratteri del DevEUI',
        'lbl_newskey':   'NewSKey (32 hex):',
        'lbl_appskey':   'AppSKey (32 hex):',
        'sec_coords':    'Coordinate (stesse per tutti)',
        'lbl_lat':       'Latitudine:',
        'lbl_lon':       'Longitudine:',
        'sec_extra':     'Parametri aggiuntivi',
        'lbl_childnumber': 'Numero valvole / childnumber:',
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'File di output:',
        'btn_gen_csv':   'Genera CSV',
        'lbl_ready':     'Pronto.',
        'labels_title':  'Generatore Etichette - PDF A4',
        'sec_opt1':      'Opzione 1 - Carica da CSV generato',
        'lbl_csv_file':  'File CSV:',
        'btn_load':      'Carica',
        'sec_opt2':      'Opzione 2 - Inserisci dati manualmente',
        'lbl_name_pfx':  'Prefisso nome:',
        'lbl_deveui_m':  'DevEUI iniziale (16 hex):',
        'sec_serial':    'Numero seriale',
        'lbl_ser_start': 'Seriale inizio:',
        'lbl_year':      'Anno:',
        'lbl_ser_fmt':   'Formato etichetta: 04906/2026  ->  04907/2026  ->  ...',
        'sec_opts':      'Opzioni etichetta',
        'chk_bt':        'Includi riga BLUETOOTH  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'Etichetta RTU in tubo  (header TECNIDRO / HYDRONET-RTU, senza Bluetooth)',
        'chk_lc':        'Etichetta RTU LORACONT  (23mm Ã— 87mm, header TECNIDRO / LORACONT-RTU)',
        'lbl_pdf_out':   'File PDF di output:',
        'btn_gen_pdf':   'Genera PDF Etichette',
        'lang_title':    'Seleziona lingua',
        'lang_sub':      'Lingua interfaccia:',
        'theme_label':   'Tema applicazione:',
        'theme_dark':    'Scuro',
        'theme_light':   'Chiaro',
        'upd_title':     'Aggiornamenti',
        'upd_version':   'Versione attuale:',
        'upd_source':    'URL del manifest:',
        'upd_auto':      "Controlla aggiornamenti all'avvio",
        'upd_save':      'Salva configurazione',
        'upd_check':     'Controlla aggiornamenti',
        'upd_saved':     'Configurazione aggiornamenti salvata.',
        'upd_status_idle':'Configura un URL del manifest per attivare gli aggiornamenti online.',
        'upd_status_checking':'Controllo aggiornamenti...',
        'upd_status_latest':"Hai gia l'ultima versione.",
        'upd_status_available':'Nuova versione disponibile: {version}',
        'upd_status_disabled':'Gli aggiornamenti online sono disattivati.',
        'upd_error_title':'Aggiornamento',
        'upd_error_no_url':"Inserisci l'URL del manifest di aggiornamento.",
        'upd_error_bad_manifest':'Il manifest non Ã¨ valido o mancano dei dati.',
        'upd_error_network':'Impossibile controllare gli aggiornamenti.\n{error}',
        'upd_error_download':"Impossibile scaricare l'aggiornamento.\n{error}",
        'upd_confirm_title':'Nuova versione disponibile',
        'upd_confirm_body':'Versione attuale: {current}\nNuova versione: {latest}\n\nVuoi scaricarla e installarla adesso?',
        'upd_download_title':'Salva aggiornamento come...',
        'upd_success_restart':"L'aggiornamento e stato scaricato. Il programma verra chiuso per installare la nuova versione.",
        'json_title':    'Generatore file JSON',
        'sec_json_model':'Modello dispositivo',
        'json_model_rtu':'RTU',
        'json_model_loracont':'LORACONT',
        'sec_json_config':'Configurazione dispositivo',
        'lbl_json_adc':'ADC:',
        'lbl_json_counters':'Counters:',
        'lbl_json_valves':'Valves:',
        'sec_valve':     'Tipo di valvola',
        'sec_allarme':   'Allarme Sportello',
        'sec_adc':       'ADC',
        'sec_deveui_j':  'Parametri radio',
        'lbl_deveui_j':  'DevEUI iniziale (16 hex):',
        'lbl_devaddr_j': 'DevAddr: estratto automaticamente dagli ultimi 8 caratteri del DevEUI',
        'sec_send_params': 'Parametri di invio',
        'lbl_sendinterval':'Send Interval (ms):',
        'sec_out_json':  'Cartella di output',
        'lbl_out_folder':'Cartella:',
        'btn_gen_json':  'Genera file JSON',
        'tic12_title':  'Generatore Etichette TIC12',
        'itic_title':   'Generatore Etichette I-TIC',
        'itic_solenoid_title': 'Collegamento Solenoide Bistabile 12v DC.',
        'itic_solenoid_red': 'Cavo Rosso   - V1_C',
        'itic_solenoid_black': 'Cavo Nero    - V1_O',
        'sec_tic_dev':  'Dispositivi',
        'lbl_tic_from': 'Da (numero):',
        'lbl_tic_to':   'A (numero):',
        'lbl_tic_yr':   'Anno:',
        'lbl_tic_fw':   'Versione FW:',
        'sec_tic_out':  'File di output',
        'lbl_tic_pdf':  'PDF di output:',
        'btn_tic_gen':  'Genera PDF',
        'proj_title':   'Generatore Progetto Completo',
        'sec_proj_loc': 'Posizione del progetto',
        'lbl_root_fld': 'Cartella radice:',
        'lbl_proj_nm':  'Nome del progetto:',
        'sec_proj_dev': 'Dispositivi',
        'sec_proj_csv': 'Parametri CSV',
        'sec_proj_lbl': 'Tipo etichetta',
        'sec_proj_ser': 'Seriale (per PDF)',
        'sec_proj_jsn': 'Parametri JSON',
        'btn_gen_all':  'GENERA TUTTO - CSV + JSON + Etichette',
        'proj_struct':  'VerrÃ  creata la struttura:',
        'gw_title': 'Gateway',
        'gw_desc': 'Genera etichette GW in formato A4 seguendo il modello Excel. Ogni pagina contiene fino a 5 gateway e ogni gateway richiede i suoi dati manuali.',
        'gw_section_list': 'Gateway',
        'gw_add': 'Aggiungi gateway',
        'gw_edit': 'Modifica selezionato',
        'gw_delete': 'Elimina selezionato',
        'gw_count': '{total} gateway caricati. Pagine A4 stimate: {pages}.',
        'gw_year': 'Anno per seriale:',
        'gw_output': 'File PDF di output:',
        'gw_generate': 'Genera PDF Gateway',
        'gw_ready': 'Pronto per generare etichette GW.',
        'gw_section_tools': 'Comandi Gateway',
        'gw_shutdown_title': 'X4S LTE - Comando di spegnimento',
        'gw_shutdown_desc': 'Copia il comando per spegnere i gateway X4S LTE.',
        'gw_shutdown_copy': 'Copia comando',
        'gw_shutdown_copied': 'Comando X4S LTE copiato.',
        'gw_dialog_title': 'Gateway',
        'gw_field_model': 'MODEL',
        'gw_field_alias': 'Nome gateway / Alias',
        'gw_field_serial': 'Serial N.',
        'gw_field_mac': 'MAC',
        'gw_field_deveui': 'DevEUI',
        'gw_cancel': 'Annulla',
        'gw_accept': 'Conferma',
        'gw_error_complete': 'Completa tutti i campi del gateway.',
        'gw_error_select_edit': 'Seleziona un gateway da modificare.',
        'gw_error_select_delete': 'Seleziona un gateway da eliminare.',
        'gw_error_output': 'Seleziona un file PDF di output.',
        'gw_error_need_gateway': 'Aggiungi almeno un gateway prima di generare il PDF.',
        'gw_error_need_year': 'Inserisci l anno per il seriale.',
        'gw_status_generating': 'Generazione PDF Gateway...',
        'gw_status_done': 'OK  {total} etichette GW -> {name}',
        'gw_status_error': 'Errore durante la generazione del PDF Gateway.',
        'gw_error_serial_numeric': 'Il seriale del gateway #{index} deve essere numerico per aggiornare il registro GitHub. Valore attuale: {value}',
        'gw_error_serial_duplicate': 'Ci sono seriali GW duplicati nella lista. Controlla i valori prima di generare il PDF.',
        'gw_pdf_ok': 'PDF Gateway generato correttamente.\n\nEtichette: {total}\nPagine A4: {pages}\n\nFile:\n{path}',
        'fw_title': 'FW Version',
        'fw_desc': 'Pulsante PIC: copia il nome del microcontrollore. Pulsante firmware: salva il file HEX dove vuoi.',
        'fw_status_ready': 'Premi un PIC per copiarlo o un firmware per salvarlo.',
        'fw_status_pic_copied': 'PIC copiato: {value}',
        'fw_status_saved': 'Firmware salvato: {value}',
        'fw_error_missing_title': 'Errore',
        'fw_error_missing_hex': 'Firmware non trovato:\n{filename}',
        'fw_save_title': 'Salva firmware come...',
        'fw_no_hex': 'Nessun HEX caricato',
        'fw_section_rtu': 'RTU',
        'fw_section_tic12': 'TIC12',
        'fw_section_fungi': 'FUNGHI',
        'fw_section_instantanei': 'INSTANTANEI',
        'fw_item_3c1s_4c': 'RTU 3C1S o 4C Singola Scheda',
        'fw_item_1v1c_k40': 'RTU 1V1C C/RESET REV4',
        'fw_item_8v_rev4_blte': 'RTU 8V BLUETOOTH',
        'fw_item_loracont': 'RTU LORACONT',
        'fw_item_rn2483': 'RN2483',
        'fw_item_external_protection': 'EXTERNAL PROTECTION (Caramella)',
        'fw_item_tic12_control_unit': 'CENTRALINA TIC12',
        'fw_item_expansion_acdc': 'MODULI DI ESPANSIONE',
        'fw_item_rev6': 'FUNGHO REV6',
        'fw_item_rev4': 'FUNGHO REV4',
        'fw_item_new': 'INSTANTANEO NUOVO',
        'fw_item_old_100l': 'INSTANTANEO VECCHIO 100L',
        'fw_item_old_1000l': 'INSTANTANEO VECCHIO 1000L',
        'serial_title': 'Serial',
        'serial_desc': 'Strumenti e file utili per il lavoro seriale.',
        'serial_section_tools': 'Strumenti Serial',
        'serial_hyperterminal_title': 'Hyperterminal',
        'serial_hyperterminal_desc': 'Salva il pacchetto ZIP di Hyperterminal dove vuoi.',
        'serial_hyperterminal_button': 'Salva Hyperterminal',
        'serial_terminal_antonio_title': 'Terminal Antonio (RTU Bluetooth e LORACONT)',
        'serial_terminal_antonio_desc': 'Salva il pacchetto ZIP di Terminal Antonio dove vuoi.',
        'serial_terminal_antonio_button': 'Salva Terminal Antonio',
        'serial_status': 'Scheda Serial pronta.',
        'serial_status_saved': 'File salvato: {value}',
        'serial_error_title': 'Errore',
        'serial_error_missing': 'File non trovato:\n{filename}',
        'serial_save_title': 'Salva Hyperterminal come...',
        'serial_repo_title': 'Registro serial GitHub',
        'serial_repo_desc': 'Sincronizza l ultimo seriale usato tra i PC dell ufficio direttamente via internet usando GitHub.',
        'serial_repo_path': 'URL RAW registro:',
        'serial_repo_branch': 'Branch:',
        'serial_repo_file': 'URL API GitHub:',
        'serial_repo_token': 'GitHub token:',
        'serial_repo_station': 'Nome PC / utente:',
        'serial_repo_save': 'Salva configurazione',
        'serial_repo_sync': 'Sincronizza da GitHub',
        'serial_repo_publish': 'Salva contatori su GitHub',
        'serial_repo_save_value': 'Salva valore {family}',
        'serial_repo_save_all': 'Salva tutti i valori',
        'serial_repo_ready': 'Configura le URL di GitHub, il token e sincronizza il registro seriale.',
        'serial_repo_saved': 'Configurazione seriale salvata.',
        'serial_repo_synced': 'Registro seriale sincronizzato da GitHub.',
        'serial_repo_published': 'Contatori seriali aggiornati su GitHub.',
        'serial_repo_value_saved': 'Valore salvato su GitHub per {family}: {value}',
        'serial_repo_all_saved': 'Tutti i valori sono stati salvati su GitHub.',
        'serial_repo_saved_title': 'GitHub aggiornato',
        'serial_repo_sync_after_generate': 'Aggiornamento ultimo seriale su GitHub...',
        'serial_repo_update_failed_title': 'Etichette generate, GitHub non aggiornato',
        'serial_repo_update_failed_body': 'I file sono stati generati correttamente, ma non e stato possibile aggiornare GitHub.\n\n{error}\n\nSalva il valore manualmente dalla scheda Serial.',
        'serial_repo_status_format': '{family}: ultimo {serial}  |  lotto {batch}  |  {who}',
        'serial_repo_status_empty': 'Nessun dato',
        'serial_repo_error_missing_path': 'Inserisci la URL RAW del registro seriale su GitHub.',
        'serial_repo_error_missing_repo': 'La configurazione del repository GitHub non e valida:\n{path}',
        'serial_repo_error_missing_token': 'Manca il GitHub token. Configuralo nella scheda Serial per salvare i nuovi seriali.',
        'serial_repo_error_overlap': '{family} arriva gia a {current}. Il seriale richiesto ({requested}) duplichera dei codici.',
        'serial_password_title': 'Password',
        'serial_password_prompt': 'Inserisci la password per salvare il valore su GitHub:',
        'serial_password_error': 'Password non corretta.',
        'serial_next_button': 'Usa il prossimo seriale GitHub',
        'serial_next_status': '{family}: prossimo seriale suggerito {value}',
        'serial_repo_reserved': 'Registro GitHub aggiornato per {family}: {start} - {end}/{year}',
        'serial_family_rtu': 'RTU',
        'serial_family_gw': 'GW',
        'serial_family_itic': 'I-TIC',
        'serial_family_tic12': 'TIC12',
        'manuals_title': 'Manuali',
        'manuals_desc': 'Area dedicata a manuali, guide e documentazione tecnica del programma e dei dispositivi.',
        'manuals_section_library': 'Libreria manuali',
        'manuals_group_itic': 'I-TIC',
        'manuals_group_loracont': 'LoraCont',
        'manuals_group_hydronet': 'Piattaforma Hydronet',
        'manuals_group_tic12': 'TIC12',
        'manuals_button_save': 'Salva PDF',
        'manuals_save_title': 'Salva manuale',
        'manuals_saved': 'Manuale salvato: {name}',
        'manuals_missing': 'Manuale incorporato non trovato: {name}',
        'nav_manuals': 'Manuali',
        'nav_language': 'Lingue',
        'header_manuals_title': 'Manuali',
        'header_manuals_subtitle': 'Area dedicata a manuali, guide e documentazione tecnica.',
        'header_language_title': 'Lingue',
        'header_language_subtitle': 'Lingua, tema e aggiornamenti dell\'applicazione.',
    },
}

_cur_lang = ['it']
_lang_cbs = []

def t(key):
    return TRANSLATIONS[_cur_lang[0]].get(key, key)

def set_lang(code):
    _cur_lang[0] = code
    for cb in _lang_cbs:
        cb()


def _serial_family_name(family):
    info = SERIAL_FAMILY_SETTINGS.get(family, {})
    return t(info.get("entry_key", family))


def _set_serial_registry_cache(registry):
    global _serial_registry_cache
    _serial_registry_cache = _normalize_serial_registry(registry)
    return _serial_registry_cache


def _serial_registry_fetch_cached(settings=None, force=False):
    global _serial_registry_cache
    if force or _serial_registry_cache is None:
        _serial_registry_cache = _normalize_serial_registry(
            _serial_registry_fetch(settings or _load_serial_settings())
        )
    return copy.deepcopy(_serial_registry_cache)


def _next_available_serial(family, count=1, settings=None, force=False):
    registry = _serial_registry_fetch_cached(settings=settings, force=force)
    last_serial = int(registry["families"][family]["last_serial"] or 0)
    next_start = last_serial + 1
    next_end = next_start + max(1, int(count)) - 1
    return next_start, next_end


def _prompt_serial_password(parent):
    value = simpledialog.askstring(
        t("serial_password_title"),
        t("serial_password_prompt"),
        parent=parent,
        show="*",
    )
    if value is None:
        return False
    if value != SERIAL_ADMIN_PASSWORD:
        messagebox.showerror(t("serial_error_title"), t("serial_password_error"), parent=parent)
        return False
    return True


def _ensure_serial_token(parent, settings):
    token = (
        str(settings.get("token", "")).strip()
        or os.environ.get("DEVICE_MANAGER_GITHUB_TOKEN", "").strip()
        or _load_embedded_serial_token()
    )
    if token:
        settings["token"] = token
        return settings
    token = simpledialog.askstring(
        "GitHub token",
        "Inserisci il GitHub token per salvare i seriali su GitHub:",
        parent=parent,
        show="*",
    )
    if token is None:
        return None
    token = token.strip()
    if not token:
        raise ValueError(t("serial_repo_error_missing_token"))
    settings["token"] = token
    return settings


def _prepare_serial_settings_for_write(parent):
    settings = _load_serial_settings()
    ensured = _ensure_serial_token(parent, dict(settings))
    if ensured is None:
        return None
    return ensured


def _notify_registry_update_failure(parent, error):
    messagebox.showwarning(
        t("serial_repo_update_failed_title"),
        t("serial_repo_update_failed_body").format(error=error),
        parent=parent,
    )


def check_for_updates(parent, interactive=True, status_cb=None):
    settings = _load_update_settings()
    manifest_url = str(settings.get("manifest_url", "")).strip()

    if not manifest_url:
        if interactive:
            if status_cb:
                status_cb(t("upd_status_disabled"))
            messagebox.showerror(t("upd_error_title"), t("upd_error_no_url"), parent=parent)
        return False

    if status_cb:
        status_cb(t("upd_status_checking"))
        try:
            parent.update()
        except Exception:
            pass

    try:
        manifest = _download_json(manifest_url)
    except (urlerror.URLError, TimeoutError, ValueError) as exc:
        if status_cb:
            status_cb(t("upd_status_idle"))
        if interactive:
            messagebox.showerror(t("upd_error_title"), t("upd_error_network").format(error=exc), parent=parent)
        return False

    latest_version = str(manifest.get("version", "")).strip()
    download_url = str(manifest.get("url", "")).strip()
    if not latest_version or not download_url:
        if status_cb:
            status_cb(t("upd_status_idle"))
        if interactive:
            messagebox.showerror(t("upd_error_title"), t("upd_error_bad_manifest"), parent=parent)
        return False

    if _parse_version(latest_version) <= _parse_version(APP_VERSION):
        if status_cb:
            status_cb(t("upd_status_latest"))
        if interactive:
            messagebox.showinfo(t("upd_title"), t("upd_status_latest"), parent=parent)
        return False

    if status_cb:
        status_cb(t("upd_status_available").format(version=latest_version))

    if not messagebox.askyesno(
        t("upd_confirm_title"),
        t("upd_confirm_body").format(current=APP_VERSION, latest=latest_version),
        parent=parent,
    ):
        return False

    try:
        target = filedialog.asksaveasfilename(
            parent=parent,
            title=t("upd_download_title"),
            initialfile=os.path.basename(download_url) or f"{APP_BUILD_NAME}_{latest_version}.exe",
            defaultextension=".exe",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if not target:
            return False

        _download_binary(download_url, target)

        if getattr(sys, "frozen", False):
            _launch_windows_downloaded_app(target)
            if status_cb:
                status_cb(t("upd_success_restart"))
            messagebox.showinfo(t("upd_title"), t("upd_success_restart"), parent=parent)
            parent.after(300, parent.destroy)
            return True
        if status_cb:
            status_cb(t("upd_status_available").format(version=latest_version))
        messagebox.showinfo(t("upd_title"), f"{latest_version}\n\n{target}", parent=parent)
        return True
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        if status_cb:
            status_cb(t("upd_status_idle"))
        messagebox.showerror(t("upd_error_title"), t("upd_error_download").format(error=exc), parent=parent)
        return False

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
FIXED_APP_EUI = "665544332211AABB"
FIXED_AUTH    = "ABP"
FIXED_CLASS   = "A"
FIXED_GROUP   = "_addon_hydronet_valve"

def _resource_path(rel):
    try:
        base = sys._MEIPASS
    except Exception:
        base = os.path.abspath(".")
    return os.path.join(base, rel)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PDF â€“ sin cambios
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _make_qr_image(data):
    import qrcode
    from io import BytesIO
    from reportlab.lib.utils import ImageReader
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return ImageReader(buf)


def _make_pdf(devices, output_path, include_bluetooth=True, rtu_header=False, loraconta=False):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.units import mm
    except ImportError:
        raise ImportError("La librerÃ­a 'reportlab' no estÃ¡ instalada.\nEjecuta:  pip install reportlab")

    PW, PH = A4
    ML = 6*mm; MR = 6*mm; MT = 4*mm; MB = 4*mm
    N_COLS = 2; COL_GAP = 2
    AW = PW-ML-MR; AH = PH-MT-MB
    GAP_V = 1*mm

    if loraconta:
        rtu_header = True; include_bluetooth = False
        LW = 87*mm; LH = 23*mm; N_LR = 6
        layout_rows = max(1, int(AH/(LH+GAP_V)))
        N_ROWS = max(1, layout_rows - 1)
        SLOT_H = LH+GAP_V; ROW_H = LH/N_LR; HEADER_H = 3*ROW_H
        ML = (PW - N_COLS*LW - (N_COLS-1)*COL_GAP) / 2
        grid_h = N_ROWS * LH + max(0, N_ROWS - 1) * GAP_V
        grid_top = PH - MT - max(0, (AH - grid_h) / 2.0)
    else:
        LW = (AW-COL_GAP)/N_COLS
        if rtu_header:
            include_bluetooth = False
        N_LR = 6 if rtu_header else (4 if include_bluetooth else 3)
        MIN_ROW_H = 5.0*mm
        LH_min = N_LR*MIN_ROW_H
        max_rows = max(1, int(AH/(LH_min+GAP_V)))
        if include_bluetooth or not rtu_header or rtu_header:
            layout_rows = max_rows
            N_ROWS = max(1, max_rows - 1)
            SLOT_H = AH/layout_rows
            LH = SLOT_H-GAP_V
            grid_h = N_ROWS * LH + max(0, N_ROWS - 1) * GAP_V
            grid_top = PH - MT - max(0, (AH - grid_h) / 2.0)
        ROW_H = LH/N_LR; HEADER_H = 3*ROW_H if rtu_header else 0

    HDR_TITLE = "LORACONT - RTU" if loraconta else "HYDRONET - RTU"
    R1 = R2 = R3 = ROW_H
    R4 = ROW_H if include_bluetooth else 0

    if rtu_header:
        CL = LW*0.220; CV = LW*0.345; CN = LW*0.435
    else:
        CL = LW*0.200; CV = LW*0.295; CN = LW*0.505
    CN_NAME = CN*0.630; CN_QR = CN*0.370

    FS_L=6.0; FS_NM=6.0; FS_SN=8.0; FS_DE=8.0
    FS_DA=8.0; FS_N=12.0; FS_BT=10.0; PAD=2.5

    black_logo_reader = _make_black_logo_reader()
    qr_images = [_make_qr_image(dev['dev_eui']) for dev in devices]
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    PER_PAGE = N_ROWS*N_COLS

    for idx, dev in enumerate(devices):
        if idx > 0 and idx % PER_PAGE == 0:
            c.showPage()
        pos = idx % PER_PAGE
        ri = pos // N_COLS; ci = pos % N_COLS
        lx = ML + ci*(LW+COL_GAP)
        slot_top = grid_top-ri*SLOT_H; ly = slot_top-LH

        serial=dev['serial']; name=dev['name']
        dev_eui=dev['dev_eui']; dev_addr=dev['dev_addr']
        bt_text=f"TECNIDROBT{dev_addr}"

        if include_bluetooth:
            bt_bot=ly; da_bot=ly+R4; de_bot=ly+R4+R3; sn_bot=ly+R4+R3+R2
        else:
            da_bot=ly; de_bot=ly+R3; sn_bot=ly+R3+R2

        top=ly+LH; hdr_bot=top-HEADER_H; content_top=hdr_bot
        xv=lx+CL; xn=xv+CV; xqr=xn+CN_NAME; xe=lx+LW

        c.setStrokeColorRGB(0,0,0); c.setLineWidth(0.8)
        c.rect(lx, ly, LW, LH)

        if rtu_header:
            HDR_LOGO_W=CL; HDR_TEXT_W=LW-HDR_LOGO_W
            logo_x0=lx; text_cx=lx+HDR_LOGO_W+HDR_TEXT_W/2
            c.setLineWidth(0.5); c.line(xv, hdr_bot, xv, top)
            if black_logo_reader:
                logo_pad=3.0
                c.drawImage(black_logo_reader, logo_x0+logo_pad, hdr_bot+logo_pad,
                            HDR_LOGO_W-2*logo_pad, HEADER_H-2*logo_pad,
                            mask='auto', preserveAspectRatio=True, anchor='c')
            fs_rtu_title=HEADER_H*0.32
            c.setFont("Helvetica-Bold", fs_rtu_title)
            c.drawCentredString(text_cx, hdr_bot+HEADER_H*0.63, HDR_TITLE)
            fs_rtu_sub=HEADER_H*0.22
            c.setFont("Helvetica", fs_rtu_sub)
            c.drawCentredString(text_cx, hdr_bot+HEADER_H*0.38, "TECNIDRO srl - GENOVA")
            fs_rtu_web=HEADER_H*0.18
            c.setFont("Helvetica", fs_rtu_web)
            c.drawCentredString(text_cx, hdr_bot+HEADER_H*0.14, "w w w . t e c n i d r o . c o m")

        cn_bot = da_bot if include_bluetooth else ly
        c.setLineWidth(0.5)
        c.line(lx, sn_bot, xn, sn_bot)
        c.line(lx, de_bot, xn, de_bot)
        if include_bluetooth: c.line(lx, da_bot, xe, da_bot)
        if rtu_header: c.line(lx, hdr_bot, xe, hdr_bot)
        c.line(xv, ly, xv, content_top)
        c.line(xn, cn_bot, xn, content_top)
        c.line(xqr, cn_bot, xqr, content_top)

        def vy(rb, rh, fs): return rb+(rh-fs)/2.0
        def lbl(tx, rb, rh):
            c.setFont("Helvetica", FS_L)
            c.drawCentredString(lx+CL/2, vy(rb,rh,FS_L), tx)
        def val_c(tx, cx, cw, rb, rh, fs):
            c.setFont("Helvetica-Bold", fs)
            c.drawCentredString(cx+cw/2, vy(rb,rh,fs), tx)

        lbl("SERIAL N.", sn_bot, R1)
        val_c(serial, xv, CV, sn_bot, R1, FS_SN)
        c.setFont("Helvetica", FS_NM)
        c.drawString(xn+PAD, vy(sn_bot, R1, FS_NM), "name:")
        lbl("DEVICE EUI", de_bot, R2)
        val_c(dev_eui, xv, CV, de_bot, R2, FS_DE)
        lbl("DEVADDR", da_bot, R3)
        val_c(dev_addr, xv, CV, da_bot, R3, FS_DA)

        name_area_bot=da_bot; name_area_h=R2+R3
        max_name_w=CN_NAME-2*PAD; fs_name=FS_N
        c.setFont("Helvetica-Bold", fs_name)
        while fs_name > 4 and c.stringWidth(name,"Helvetica-Bold",fs_name) > max_name_w:
            fs_name -= 0.5; c.setFont("Helvetica-Bold", fs_name)
        c.drawCentredString(xn+CN_NAME/2, name_area_bot+(name_area_h-fs_name)/2.0, name)

        qr_area_h=content_top-cn_bot
        qr_size=min(CN_QR, qr_area_h)-4
        qr_x=xqr+(CN_QR-qr_size)/2; qr_y=cn_bot+(qr_area_h-qr_size)/2
        c.drawImage(qr_images[idx], qr_x, qr_y, qr_size, qr_size, mask='auto')

        if include_bluetooth:
            lbl("BLUETOOTH", bt_bot, R4)
            val_c(bt_text, xv, CV+CN, bt_bot, R4, FS_BT)

    c.save()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# GUI helpers
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
LBL_W = 200

# Paleta premium
# Light C: Cool Pearl Gray + Slate Blue
# Dark 1: Dark Slate Blue
C_APP_BG       = ("#eef2f6", "#0f1622")
C_SHELL_BG     = ("#f5f7fa", "#223147")
C_BODY_BG      = ("#f5f7fa", "#223147")
C_CARD_BG      = ("#ffffff", "#2b3c55")
C_CARD_ALT     = ("#e8edf3", "#314663")
C_CARD_BORDER  = ("#c9d3df", "#4d6686")
C_TEXT         = ("#223245", "#f3f8ff")
C_MUTED        = ("#6b7a8c", "#bed0e4")
C_ACCENT       = ("#54779b", "#8ab6ea")
C_ACCENT_HOVER = ("#456783", "#74a2da")
C_ACCENT_SOFT  = ("#dbe5ef", "#38526f")
C_SEC_BG       = ("#e6ecf3", "#314866")
C_SEC_TEXT     = ("#314a67", "#eef5ff")
C_HINT         = ("#78879a", "#bdd0e5")
C_STATUS       = ("#54779b", "#acd0ff")
C_HDR_BG       = ("#e9eef4", "#1d2b3f")
C_HDR_TEXT     = ("#223245", "#f7fbff")
C_BAR_BG       = ("#e3e9f0", "#1a2637")
C_BAR_TEXT     = ("#66778c", "#b0c3d8")
C_DIV          = ("#d2dbe6", "#47607e")
C_TAB_BG       = ("#e3e9f0", "#26384f")
C_TAB_TEXT     = ("#3f5874", "#ebf4ff")


def _sec(parent, key, refs=None):
    """Barra de secciÃ³n."""
    f = ctk.CTkFrame(parent, fg_color=C_SEC_BG, corner_radius=14, height=34, border_width=1, border_color=C_CARD_BORDER)
    f.pack(fill="x", padx=10, pady=(16, 6))
    f.pack_propagate(False)
    lbl = ctk.CTkLabel(f, text=t(key),
                       font=ctk.CTkFont(size=11, weight="bold"),
                       text_color=C_SEC_TEXT)
    lbl.pack(side="left", padx=14)
    if refs is not None:
        refs[f'_sec_{key}'] = lbl
    return lbl


def _div(parent):
    ctk.CTkFrame(parent, height=1, fg_color=C_DIV).pack(fill="x", padx=14, pady=(18, 10))


def _row(parent, pady=3):
    f = ctk.CTkFrame(
        parent,
        fg_color=C_CARD_BG,
        corner_radius=14,
        border_width=1,
        border_color=C_CARD_BORDER,
    )
    f.pack(fill="x", padx=14, pady=max(pady, 4))
    return f


def _style_tabview(tabview, nested=False):
    try:
        tabview.configure(
            fg_color="transparent",
            segmented_button_fg_color=C_TAB_BG,
            segmented_button_selected_color=C_ACCENT,
            segmented_button_selected_hover_color=C_ACCENT_HOVER,
            segmented_button_unselected_color=C_TAB_BG,
            segmented_button_unselected_hover_color=C_ACCENT_SOFT,
            text_color=C_TAB_TEXT,
            corner_radius=18 if not nested else 14,
            border_width=0,
        )
    except Exception:
        pass


def _apply_premium_theme(widget):
    try:
        if getattr(widget, "_dm_style_locked", False):
            pass
        if isinstance(widget, ctk.CTkScrollableFrame):
            widget.configure(fg_color="transparent")
        elif isinstance(widget, ctk.CTkTabview):
            _style_tabview(widget, nested=False)
        elif isinstance(widget, ctk.CTkEntry):
            widget.configure(
                fg_color=C_CARD_ALT,
                border_color=C_CARD_BORDER,
                text_color=C_TEXT,
                corner_radius=12,
                border_width=1,
                height=36,
            )
        elif isinstance(widget, ctk.CTkTextbox):
            widget.configure(
                fg_color=C_CARD_ALT,
                border_color=C_CARD_BORDER,
                text_color=C_TEXT,
                corner_radius=12,
                border_width=1,
            )
        elif isinstance(widget, ctk.CTkOptionMenu):
            widget.configure(
                fg_color=C_CARD_ALT,
                button_color=C_ACCENT,
                button_hover_color=C_ACCENT_HOVER,
                text_color=C_TEXT,
                corner_radius=12,
            )
        elif isinstance(widget, ctk.CTkButton):
            if getattr(widget, "_dm_style_locked", False):
                return
            text = str(widget.cget("text") or "")
            if text == "...":
                widget.configure(
                    fg_color=C_ACCENT_SOFT,
                    hover_color=("#cfdae7", "#28425d"),
                    text_color=C_SEC_TEXT,
                    corner_radius=12,
                    border_width=0,
                )
            else:
                widget.configure(
                    fg_color=C_ACCENT,
                    hover_color=C_ACCENT_HOVER,
                    text_color=("white", "#f7fbff"),
                    corner_radius=14,
                    border_width=0,
                )
        elif isinstance(widget, ctk.CTkRadioButton):
            widget.configure(
                fg_color=C_ACCENT,
                hover_color=C_ACCENT_HOVER,
                border_color=C_CARD_BORDER,
                text_color=C_TEXT,
            )
        elif isinstance(widget, tk.Listbox):
            widget.configure(
                bg="#fffdfa",
                fg="#1d2430",
                selectbackground="#2f5c88",
                selectforeground="white",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#d8cfc3",
                bd=0,
            )
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _apply_premium_theme(child)
    except Exception:
        pass


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab 1: CSV
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class CSVTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C_BODY_BG,
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        lbl_title = ctk.CTkLabel(self, text=t('csv_title'),
                                  font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(12, 6))
        self._refs['csv_title'] = lbl_title

        # â”€â”€ Nombre â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_name', self._refs)
        self._frow('lbl_prefix', "CBG_",  "name_prefix",  w=130)
        self._frow('lbl_from',   "1201",  "start_number", w=100)
        self._frow('lbl_to',     "1220",  "end_number",   w=100)

        # Preview (sin textvariable â€” se actualiza con trace)
        self._preview_lbl = ctk.CTkLabel(self, text="",
                                          text_color=C_HINT,
                                          font=ctk.CTkFont(size=10))
        self._preview_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        for v in (self.name_prefix_var, self.start_number_var, self.end_number_var):
            v.trace_add("write", self._update_preview)
        self._update_preview()

        # â”€â”€ LoRa â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_lora', self._refs)
        self._frow('lbl_model',   "210",                              "model")
        self._frow('lbl_deveui',  "512345678B1904B1",                 "start_dev_eui")
        self._hint_da = ctk.CTkLabel(self, text=t('lbl_devaddr_i'),
                                      text_color=C_HINT,
                                      font=ctk.CTkFont(size=10, slant="italic"))
        self._hint_da.pack(anchor="w", padx=18, pady=(0, 4))
        self._refs['lbl_devaddr_i'] = self._hint_da
        self._frow('lbl_newskey', "0123456789ABCDEF0123456789ABCDEF", "new_skey")
        self._frow('lbl_appskey', "0123456789ABCDEF0123456789ABCDEF", "app_skey")

        # â”€â”€ Coordenadas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_coords', self._refs)
        r = _row(self)
        lbl_lat = ctk.CTkLabel(r, text=t('lbl_lat'), width=LBL_W, anchor="w")
        lbl_lat.pack(side="left")
        self._refs['lbl_lat'] = lbl_lat
        self.latitude_var = tk.StringVar()
        ctk.CTkEntry(r, textvariable=self.latitude_var, width=150).pack(side="left", padx=(4, 18))
        lbl_lon = ctk.CTkLabel(r, text=t('lbl_lon'), width=80, anchor="w")
        lbl_lon.pack(side="left")
        self._refs['lbl_lon'] = lbl_lon
        self.longitude_var = tk.StringVar()
        ctk.CTkEntry(r, textvariable=self.longitude_var, width=150).pack(side="left", padx=4)

        # â”€â”€ Extra â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_extra', self._refs)
        re = _row(self)
        lbl_childnumber = ctk.CTkLabel(re, text=t('lbl_childnumber'), width=LBL_W, anchor="w")
        lbl_childnumber.pack(side="left")
        self._refs['lbl_childnumber'] = lbl_childnumber
        self.childnumber_var = tk.StringVar(value="1")
        ctk.CTkEntry(re, textvariable=self.childnumber_var, width=100).pack(side="left", padx=(4, 18))
        ctk.CTkLabel(re, text="devStatusReqInterval:", width=170, anchor="w").pack(side="left")
        self.devstatusreqinterval_var = tk.StringVar(value="0")
        ctk.CTkEntry(re, textvariable=self.devstatusreqinterval_var, width=80).pack(side="left", padx=4)
        # â”€â”€ Output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _div(self)
        ro = _row(self)
        lbl_out = ctk.CTkLabel(ro, text=t('lbl_out_file'), width=LBL_W, anchor="w")
        lbl_out.pack(side="left")
        self._refs['lbl_out_file'] = lbl_out
        self.csv_output_var = tk.StringVar()
        ctk.CTkEntry(ro, textvariable=self.csv_output_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(ro, text="...", width=36, command=self._browse_csv).pack(side="left")

        btn = ctk.CTkButton(self, text=t('btn_gen_csv'), command=self._generate,
                             height=44, font=ctk.CTkFont(size=13, weight="bold"))
        btn.pack(pady=(16, 16), padx=30, fill="x")
        self._refs['btn_gen_csv'] = btn

    # â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _frow(self, key, default, attr, w=None):
        r = _row(self)
        lbl = ctk.CTkLabel(r, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._refs[key] = lbl
        var = tk.StringVar(value=default)
        setattr(self, f"{attr}_var", var)
        if w:
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkEntry(r, textvariable=var).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _refresh_lang(self):
        for key, w in self._refs.items():
            w.configure(text=t(key[5:]) if key.startswith('_sec_') else t(key))
        self._update_preview()

    def _update_preview(self, *_):
        try:
            prefix = self.name_prefix_var.get()
            start  = int(self.start_number_var.get())
            end    = int(self.end_number_var.get())
            count  = end - start + 1
            wd     = len(self.start_number_var.get())
            if count > 0:
                txt = t('prev_fmt').format(n=count, a=f"{prefix}{start:0{wd}d}", b=f"{prefix}{end:0{wd}d}")
            else:
                txt = t('prev_error')
        except ValueError:
            txt = ""
        self._preview_lbl.configure(text=txt)

    def _browse_csv(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files","*.csv"),("All files","*.*")],
            title="Guardar CSV como...")
        if p: self.csv_output_var.set(p)

    def _generate(self):
        try:
            prefix       = self.name_prefix_var.get().strip()
            start_raw    = self.start_number_var.get().strip()
            start        = int(start_raw); num_width = len(start_raw)
            end          = int(self.end_number_var.get().strip())
            model        = self.model_var.get().strip()
            start_deveui = self.start_dev_eui_var.get().strip().upper()
            new_skey     = self.new_skey_var.get().strip().upper()
            app_skey     = self.app_skey_var.get().strip().upper()
            latitude     = self.latitude_var.get().strip()
            longitude    = self.longitude_var.get().strip()
            childnumber  = self.childnumber_var.get().strip()
            devstatusreq = self.devstatusreqinterval_var.get().strip()
            tag          = ""
            alias        = ""
            output_file  = self.csv_output_var.get().strip()

            if not output_file: messagebox.showerror("Error","Selecciona un archivo de salida."); return
            num_devices = end-start+1
            if num_devices <= 0: messagebox.showerror("Error","'Hasta' debe ser â‰¥ 'Desde'."); return
            if not childnumber.isdigit(): messagebox.showerror("Error","La cantidad de valvulas / childnumber debe ser numerica."); return
            if len(start_deveui) != 16: messagebox.showerror("Error",f"DevEUI debe tener 16 hex (tiene {len(start_deveui)})."); return
            int(start_deveui, 16)
            if len(new_skey) != 32: messagebox.showerror("Error",f"NewSKey debe tener 32 hex."); return
            if len(app_skey) != 32: messagebox.showerror("Error",f"AppSKey debe tener 32 hex."); return

            deveui_int = int(start_deveui, 16)
            header = ["Name","Model","AppEUI","DevEUI","Auth","AppKey","DevAddr",
                      "NewSKey","AppSKey","Class","Latitude","Longitude","Tag",
                      "MultiTag","Alias","Group","ParentAppEUI","ParentDevEUI",
                      "childnumber","devStatusReqInterval"]
            rows = []
            for i in range(num_devices):
                nm = f"{prefix}{start+i:0{num_width}d}"
                de = format(deveui_int+i,"016X"); da = de[-8:]
                rows.append([nm,model,FIXED_APP_EUI,de,FIXED_AUTH,"",da,
                              new_skey,app_skey,FIXED_CLASS,latitude,longitude,tag,
                              "",alias,FIXED_GROUP,"","",childnumber,devstatusreq])
            with open(output_file,"w",newline="",encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";"); w.writerow(header); w.writerows(rows)
            messagebox.showinfo("Ã‰xito",
                f"CSV generado correctamente.\n\n"
                f"  Dispositivos: {num_devices}\n"
                f"  DevEUI desde: {start_deveui}\n"
                f"  DevEUI hasta: {format(deveui_int+num_devices-1,'016X')}\n\n"
                f"Archivo:\n{output_file}")
        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numÃ©ricos/hex.\n\nDetalle: {e}")
        except PermissionError:
            messagebox.showerror("Error de permisos","No se pudo escribir el archivo.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab 2: Etichette PDF
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class EtichetteTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C_BODY_BG,
                         corner_radius=0, border_width=0, label_text="")
        self._devices = []
        self._refs    = {}
        self._pdf_output_auto = True
        self._last_auto_pdf_path = ""
        self._build()
        _lang_cbs.append(self._refresh_lang)
        _register_serial_refresh_callback(self._handle_serial_registry_changed)

    def _build(self):
        lbl_title = ctk.CTkLabel(self, text=t('labels_title'),
                                  font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(12, 6))
        self._refs['labels_title'] = lbl_title

        # â”€â”€ OpciÃ³n 1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_opt1', self._refs)
        r1 = _row(self)
        lbl_cf = ctk.CTkLabel(r1, text=t('lbl_csv_file'), width=LBL_W, anchor="w")
        lbl_cf.pack(side="left")
        self._refs['lbl_csv_file'] = lbl_cf
        self.csv_input_var = tk.StringVar()
        ctk.CTkEntry(r1, textvariable=self.csv_input_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="...", width=36, command=self._browse_csv_in).pack(side="left", padx=(0,4))
        btn_load = ctk.CTkButton(r1, text=t('btn_load'), width=80, command=self._load_csv)
        btn_load.pack(side="left")
        self._refs['btn_load'] = btn_load

        # Status CSV (sin textvariable)
        self._csv_status_lbl = ctk.CTkLabel(self, text="",
                                             text_color=C_STATUS,
                                             font=ctk.CTkFont(size=10))
        self._csv_status_lbl.pack(anchor="w", padx=18, pady=(2, 4))

        # â”€â”€ OpciÃ³n 2 â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_opt2', self._refs)
        self._frow('lbl_name_pfx', "CBG_",            "m_prefix", w=130)
        self._frow('lbl_from',     "1201",             "m_from",   w=100)
        self._frow('lbl_to',       "1220",             "m_to",     w=100)
        self._frow('lbl_deveui_m', "512345678B1904B1", "m_deveui")

        # â”€â”€ Serial â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_serial', self._refs)
        rs = _row(self)
        lbl_ss = ctk.CTkLabel(rs, text=t('lbl_ser_start'), width=LBL_W, anchor="w")
        lbl_ss.pack(side="left")
        self._refs['lbl_ser_start'] = lbl_ss
        self.serial_start_var = tk.StringVar(value="04906")
        ctk.CTkEntry(rs, textvariable=self.serial_start_var, width=120).pack(side="left", padx=(4,18))
        lbl_yr = ctk.CTkLabel(rs, text=t('lbl_year'), width=80, anchor="w")
        lbl_yr.pack(side="left")
        self._refs['lbl_year'] = lbl_yr
        self.serial_year_var = tk.StringVar(value="2026")
        ctk.CTkEntry(rs, textvariable=self.serial_year_var, width=80).pack(side="left", padx=4)

        self._hint_sf = ctk.CTkLabel(self, text=t('lbl_ser_fmt'),
                                      text_color=C_HINT,
                                      font=ctk.CTkFont(size=10, slant="italic"))
        self._hint_sf.pack(anchor="w", padx=18, pady=(0, 4))
        self._refs['lbl_ser_fmt'] = self._hint_sf

        # â”€â”€ Opciones â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_opts', self._refs)

        # Una sola variable â€” 4 opciones mutuamente exclusivas
        self.label_type_var = tk.StringVar(value="nortu")

        OPTS = [
            ("nortu",    "RTU NO BLTE"),
            ("blte",     "RTU BLTE"),
            ("tubo",     "RTU TUBO"),
            ("loracont", "RTU LORACONT"),
        ]
        for val, label in OPTS:
            ctk.CTkRadioButton(
                self,
                text=label,
                variable=self.label_type_var,
                value=val,
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", padx=28, pady=6)

        # â”€â”€ Output â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _div(self)
        rpo = _row(self)
        lbl_po = ctk.CTkLabel(rpo, text=t('lbl_pdf_out'), width=LBL_W, anchor="w")
        lbl_po.pack(side="left")
        self._refs['lbl_pdf_out'] = lbl_po
        self.pdf_output_var = tk.StringVar()
        ctk.CTkEntry(rpo, textvariable=self.pdf_output_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(rpo, text="...", width=36, command=self._browse_pdf).pack(side="left")

        btn_pdf = ctk.CTkButton(self, text=t('btn_gen_pdf'), command=self._generate_pdf,
                                 height=44, font=ctk.CTkFont(size=13, weight="bold"))
        btn_pdf.pack(pady=(16, 6), padx=30, fill="x")
        self._refs['btn_gen_pdf'] = btn_pdf

        # Status PDF (sin textvariable)
        self._pdf_status_lbl = ctk.CTkLabel(self, text=t('lbl_ready'),
                                             text_color=C_HINT,
                                             font=ctk.CTkFont(size=10))
        self._pdf_status_lbl.pack(anchor="w", padx=18, pady=(0, 14))
        for var in (self.m_from_var, self.m_to_var, self.serial_start_var, self.label_type_var):
            var.trace_add("write", self._update_auto_pdf_output)
        self._update_auto_pdf_output()
        self.after(150, self._use_next_serial_from_github)

    # â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _frow(self, key, default, attr, w=None):
        r = _row(self)
        lbl = ctk.CTkLabel(r, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._refs[key] = lbl
        var = tk.StringVar(value=default)
        setattr(self, f"{attr}_var", var)
        if w:
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkEntry(r, textvariable=var).pack(side="left", fill="x", expand=True, padx=(4, 0))

    def _refresh_lang(self):
        for key, w in self._refs.items():
            w.configure(text=t(key[5:]) if key.startswith('_sec_') else t(key))
        self._pdf_status_lbl.configure(text=t('lbl_ready'))

    def _browse_csv_in(self):
        p = filedialog.askopenfilename(
            filetypes=[("CSV files","*.csv"),("All files","*.*")],
            title="Abrir CSV de dispositivos")
        if p: self.csv_input_var.set(p)

    def _browse_pdf(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files","*.pdf"),("All files","*.*")],
            title="Guardar PDF como...")
        if p:
            self.pdf_output_var.set(p)
            self._pdf_output_auto = False

    def _suggest_pdf_output_path(self):
        try:
            count = len(self._devices) if self._devices else (int(self.m_to_var.get().strip()) - int(self.m_from_var.get().strip()) + 1)
            if count <= 0:
                return ""
            start_raw = self.serial_start_var.get().strip()
            width = max(len(start_raw), SERIAL_FAMILY_SETTINGS["RTU"]["number_width"])
            start_num = int(start_raw)
            end_num = start_num + count - 1
            start_value = f"{start_num:0{width}d}"
            end_value = f"{end_num:0{width}d}"
            label_name = {
                "nortu": "RTU",
                "blte": "RTU BLTE",
                "tubo": "RTU TUBO",
                "loracont": "RTU LORACONT",
            }.get(self.label_type_var.get(), "RTU")
            return _default_label_pdf_path(label_name, start_value, end_value)
        except Exception:
            return ""

    def _update_auto_pdf_output(self, *_):
        suggested = self._suggest_pdf_output_path()
        current = self.pdf_output_var.get().strip()
        if suggested and (self._pdf_output_auto or not current or current == self._last_auto_pdf_path):
            self.pdf_output_var.set(suggested)
            self._pdf_output_auto = True
        if suggested:
            self._last_auto_pdf_path = suggested

    def _handle_serial_registry_changed(self):
        self.after(0, self._use_next_serial_from_github)

    def _load_csv(self):
        path = self.csv_input_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error","Selecciona un archivo CSV vÃ¡lido."); return
        try:
            devices = []
            with open(path,"r",encoding="utf-8") as f:
                reader = csv.reader(f, delimiter=";")
                header = next(reader); h = [x.strip() for x in header]
                for row in reader:
                    if not row or not row[0].strip(): continue
                    d = dict(zip(h,row))
                    devices.append({'name': d.get('Name','').strip(),
                                    'dev_eui': d.get('DevEUI','').strip(),
                                    'dev_addr': d.get('DevAddr','').strip()})
            self._devices = devices
            self._csv_status_lbl.configure(text=f"  âœ“  {len(devices)} dispositivos cargados desde CSV.")
            if devices:
                fn = devices[0]['name']; ln = devices[-1]['name']
                np = ''.join(c for c in fn if c.isdigit())
                pp = fn[:len(fn)-len(np)]
                if np:
                    self.m_prefix_var.set(pp); self.m_from_var.set(np)
                    ln2 = ''.join(c for c in ln if c.isdigit())
                    if ln2: self.m_to_var.set(ln2)
                self.m_deveui_var.set(devices[0]['dev_eui'])
            self._update_auto_pdf_output()
        except Exception as e:
            messagebox.showerror("Error al leer CSV", str(e))

    def _build_devices_manual(self):
        prefix = self.m_prefix_var.get().strip()
        sr = self.m_from_var.get().strip(); start = int(sr); nw = len(sr)
        end = int(self.m_to_var.get().strip())
        ds = self.m_deveui_var.get().strip().upper()
        if len(ds) != 16: raise ValueError(f"DevEUI debe tener 16 hex (tiene {len(ds)}).")
        int(ds, 16); di = int(ds,16); n = end-start+1
        if n <= 0: raise ValueError("'Hasta' debe ser â‰¥ 'Desde'.")
        devs = []
        for i in range(n):
            nm = f"{prefix}{start+i:0{nw}d}"; de = format(di+i,"016X"); da = de[-8:]
            devs.append({'name':nm,'dev_eui':de,'dev_addr':da})
        return devs

    def _use_next_serial_from_github(self):
        try:
            base_devices = self._devices if self._devices else self._build_devices_manual()
            count = len(base_devices)
            if count <= 0:
                return
            next_start, _ = _next_available_serial("RTU", count=count, settings=_load_serial_settings())
            width = max(len(self.serial_start_var.get().strip()), SERIAL_FAMILY_SETTINGS["RTU"]["number_width"])
            self.serial_start_var.set(f"{next_start:0{width}d}")
            self._update_auto_pdf_output()
            self._pdf_status_lbl.configure(
                text=t("serial_next_status").format(
                    family=_serial_family_name("RTU"),
                    value=f"{next_start:0{width}d}",
                )
            )
        except Exception as exc:
            self._pdf_status_lbl.configure(text=str(exc))

    def _generate_pdf(self):
        try:
            ssr = self.serial_start_var.get().strip()
            sy  = self.serial_year_var.get().strip()
            of  = self.pdf_output_var.get().strip()
            if not of:
                self._update_auto_pdf_output()
                of = self.pdf_output_var.get().strip()
            if not of: messagebox.showerror("Error","Selecciona un archivo PDF de salida."); return
            bd = self._devices if self._devices else self._build_devices_manual()
            if not bd: messagebox.showerror("Error","No hay dispositivos."); return
            sw = len(ssr); ss = int(ssr)

            devices = []
            for i, dev in enumerate(bd):
                sn = format(ss+i,f"0{sw}d")
                devices.append({'serial':f"{sn}/{sy}",'name':dev['name'],
                                'dev_eui':dev['dev_eui'],'dev_addr':dev['dev_addr']})
            opt = self.label_type_var.get()
            include_bluetooth = (opt == "blte")
            rtu_header        = (opt == "tubo")
            loraconta         = (opt == "loracont")

            self._pdf_status_lbl.configure(text="Generando PDFâ€¦")
            self.update()
            _make_pdf(devices, of,
                      include_bluetooth=include_bluetooth,
                      rtu_header=rtu_header,
                      loraconta=loraconta)
            settings = _prepare_serial_settings_for_write(self)
            if settings is None:
                return
            self._pdf_status_lbl.configure(text=t("serial_repo_sync_after_generate"))
            self.update()
            try:
                _serial_registry_update_last(settings, "RTU", ss, ss + len(bd) - 1, sy, len(bd))
            except Exception as exc:
                self._pdf_status_lbl.configure(text=str(exc))
                _notify_registry_update_failure(self, exc)
                return
            n = len(devices)
            self._pdf_status_lbl.configure(text=t("serial_repo_reserved").format(
                family=_serial_family_name("RTU"),
                start=devices[0]['serial'].split('/')[0],
                end=devices[-1]['serial'].split('/')[0],
                year=sy,
            ))
            _notify_serial_registry_changed()
            messagebox.showinfo("Ã‰xito",
                f"PDF generado correctamente.\n\n"
                f"  Etiquetas:  {n}\n"
                f"  Primera:    {devices[0]['name']}  |  {devices[0]['serial']}\n"
                f"  Ãšltima:     {devices[-1]['name']}  |  {devices[-1]['serial']}\n\n"
                f"Archivo:\n{of}")
        except ValueError as e:
            messagebox.showerror("Error de valor", str(e))
        except ImportError as e:
            messagebox.showerror("LibrerÃ­a faltante", str(e))
        except PermissionError:
            messagebox.showerror("Error de permisos","No se pudo escribir el PDF.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab 3: Idioma + Tema
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class LangTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C_BODY_BG)
        self._is_dark = True
        self._update_settings = _load_update_settings()
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        # Centrado vertical con spacer
        ctk.CTkFrame(self, fg_color="transparent", height=50).pack()

        self._lbl_title = ctk.CTkLabel(self, text=t('lang_title'),
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self._lbl_title.pack(pady=(0, 6))

        self._lbl_sub = ctk.CTkLabel(self, text=t('lang_sub'),
                                      font=ctk.CTkFont(size=12),
                                      text_color=C_HINT)
        self._lbl_sub.pack(pady=(0, 20))

        # Selector de idioma
        self._lang_seg = ctk.CTkSegmentedButton(
            self,
            values=["ES Espanol", "EN English", "IT Italiano"],
            command=self._on_lang,
            font=ctk.CTkFont(size=13),
            height=44, width=420,
        )
        self._lang_seg.set({"es": "ES Espanol", "en": "EN English", "it": "IT Italiano"}.get(_cur_lang[0], "IT Italiano"))
        self._lang_seg.pack(pady=(0, 40))

        # Divisor
        ctk.CTkFrame(self, height=1, fg_color=C_DIV, width=420).pack(pady=(0, 28))

        # Tema
        self._lbl_theme = ctk.CTkLabel(self, text=t('theme_label'),
                                        font=ctk.CTkFont(size=12),
                                        text_color=C_HINT)
        self._lbl_theme.pack(pady=(0, 14))

        # Botones dark / light como segmented button
        self._theme_seg = ctk.CTkSegmentedButton(
            self,
            values=[t('theme_dark'), t('theme_light')],
            command=self._on_theme,
            font=ctk.CTkFont(size=13),
            height=42, width=300,
        )
        self._theme_seg.set(t('theme_dark'))
        self._theme_seg.pack()

        ctk.CTkFrame(self, height=1, fg_color=C_DIV, width=420).pack(pady=(28, 22))

        self._lbl_upd_title = ctk.CTkLabel(self, text=t('upd_title'),
                                           font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_upd_title.pack(pady=(0, 8))

        self._lbl_upd_ver = ctk.CTkLabel(self, text=f"{t('upd_version')} {APP_VERSION}",
                                         font=ctk.CTkFont(size=12),
                                         text_color=C_HINT)
        self._lbl_upd_ver.pack(pady=(0, 10))

        upd_row = ctk.CTkFrame(self, fg_color="transparent")
        upd_row.pack(fill="x", padx=24, pady=(0, 8))
        self._lbl_upd_source = ctk.CTkLabel(upd_row, text=t('upd_source'), width=150, anchor="w")
        self._lbl_upd_source.pack(side="left")
        self._upd_url_var = tk.StringVar(value=str(self._update_settings.get("manifest_url", "")))
        ctk.CTkEntry(upd_row, textvariable=self._upd_url_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        self._upd_auto_var = tk.BooleanVar(value=bool(self._update_settings.get("auto_check", True)))
        self._chk_upd_auto = ctk.CTkCheckBox(self, text=t('upd_auto'), variable=self._upd_auto_var)
        self._chk_upd_auto.pack(pady=(0, 14))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 8))
        self._btn_upd_save = ctk.CTkButton(btn_row, text=t('upd_save'), width=170, command=self._save_update_settings)
        self._btn_upd_save.pack(side="left")
        self._btn_upd_check = ctk.CTkButton(btn_row, text=t('upd_check'), width=190, command=self._check_updates)
        self._btn_upd_check.pack(side="left", padx=(12, 0))

        self._lbl_upd_status = ctk.CTkLabel(self, text=t('upd_status_idle'),
                                            font=ctk.CTkFont(size=11),
                                            text_color=C_HINT,
                                            justify="center",
                                            wraplength=700)
        self._lbl_upd_status.pack(pady=(4, 0))

    def _on_lang(self, value):
        code_map = {"ES Espanol": "es", "EN English": "en", "IT Italiano": "it"}
        set_lang(code_map.get(value, "es"))
        # Actualizar el theme segmented button con los textos del nuevo idioma,
        # preservando la selecciÃ³n actual
        cur = "dark" if self._is_dark else "light"
        new_vals = [t('theme_dark'), t('theme_light')]
        self._theme_seg.configure(values=new_vals)
        self._theme_seg.set(new_vals[0] if cur == "dark" else new_vals[1])

    def _on_theme(self, value):
        dark_text = t('theme_dark')
        self._is_dark = (value == dark_text)
        ctk.set_appearance_mode("dark" if self._is_dark else "light")

    def _set_update_status(self, text):
        self._lbl_upd_status.configure(text=text)

    def _save_update_settings(self):
        self._update_settings = {
            "manifest_url": self._upd_url_var.get().strip(),
            "auto_check": bool(self._upd_auto_var.get()),
        }
        _save_update_settings(self._update_settings)
        self._set_update_status(t('upd_saved'))

    def _check_updates(self):
        self._save_update_settings()
        check_for_updates(self, interactive=True, status_cb=self._set_update_status)

    def _refresh_lang(self):
        self._lbl_title.configure(text=t('lang_title'))
        self._lbl_sub.configure(text=t('lang_sub'))
        self._lang_seg.set({"es": "ES Espanol", "en": "EN English", "it": "IT Italiano"}.get(_cur_lang[0], "IT Italiano"))
        self._lbl_theme.configure(text=t('theme_label'))
        self._lbl_upd_title.configure(text=t('upd_title'))
        self._lbl_upd_ver.configure(text=f"{t('upd_version')} {APP_VERSION}")
        self._lbl_upd_source.configure(text=t('upd_source'))
        self._chk_upd_auto.configure(text=t('upd_auto'))
        self._btn_upd_save.configure(text=t('upd_save'))
        self._btn_upd_check.configure(text=t('upd_check'))
        self._lbl_upd_status.configure(text=t('upd_status_idle'))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Template JSON
# Todos los valores son fijos excepto: allarmi, valvetype, deui, daddr
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
_JSON_BASE = {
    "device": {
        "allarmi":          None,   # 1=ON / 0=OFF  â†’ desde UI
        "adc":              0,
        "minvddbat":        3000,
        "alarmbat":         3200,
        "vddbat":           3600,
        "cfm":              0,
        "alarmcycle":       16000,
        "valvestatuscycle": 120000,
        "payloadcycle":     0,
        "cfm_msg_cycle":    0,
        "valvetype":        None,   # 1=Motorizzata / 0=ELBA  â†’ desde UI
        "pulseduration":    80,
        "motorduration":    12000,
        "adcdelay":         500,
        "sendinterval":     130000,
        "capmv":            16000,
        "numcounters":      1,
        "numvalves":        1,
        "valvestatus":      0,
    },
    "radio": {
        "deui":      None,          # desde UI
        "daddr":     None,          # desde UI
        "appkey":    "0123456789ABCDEF0123456789ABCDEF",
        "nwkskey":   "0123456789ABCDEF0123456789ABCDEF",
        "appskey":   "0123456789ABCDEF0123456789ABCDEF",
        "appeui":    "665544332211AABB",
        "adr":       1,
        "port":      "1",
        "njm":       "0",
        "hweui":     "13",
        "nwkid":     "13",
        "pwr_value": "15",
        "retries":   "0",
        "dcs":       "0",
    },
}


def _build_json(dev_eui, dev_addr, model_type, allarme_on, sendinterval=130000, adc_value=0, counter_count=1, valve_count=0, valve_type="motorizzata"):
    """Construye el dict JSON para un dispositivo.
    valve_type: 'motorizzata' â†’ valvetype=1  |  'elba' â†’ valvetype=0
    adc_on: True â†’ adc=1  |  False â†’ adc=0
    """
    data = copy.deepcopy(_JSON_BASE)
    is_loracont = str(model_type).strip().lower() == "loracont"
    counter_total = int(counter_count)
    valve_total = 0 if is_loracont else int(valve_count)
    data["device"]["allarmi"]      = 1 if allarme_on else 0
    data["device"]["adc"]          = int(adc_value)
    data["device"]["valvetype"]    = 0 if is_loracont else (1 if valve_type == "motorizzata" else 0)
    data["device"]["sendinterval"] = int(sendinterval)
    data["device"]["numcounters"]  = counter_total
    data["device"]["numvalves"]    = valve_total
    data["radio"]["deui"]  = dev_eui
    data["radio"]["daddr"] = dev_addr
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# PDF: Etichette TIC12 / I-TIC
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _make_tic_pdf(labels, output_path, product_name):
    """
    labels: list of dicts {'serial': '00001/2026', 'fw': '04.00.05'}
    product_name: 'TIC12' or 'I-TIC 1V'
    Generates A4 portrait PDF: 3 labels/row Ã— 15 rows = 45 labels/page.
    Layout: logo on left | product/company/website on right | serial/FW bar bottom.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise ImportError("La librerÃ­a 'reportlab' no estÃ¡ instalada.\nEjecuta:  pip install reportlab")

    import io

    PW, PH = A4          # 595.28 Ã— 841.89 pt  (portrait)

    # â”€â”€ Margins (from Excel page setup) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    ML = 18 * mm
    MR = 14 * mm
    MT =  9 * mm
    MB =  4 * mm

    # â”€â”€ Grid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    N_COLS  = 3
    N_ROWS  = 15
    COL_GAP = 0.5 * mm
    GAP_V   = 0.8 * mm

    AW = PW - ML - MR
    AH = PH - MT - MB

    # Row heights (from Excel, in points)
    R1 = 13.5   # product name  (top)
    R2 = 12.0   # company
    R3 = 10.5   # website
    R4 = 12.0   # serial / FW bar  (bottom)
    LH = R1 + R2 + R3 + R4          # 48 pt total

    LABEL_W = 50 * mm
    grid_w = N_COLS * LABEL_W + (N_COLS - 1) * COL_GAP
    LW = LABEL_W
    grid_h = N_ROWS * LH + (N_ROWS - 1) * GAP_V
    grid_top = PH - MT - max(0, (AH - grid_h) / 2.0) + (4.5 * mm)
    grid_left = ML + max(0, (AW - grid_w) / 2.0)

    # Column proportions from Excel col widths: 7.0 / 9.29 / 9.86 (total 26.15)
    CA = LW * (7.00 / 26.15)        # logo area  =  "SERIAL N." cell width
    CB = LW * (9.29 / 26.15)        # serial value cell
    CC = LW * (9.86 / 26.15)        # FW cell
    TW = CB + CC                    # text section width

    # Font sizes
    FS_PROD = 10.0
    FS_COMP =  8.0
    FS_WEB  =  8.0
    FS_SLBL =  6.0
    FS_SVAL =  6.0
    FS_FW   =  6.0

    def _cy(row_bottom, row_h, fs):
        return row_bottom + (row_h - fs) * 0.5

    # â”€â”€ Prepare black version of logo for labels â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    logo_reader = None
    logo_path   = _resource("logo.png")
    if os.path.isfile(logo_path):
        try:
            src = Image.open(logo_path).convert("RGBA")
            px  = list(src.getdata())
            bpx = []
            for r, g, b, a in px:
                lum = 0.299*r + 0.587*g + 0.114*b
                if lum > 210 or a < 30:          # white / transparent â†’ keep transparent
                    bpx.append((255, 255, 255, 0))
                else:                              # any colored pixel â†’ black
                    bpx.append((0, 0, 0, a))
            black_img = Image.new("RGBA", src.size)
            black_img.putdata(bpx)
            buf = io.BytesIO()
            black_img.save(buf, format="PNG")
            buf.seek(0)
            logo_reader = ImageReader(buf)
        except Exception:
            logo_reader = None

    c = rl_canvas.Canvas(output_path, pagesize=A4)
    PER_PAGE = N_COLS * N_ROWS

    for idx, lbl in enumerate(labels):
        if idx > 0 and idx % PER_PAGE == 0:
            c.showPage()

        pos = idx % PER_PAGE
        ci  = pos % N_COLS
        ri  = pos // N_COLS

        lx       = grid_left + ci * (LW + COL_GAP)
        slot_top = grid_top - ri * (LH + GAP_V)
        ly       = slot_top - LH

        row4_bot = ly
        row3_bot = ly + R4
        row2_bot = ly + R4 + R3
        row1_bot = ly + R4 + R3 + R2
        label_top = ly + LH

        serial  = lbl['serial']
        fw_text = f"FW: {lbl['fw']}"

        # â”€â”€ Borders â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.5)

        # Outer rectangle
        c.rect(lx, ly, LW, LH, stroke=1, fill=0)

        # Vertical divider: logo | text  (full label height)
        c.line(lx + CA, ly, lx + CA, label_top)

        # Horizontal divider: header rows | bottom bar
        c.line(lx, row3_bot, lx + LW, row3_bot)

        # Vertical divider inside bottom bar: serial | FW
        c.line(lx + CA + CB, row4_bot, lx + CA + CB, row3_bot)

        # â”€â”€ Logo negro (left section, rows 1-3) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        if logo_reader:
            c.drawImage(logo_reader,
                        lx, row3_bot,
                        CA, (R1+R2+R3),
                        mask='auto', preserveAspectRatio=True, anchor='c')

        # â”€â”€ Text section center x â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        tx = lx + CA + TW / 2      # center of text area

        c.setFillColorRGB(0, 0, 0)

        # Row 1: product name
        c.setFont("Helvetica-Bold", FS_PROD)
        c.drawCentredString(tx, _cy(row1_bot, R1, FS_PROD), product_name)

        # Row 2: company
        c.setFont("Helvetica-Bold", FS_COMP)
        c.drawCentredString(tx, _cy(row2_bot, R2, FS_COMP), "TECNIDRO srl - GENOVA")

        # Row 3: website (centered in text section)
        c.setFont("Helvetica", FS_WEB)
        c.drawCentredString(tx, _cy(row3_bot, R3, FS_WEB),
                            "w w w . t e c n i d r o . c o m")

        # â”€â”€ Row 4 bottom bar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # Cell A â€” "SERIAL N."
        c.setFont("Helvetica", FS_SLBL)
        c.drawCentredString(lx + CA / 2, _cy(row4_bot, R4, FS_SLBL), "SERIAL N.")

        # Cell B â€” serial number
        c.setFont("Helvetica-Bold", FS_SVAL)
        c.drawCentredString(lx + CA + CB / 2, _cy(row4_bot, R4, FS_SVAL), serial)

        # Cell C â€” FW version
        c.setFont("Helvetica-Bold", FS_FW)
        c.drawCentredString(lx + CA + CB + CC / 2, _cy(row4_bot, R4, FS_FW), fw_text)

    c.save()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab 4: Generador JSON
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class JSONTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C_BODY_BG,
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        # TÃ­tulo
        self._lbl_title = ctk.CTkLabel(self, text=t('json_title'),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 6))

        # â”€â”€ Nombre del dispositivo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_name', self._refs)
        self._frow('lbl_prefix', "CBG_",  "j_prefix",  w=130)
        self._frow('lbl_from',   "0081",  "j_from",    w=100)
        self._frow('lbl_to',     "0100",  "j_to",      w=100)

        self._preview_lbl = ctk.CTkLabel(self, text="",
                                          text_color=C_HINT,
                                          font=ctk.CTkFont(size=10))
        self._preview_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        for v in (self.j_prefix_var, self.j_from_var, self.j_to_var):
            v.trace_add("write", self._update_preview)
        self._update_preview()

        # â”€â”€ Radio (DevEUI) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_deveui_j', self._refs)
        self._frow('lbl_deveui_j', "512345678B190051", "j_deveui")
        hint = ctk.CTkLabel(self, text=t('lbl_devaddr_j'),
                             text_color=C_HINT,
                             font=ctk.CTkFont(size=10, slant="italic"))
        hint.pack(anchor="w", padx=18, pady=(0, 4))
        self._refs['lbl_devaddr_j'] = hint

        _sec(self, 'sec_json_model', self._refs)
        self.json_model_var = tk.StringVar(value="rtu")
        self._json_model_rtu_btn = ctk.CTkRadioButton(
            self, text=t('json_model_rtu'),
            variable=self.json_model_var, value="rtu",
            font=ctk.CTkFont(size=13)
        )
        self._json_model_rtu_btn.pack(anchor="w", padx=28, pady=6)
        self._json_model_loracont_btn = ctk.CTkRadioButton(
            self, text=t('json_model_loracont'),
            variable=self.json_model_var, value="loracont",
            font=ctk.CTkFont(size=13)
        )
        self._json_model_loracont_btn.pack(anchor="w", padx=28, pady=6)
        self.json_model_var.trace_add("write", self._sync_json_model_type)

        _sec(self, 'sec_json_config', self._refs)
        r_adc = _row(self)
        lbl_json_adc = ctk.CTkLabel(r_adc, text=t('lbl_json_adc'), width=LBL_W, anchor="w")
        lbl_json_adc.pack(side="left")
        self._refs['lbl_json_adc'] = lbl_json_adc
        self.json_adc_var = tk.StringVar(value="0")
        self._json_adc_menu = ctk.CTkOptionMenu(r_adc, variable=self.json_adc_var, values=["0", "1"], width=120)
        self._json_adc_menu.pack(side="left", padx=(4, 0))

        r_counters = _row(self)
        lbl_json_counters = ctk.CTkLabel(r_counters, text=t('lbl_json_counters'), width=LBL_W, anchor="w")
        lbl_json_counters.pack(side="left")
        self._refs['lbl_json_counters'] = lbl_json_counters
        self.json_counters_var = tk.StringVar(value="1")
        self._json_counters_menu = ctk.CTkOptionMenu(r_counters, variable=self.json_counters_var, values=[str(i) for i in range(9)], width=120)
        self._json_counters_menu.pack(side="left", padx=(4, 0))

        # â”€â”€ Tipo de vÃ¡lvula â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_valve', self._refs)
        self.valve_var = tk.StringVar(value="motorizzata")
        self._json_valve_buttons = []
        for val, label in [("motorizzata", "Valvola Motorizzata"), ("elba", "ELBA")]:
            btn = ctk.CTkRadioButton(self, text=label,
                                     variable=self.valve_var, value=val,
                                     font=ctk.CTkFont(size=13))
            btn.pack(anchor="w", padx=28, pady=6)
            self._json_valve_buttons.append(btn)

        self._json_valves_row = _row(self)
        lbl_json_valves = ctk.CTkLabel(self._json_valves_row, text=t('lbl_json_valves'), width=LBL_W, anchor="w")
        lbl_json_valves.pack(side="left")
        self._refs['lbl_json_valves'] = lbl_json_valves
        self.json_valves_var = tk.StringVar(value="1")
        self._json_valves_menu = ctk.CTkOptionMenu(self._json_valves_row, variable=self.json_valves_var, values=[str(i) for i in range(9)], width=120)
        self._json_valves_menu.pack(side="left", padx=(4, 0))

        # â”€â”€ Allarme Sportello â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_allarme', self._refs)
        self.allarme_var = tk.StringVar(value="on")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.allarme_var, value=val,
                               font=ctk.CTkFont(size=13)
                               ).pack(anchor="w", padx=28, pady=6)

        # â”€â”€ ParÃ¡metros de envÃ­o â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_send_params', self._refs)
        self._frow('lbl_sendinterval', "130000", "j_sendinterval", w=140)
        self._sync_json_model_type()

        # â”€â”€ Carpeta de salida â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_out_json', self._refs)
        r_out = _row(self)
        lbl_fld = ctk.CTkLabel(r_out, text=t('lbl_out_folder'), width=LBL_W, anchor="w")
        lbl_fld.pack(side="left")
        self._refs['lbl_out_folder'] = lbl_fld
        self.out_folder_var = tk.StringVar()
        ctk.CTkEntry(r_out, textvariable=self.out_folder_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r_out, text="...", width=36,
                       command=self._browse_folder).pack(side="left")

        # â”€â”€ BotÃ³n generar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _div(self)
        btn = ctk.CTkButton(self, text=t('btn_gen_json'),
                             command=self._generate,
                             height=44, font=ctk.CTkFont(size=13, weight="bold"))
        btn.pack(pady=(4, 8), padx=30, fill="x")
        self._refs['btn_gen_json'] = btn

        self._status_lbl = ctk.CTkLabel(self, text="",
                                         text_color=C_HINT,
                                         font=ctk.CTkFont(size=10))
        self._status_lbl.pack(anchor="w", padx=18, pady=(0, 14))

    # â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _frow(self, key, default, attr, w=None):
        r = _row(self)
        lbl = ctk.CTkLabel(r, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._refs[key] = lbl
        var = tk.StringVar(value=default)
        setattr(self, f"{attr}_var", var)
        if w:
            entry = ctk.CTkEntry(r, textvariable=var, width=w)
            entry.pack(side="left", padx=(4, 0))
        else:
            entry = ctk.CTkEntry(r, textvariable=var)
            entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        setattr(self, f"{attr}_entry", entry)

    def _refresh_lang(self):
        self._lbl_title.configure(text=t('json_title'))
        for key, w in self._refs.items():
            w.configure(text=t(key[5:]) if key.startswith('_sec_') else t(key))
        self._json_model_rtu_btn.configure(text=t('json_model_rtu'))
        self._json_model_loracont_btn.configure(text=t('json_model_loracont'))
        self._sync_json_model_type()
        self._update_preview()

    def _sync_json_model_type(self, *_):
        try:
            is_loracont = self.json_model_var.get() == "loracont"
            if is_loracont:
                self._json_counters_menu.configure(values=["0", "1"])
                if self.json_counters_var.get() not in ("0", "1"):
                    self.json_counters_var.set("0")
                self.json_valves_var.set("0")
                self._refs['_sec_sec_valve'].master.pack_forget()
                for btn in self._json_valve_buttons:
                    btn.pack_forget()
                self._json_valves_row.pack_forget()
            else:
                self._json_counters_menu.configure(values=[str(i) for i in range(9)])
                if self.json_counters_var.get() not in [str(i) for i in range(9)]:
                    self.json_counters_var.set("1")
                before_widget = self._refs['_sec_sec_allarme'].master
                self._refs['_sec_sec_valve'].master.pack(before=before_widget, fill="x", padx=6, pady=(14, 4))
                for btn in self._json_valve_buttons:
                    btn.pack(before=before_widget, anchor="w", padx=28, pady=6)
                self._json_valves_row.pack(before=before_widget, fill="x", padx=10, pady=3)
        except Exception:
            pass

    def _update_preview(self, *_):
        try:
            prefix = self.j_prefix_var.get()
            start  = int(self.j_from_var.get())
            end    = int(self.j_to_var.get())
            count  = end - start + 1
            wd     = len(self.j_from_var.get())
            if count > 0:
                txt = t('prev_fmt').format(n=count,
                                           a=f"{prefix}{start:0{wd}d}",
                                           b=f"{prefix}{end:0{wd}d}")
            else:
                txt = t('prev_error')
        except ValueError:
            txt = ""
        self._preview_lbl.configure(text=txt)

    def _browse_folder(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta de salida")
        if p:
            self.out_folder_var.set(p)

    def _generate(self):
        try:
            prefix       = self.j_prefix_var.get().strip()
            start_raw    = self.j_from_var.get().strip()
            start        = int(start_raw)
            nw           = len(start_raw)
            end          = int(self.j_to_var.get().strip())
            deveui_s     = self.j_deveui_var.get().strip().upper()
            folder       = self.out_folder_var.get().strip()
            model_type   = self.json_model_var.get().strip()
            valve        = self.valve_var.get()
            allarme      = (self.allarme_var.get() == "on")
            adc_value    = self.json_adc_var.get().strip() or "0"
            counter_count = self.json_counters_var.get().strip() or "0"
            valve_count  = "0" if model_type == "loracont" else (self.json_valves_var.get().strip() or "0")
            sendinterval = int(self.j_sendinterval_var.get().strip())

            if not folder:
                messagebox.showerror("Error", "Selecciona una carpeta de salida."); return
            if not os.path.isdir(folder):
                messagebox.showerror("Error", "La carpeta no existe."); return
            if end < start:
                messagebox.showerror("Error", "'Hasta' debe ser â‰¥ 'Desde'."); return
            if adc_value not in ("0", "1"):
                messagebox.showerror("Error", "ADC debe ser 0 o 1."); return
            if not counter_count.isdigit():
                messagebox.showerror("Error", "Counters debe ser numerico."); return
            if not valve_count.isdigit():
                messagebox.showerror("Error", "Valves debe ser numerico."); return
            if len(deveui_s) != 16:
                messagebox.showerror("Error", f"DevEUI debe tener 16 hex (tiene {len(deveui_s)})."); return
            int(deveui_s, 16)

            deveui_int  = int(deveui_s, 16)
            num_devices = end - start + 1

            self._status_lbl.configure(text="Generando JSONâ€¦")
            self.update()

            for i in range(num_devices):
                name    = f"{prefix}{start + i:0{nw}d}"
                dev_eui = format(deveui_int + i, "016X")
                dev_addr = dev_eui[-8:]
                data = _build_json(
                    dev_eui,
                    dev_addr,
                    model_type,
                    allarme,
                    sendinterval,
                    adc_value,
                    counter_count,
                    valve_count,
                    valve,
                )
                filepath = os.path.join(folder, f"{name}.JSON")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)

            self._status_lbl.configure(
                text=f"âœ“  {num_devices} archivos JSON generados  â†’  {folder}")
            messagebox.showinfo("Ã‰xito",
                f"JSON generados correctamente.\n\n"
                f"  Dispositivos:   {num_devices}\n"
                f"  VÃ¡lvula:        {'Valvola Motorizzata' if valve=='motorizzata' else 'ELBA'}\n"
                f"  Allarme Sport.: {'ON' if allarme else 'OFF'}\n"
                f"  DevEUI desde:   {deveui_s}\n"
                f"  DevEUI hasta:   {format(deveui_int+num_devices-1,'016X')}\n\n"
                f"Carpeta:\n{folder}")

        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numÃ©ricos/hex.\n\nDetalle: {e}")
        except PermissionError:
            messagebox.showerror("Error de permisos", "No se pudo escribir en la carpeta.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab 5: Proyecto Completo
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class ProjectTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=C_BODY_BG,
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)
        _register_serial_refresh_callback(self._handle_serial_registry_changed)

    def _build(self):
        # TÃ­tulo
        self._lbl_title = ctk.CTkLabel(self, text=t('proj_title'),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 4))

        # Preview estructura (se actualiza dinÃ¡micamente)
        self._struct_lbl = ctk.CTkLabel(self, text="",
                                         text_color=C_HINT,
                                         font=ctk.CTkFont(size=10),
                                         justify="left")
        self._struct_lbl.pack(anchor="w", padx=18, pady=(0, 6))

        # â”€â”€ UbicaciÃ³n del proyecto â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_loc', self._refs)

        r_root = _row(self)
        lbl_rf = ctk.CTkLabel(r_root, text=t('lbl_root_fld'), width=LBL_W, anchor="w")
        lbl_rf.pack(side="left")
        self._refs['lbl_root_fld'] = lbl_rf
        self.root_folder_var = tk.StringVar()
        self.root_folder_var.trace_add("write", self._update_struct)
        ctk.CTkEntry(r_root, textvariable=self.root_folder_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r_root, text="...", width=36,
                       command=self._browse_root).pack(side="left")

        r_name = _row(self)
        lbl_pn = ctk.CTkLabel(r_name, text=t('lbl_proj_nm'), width=LBL_W, anchor="w")
        lbl_pn.pack(side="left")
        self._refs['lbl_proj_nm'] = lbl_pn
        self.proj_name_var = tk.StringVar(value="Proyecto_01")
        self.proj_name_var.trace_add("write", self._update_struct)
        ctk.CTkEntry(r_name, textvariable=self.proj_name_var).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        # â”€â”€ Dispositivos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_dev', self._refs)
        self._frow('lbl_prefix',  "CBG_",             "p_prefix",  w=130)
        self._frow('lbl_from',    "0081",              "p_from",    w=100)
        self._frow('lbl_to',      "0100",              "p_to",      w=100)
        self._frow('lbl_deveui',  "512345678B190051",  "p_deveui")

        for v in (self.p_prefix_var, self.p_from_var, self.p_to_var):
            v.trace_add("write", self._update_struct)

        self._prev_lbl = ctk.CTkLabel(self, text="",
                                       text_color=C_HINT,
                                       font=ctk.CTkFont(size=10))
        self._prev_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        self._update_preview()

        # â”€â”€ ParÃ¡metros CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_csv', self._refs)
        self._frow('lbl_model',   "210",                              "p_model")
        self._frow('lbl_newskey', "0123456789ABCDEF0123456789ABCDEF", "p_newskey")
        self._frow('lbl_appskey', "0123456789ABCDEF0123456789ABCDEF", "p_appskey")

        r_coords = _row(self)
        lbl_lat = ctk.CTkLabel(r_coords, text=t('lbl_lat'), width=LBL_W, anchor="w")
        lbl_lat.pack(side="left")
        self._refs['lbl_lat'] = lbl_lat
        self.p_lat_var = tk.StringVar()
        ctk.CTkEntry(r_coords, textvariable=self.p_lat_var, width=150).pack(
            side="left", padx=(4, 18))
        lbl_lon = ctk.CTkLabel(r_coords, text=t('lbl_lon'), width=80, anchor="w")
        lbl_lon.pack(side="left")
        self._refs['lbl_lon'] = lbl_lon
        self.p_lon_var = tk.StringVar()
        ctk.CTkEntry(r_coords, textvariable=self.p_lon_var, width=150).pack(
            side="left", padx=4)
        r_child = _row(self)
        lbl_childnumber = ctk.CTkLabel(r_child, text=t('lbl_childnumber'), width=LBL_W, anchor="w")
        lbl_childnumber.pack(side="left")
        self._refs['lbl_childnumber'] = lbl_childnumber
        self.p_childnumber_var = tk.StringVar(value="1")
        ctk.CTkEntry(r_child, textvariable=self.p_childnumber_var, width=120).pack(
            side="left", padx=(4, 18))

        # â”€â”€ Tipo de etiqueta â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_lbl', self._refs)
        self.p_label_var = tk.StringVar(value="nortu")
        for val, label in [("nortu",    "RTU NO BLTE"),
                            ("blte",     "RTU BLTE"),
                            ("tubo",     "RTU TUBO"),
                            ("loracont", "RTU LORACONT")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.p_label_var, value=val,
                               font=ctk.CTkFont(size=12)
                               ).pack(anchor="w", padx=28, pady=4)
        self.p_label_var.trace_add("write", self._sync_project_model_from_label)
        self._sync_project_model_from_label()

        # â”€â”€ Serial (para PDF) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_ser', self._refs)
        r_ser = _row(self)
        lbl_ss = ctk.CTkLabel(r_ser, text=t('lbl_ser_start'), width=LBL_W, anchor="w")
        lbl_ss.pack(side="left")
        self._refs['lbl_ser_start'] = lbl_ss
        self.p_ser_start_var = tk.StringVar(value="04906")
        ctk.CTkEntry(r_ser, textvariable=self.p_ser_start_var, width=120).pack(
            side="left", padx=(4, 18))
        lbl_yr = ctk.CTkLabel(r_ser, text=t('lbl_year'), width=80, anchor="w")
        lbl_yr.pack(side="left")
        self._refs['lbl_year'] = lbl_yr
        self.p_ser_year_var = tk.StringVar(value="2026")
        ctk.CTkEntry(r_ser, textvariable=self.p_ser_year_var, width=80).pack(
            side="left", padx=4)

        # â”€â”€ ParÃ¡metros JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _sec(self, 'sec_proj_jsn', self._refs)
        r_proj_adc = _row(self)
        lbl_proj_adc = ctk.CTkLabel(r_proj_adc, text=t('lbl_json_adc'), width=LBL_W, anchor="w")
        lbl_proj_adc.pack(side="left")
        self._refs['proj_lbl_json_adc'] = lbl_proj_adc
        self.p_json_adc_var = tk.StringVar(value="0")
        self._proj_json_adc_menu = ctk.CTkOptionMenu(
            r_proj_adc, variable=self.p_json_adc_var, values=["0", "1"], width=120
        )
        self._proj_json_adc_menu.pack(side="left", padx=(4, 0))

        r_proj_counters = _row(self)
        lbl_proj_counters = ctk.CTkLabel(r_proj_counters, text=t('lbl_json_counters'), width=LBL_W, anchor="w")
        lbl_proj_counters.pack(side="left")
        self._refs['proj_lbl_json_counters'] = lbl_proj_counters
        self.p_json_counters_var = tk.StringVar(value="1")
        self._proj_json_counters_menu = ctk.CTkOptionMenu(
            r_proj_counters, variable=self.p_json_counters_var, values=[str(i) for i in range(9)], width=120
        )
        self._proj_json_counters_menu.pack(side="left", padx=(4, 0))

        _sec(self, 'sec_valve', self._refs)
        self.p_valve_var = tk.StringVar(value="motorizzata")
        self._project_valve_buttons = []
        for val, label in [("motorizzata", "Valvola Motorizzata"), ("elba", "ELBA")]:
            btn = ctk.CTkRadioButton(
                self, text=label, variable=self.p_valve_var, value=val,
                font=ctk.CTkFont(size=12)
            )
            btn.pack(anchor="w", padx=28, pady=3)
            self._project_valve_buttons.append(btn)

        self._proj_json_valves_row = _row(self)
        lbl_proj_valves = ctk.CTkLabel(self._proj_json_valves_row, text=t('lbl_json_valves'), width=LBL_W, anchor="w")
        lbl_proj_valves.pack(side="left")
        self._refs['proj_lbl_json_valves'] = lbl_proj_valves
        self.p_json_valves_var = tk.StringVar(value="1")
        self._proj_json_valves_menu = ctk.CTkOptionMenu(
            self._proj_json_valves_row, variable=self.p_json_valves_var, values=[str(i) for i in range(9)], width=120
        )
        self._proj_json_valves_menu.pack(side="left", padx=(4, 0))

        _sec(self, 'sec_allarme', self._refs)
        self.p_allarme_var = tk.StringVar(value="on")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.p_allarme_var, value=val,
                               font=ctk.CTkFont(size=12)
                               ).pack(anchor="w", padx=28, pady=3)

        self._frow('lbl_sendinterval', "130000", "p_sendinterval", w=140)
        self._sync_project_json_params_from_label()

        # â”€â”€ BotÃ³n principal â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _div(self)
        self._btn_all = ctk.CTkButton(
            self, text=t('btn_gen_all'),
            command=self._generate_all,
            height=52,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#1a6a2a", "#1a6a2a"),
            hover_color=("#145520", "#145520"),
        )
        self._btn_all.pack(pady=(4, 10), padx=20, fill="x")

        self._status_lbl = ctk.CTkLabel(self, text="",
                                         text_color=C_HINT,
                                         font=ctk.CTkFont(size=10),
                                         justify="left")
        self._status_lbl.pack(anchor="w", padx=18, pady=(0, 16))

        self._update_struct()
        self.after(150, self._use_next_serial_from_github)

    # â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _frow(self, key, default, attr, w=None):
        r = _row(self)
        lbl = ctk.CTkLabel(r, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._refs[key] = lbl
        var = tk.StringVar(value=default)
        setattr(self, f"{attr}_var", var)
        if w:
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkEntry(r, textvariable=var).pack(
                side="left", fill="x", expand=True, padx=(4, 0))

    def _refresh_lang(self):
        self._lbl_title.configure(text=t('proj_title'))
        for key, w in self._refs.items():
            if key.startswith('_sec_'):
                text_key = key[5:]
            elif key.startswith('proj_'):
                text_key = key[5:]
            else:
                text_key = key
            w.configure(text=t(text_key))
        self._sync_project_json_params_from_label()
        self._update_struct()
        self._update_preview()
        self._btn_all.configure(text=t('btn_gen_all'))

    def _browse_root(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta raiz")
        if p:
            self.root_folder_var.set(p)

    def _update_preview(self, *_):
        try:
            prefix = self.p_prefix_var.get()
            start  = int(self.p_from_var.get())
            end    = int(self.p_to_var.get())
            count  = end - start + 1
            wd     = len(self.p_from_var.get())
            if count > 0:
                txt = t('prev_fmt').format(n=count,
                                           a=f"{prefix}{start:0{wd}d}",
                                           b=f"{prefix}{end:0{wd}d}")
            else:
                txt = t('prev_error')
        except ValueError:
            txt = ""
        self._prev_lbl.configure(text=txt)

    def _update_struct(self, *_):
        root   = self.root_folder_var.get().strip() or "..."
        name   = self.proj_name_var.get().strip()   or "NombreProyecto"
        try:
            n = int(self.p_to_var.get()) - int(self.p_from_var.get()) + 1
        except Exception:
            n = "?"
        pfx = self.p_prefix_var.get() if hasattr(self, 'p_prefix_var') else ""
        txt = (
            f"  {root}/{name}/\n"
            f"    CSV/       -> {name}.csv\n"
            f"    JSON/      -> {n} archivos ({pfx}...).JSON\n"
            f"    etichette/ -> {name}.pdf"
        )
        self._struct_lbl.configure(text=txt)

    def _sync_project_model_from_label(self, *_):
        try:
            self.p_model_var.set("297" if self.p_label_var.get() == "loracont" else "210")
            self._sync_project_json_params_from_label()
        except Exception:
            pass

    def _sync_project_json_params_from_label(self, *_):
        try:
            is_loracont = self.p_label_var.get() == "loracont"
            if is_loracont:
                self._proj_json_counters_menu.configure(values=["0", "1"])
                if self.p_json_counters_var.get() not in ("0", "1"):
                    self.p_json_counters_var.set("0")
                self.p_json_valves_var.set("0")
                self._refs['_sec_sec_valve'].master.pack_forget()
                for btn in self._project_valve_buttons:
                    btn.pack_forget()
                self._proj_json_valves_row.pack_forget()
            else:
                self._proj_json_counters_menu.configure(values=[str(i) for i in range(9)])
                if self.p_json_counters_var.get() not in [str(i) for i in range(9)]:
                    self.p_json_counters_var.set("1")
                before_widget = self._refs['_sec_sec_allarme'].master
                self._refs['_sec_sec_valve'].master.pack(before=before_widget, fill="x", padx=6, pady=(14, 4))
                for btn in self._project_valve_buttons:
                    btn.pack(before=before_widget, anchor="w", padx=28, pady=3)
                self._proj_json_valves_row.pack(before=before_widget, fill="x", padx=10, pady=3)
        except Exception:
            pass

    def _handle_serial_registry_changed(self):
        self.after(0, self._use_next_serial_from_github)

    def _use_next_serial_from_github(self):
        try:
            start = int(self.p_from_var.get().strip())
            end = int(self.p_to_var.get().strip())
            if end < start:
                return
            next_start, _ = _next_available_serial("RTU", count=(end - start + 1), settings=_load_serial_settings())
            width = max(len(self.p_ser_start_var.get().strip()), SERIAL_FAMILY_SETTINGS["RTU"]["number_width"])
            self.p_ser_start_var.set(f"{next_start:0{width}d}")
            self._status_lbl.configure(
                text=t("serial_next_status").format(
                    family=_serial_family_name("RTU"),
                    value=f"{next_start:0{width}d}",
                )
            )
        except Exception as exc:
            self._status_lbl.configure(text=str(exc))

    # â”€â”€ GeneraciÃ³n â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def _generate_all(self):
        try:
            # â”€â”€ Validaciones bÃ¡sicas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            root      = self.root_folder_var.get().strip()
            proj_name = self.proj_name_var.get().strip()
            prefix    = self.p_prefix_var.get().strip()
            start_raw = self.p_from_var.get().strip()
            start     = int(start_raw)
            nw        = len(start_raw)
            end       = int(self.p_to_var.get().strip())
            deveui_s  = self.p_deveui_var.get().strip().upper()
            model     = self.p_model_var.get().strip()
            new_skey  = self.p_newskey_var.get().strip().upper()
            app_skey  = self.p_appskey_var.get().strip().upper()
            lat       = self.p_lat_var.get().strip()
            lon       = self.p_lon_var.get().strip()
            ser_raw   = self.p_ser_start_var.get().strip()
            ser_year  = self.p_ser_year_var.get().strip()
            label_opt    = self.p_label_var.get()
            valve        = self.p_valve_var.get()
            allarme      = (self.p_allarme_var.get() == "on")
            adc_value    = self.p_json_adc_var.get().strip() or "0"
            counter_count = self.p_json_counters_var.get().strip() or "0"
            valve_count  = "0" if label_opt == "loracont" else (self.p_json_valves_var.get().strip() or "0")
            sendinterval = int(self.p_sendinterval_var.get().strip())
            project_childnumber = "0" if label_opt == "loracont" else (self.p_childnumber_var.get().strip() or "1")

            if not root:
                messagebox.showerror("Error", "Selecciona una carpeta raÃ­z."); return
            if not proj_name:
                messagebox.showerror("Error", "Escribe un nombre de proyecto."); return
            if not os.path.isdir(root):
                messagebox.showerror("Error", "La carpeta raÃ­z no existe."); return
            if end < start:
                messagebox.showerror("Error", "'Hasta' debe ser â‰¥ 'Desde'."); return
            if not project_childnumber.isdigit():
                messagebox.showerror("Error", "La cantidad de valvulas / childnumber debe ser numerica."); return
            if len(deveui_s) != 16:
                messagebox.showerror("Error", f"DevEUI debe tener 16 hex."); return
            int(deveui_s, 16)
            if len(new_skey) != 32:
                messagebox.showerror("Error", "NewSKey debe tener 32 hex."); return
            if len(app_skey) != 32:
                messagebox.showerror("Error", "AppSKey debe tener 32 hex."); return
            if adc_value not in ("0", "1"):
                messagebox.showerror("Error", "ADC debe ser 0 o 1."); return
            if not counter_count.isdigit():
                messagebox.showerror("Error", "La cantidad de counters debe ser numerica."); return
            if label_opt != "loracont" and not valve_count.isdigit():
                messagebox.showerror("Error", "La cantidad de valvulas debe ser numerica."); return

            num_devices = end - start + 1
            deveui_int  = int(deveui_s, 16)
            ser_width   = len(ser_raw)
            ser_start   = int(ser_raw)

            # â”€â”€ Crear estructura de carpetas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            proj_dir  = os.path.join(root, proj_name)
            csv_dir   = os.path.join(proj_dir, "CSV")
            json_dir  = os.path.join(proj_dir, "JSON")
            label_dir = os.path.join(proj_dir, "etiquette")
            for d in (proj_dir, csv_dir, json_dir, label_dir):
                os.makedirs(d, exist_ok=True)

            self._status_lbl.configure(text="â³  Generandoâ€¦")
            self.update()

            # â”€â”€ 1. CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            csv_path = os.path.join(csv_dir, f"{proj_name}.csv")
            hdr = ["Name","Model","AppEUI","DevEUI","Auth","AppKey","DevAddr",
                   "NewSKey","AppSKey","Class","Latitude","Longitude","Tag",
                   "MultiTag","Alias","Group","ParentAppEUI","ParentDevEUI",
                   "childnumber","devStatusReqInterval"]
            rows = []
            devices = []
            for i in range(num_devices):
                nm = f"{prefix}{start+i:0{nw}d}"
                de = format(deveui_int+i, "016X")
                da = de[-8:]
                devices.append({'name': nm, 'dev_eui': de, 'dev_addr': da})
                rows.append([nm, model, FIXED_APP_EUI, de, FIXED_AUTH, "", da,
                              new_skey, app_skey, FIXED_CLASS, lat, lon, "",
                              "", "", FIXED_GROUP, "", "", project_childnumber, "0"])
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(hdr); w.writerows(rows)

            # â”€â”€ 2. JSON â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            for i, dev in enumerate(devices):
                data = _build_json(
                    dev['dev_eui'],
                    dev['dev_addr'],
                    "loracont" if label_opt == "loracont" else "rtu",
                    allarme,
                    sendinterval,
                    adc_value,
                    counter_count,
                    valve_count,
                    valve,
                )
                with open(os.path.join(json_dir, f"{dev['name']}.JSON"),
                          "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)

            # â”€â”€ 3. PDF Etichette â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            pdf_devices = []
            for i, dev in enumerate(devices):
                sn = format(ser_start+i, f"0{ser_width}d")
                pdf_devices.append({
                    'serial':   f"{sn}/{ser_year}",
                    'name':     dev['name'],
                    'dev_eui':  dev['dev_eui'],
                    'dev_addr': dev['dev_addr'],
                })
            pdf_path = os.path.join(label_dir, f"{proj_name}.pdf")
            _make_pdf(pdf_devices, pdf_path,
                      include_bluetooth=(label_opt == "blte"),
                      rtu_header=(label_opt == "tubo"),
                      loraconta=(label_opt == "loracont"))
            settings = _prepare_serial_settings_for_write(self)
            if settings is None:
                return
            self._status_lbl.configure(text=t("serial_repo_sync_after_generate"))
            self.update()
            try:
                _serial_registry_update_last(settings, "RTU", ser_start, ser_start + num_devices - 1, ser_year, num_devices)
            except Exception as exc:
                self._status_lbl.configure(text=str(exc))
                _notify_registry_update_failure(self, exc)
                return

            # â”€â”€ Resultado â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self._status_lbl.configure(
                text=t("serial_repo_reserved").format(
                    family=_serial_family_name("RTU"),
                    start=f"{ser_start:0{ser_width}d}",
                    end=f"{ser_start + num_devices - 1:0{ser_width}d}",
                    year=ser_year,
                ))
            _notify_serial_registry_changed()
            messagebox.showinfo("Ã‰xito",
                f"Proyecto generado correctamente.\n\n"
                f"  {proj_name}/\n"
                f"  CSV/       -> {proj_name}.csv\n"
                f"  JSON/      -> {num_devices} archivos .JSON\n"
                f"  etichette/ -> {proj_name}.pdf\n\n"
                f"  Dispositivos:  {num_devices}\n"
                f"  VÃ¡lvula:       {'Motorizzata' if valve=='motorizzata' else 'ELBA'}\n"
                f"  Allarme:       {'ON' if allarme else 'OFF'}\n"
                f"  Etiqueta:      {label_opt.upper()}\n\n"
                f"Carpeta:\n{proj_dir}")

        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numÃ©ricos/hex.\n\nDetalle: {e}")
        except ImportError as e:
            messagebox.showerror("LibrerÃ­a faltante", str(e))
        except PermissionError:
            messagebox.showerror("Error de permisos", "No se pudo escribir en la carpeta.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# Tab: Etichette TIC12 / I-TIC
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
class TICLabelTab(ctk.CTkScrollableFrame):
    def __init__(self, parent, product_name, title_key):
        super().__init__(parent, fg_color=C_BODY_BG,
                         corner_radius=0, border_width=0, label_text="")
        self._product_name = product_name
        self._title_key    = title_key
        self._family = "TIC12" if product_name == "TIC12" else "I-TIC"
        self._refs = {}
        self._pdf_output_auto = True
        self._last_auto_pdf_path = ""
        self._build()
        _lang_cbs.append(self._refresh_lang)
        _register_serial_refresh_callback(self._handle_serial_registry_changed)

    def _build(self):
        fw_default = "03.02.03" if self._product_name == "TIC12" else "04.00.05"

        self._lbl_title = ctk.CTkLabel(self, text=t(self._title_key),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 6))

        if self._family == "I-TIC":
            info_card = ctk.CTkFrame(
                self,
                fg_color=C_CARD_BG,
                corner_radius=16,
                border_width=1,
                border_color=C_CARD_BORDER,
            )
            info_card.pack(fill="x", padx=18, pady=(0, 10))

            self._refs["itic_solenoid_title"] = ctk.CTkLabel(
                info_card,
                text=t("itic_solenoid_title"),
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            )
            self._refs["itic_solenoid_title"].pack(anchor="w", padx=16, pady=(12, 4))

            self._refs["itic_solenoid_red"] = ctk.CTkLabel(
                info_card,
                text=t("itic_solenoid_red"),
                anchor="w",
            )
            self._refs["itic_solenoid_red"].pack(anchor="w", padx=16, pady=(0, 2))

            self._refs["itic_solenoid_black"] = ctk.CTkLabel(
                info_card,
                text=t("itic_solenoid_black"),
                anchor="w",
            )
            self._refs["itic_solenoid_black"].pack(anchor="w", padx=16, pady=(0, 12))

        _sec(self, 'sec_tic_dev', self._refs)
        self._frow('lbl_tic_from', '0001',     'tic_from', w=100)
        self._frow('lbl_tic_to',   '1000',     'tic_to',   w=100)
        self._frow('lbl_tic_yr',   '2026',     'tic_yr',   w=100)
        self._frow('lbl_tic_fw',   fw_default, 'tic_fw')

        self._prev_lbl = ctk.CTkLabel(self, text="", text_color=C_HINT,
                                       font=ctk.CTkFont(size=10))
        self._prev_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        for v in (self.tic_from_var, self.tic_to_var):
            v.trace_add("write", self._update_preview)
        self._update_preview()

        _sec(self, 'sec_tic_out', self._refs)
        r = _row(self)
        lbl_pdf = ctk.CTkLabel(r, text=t('lbl_tic_pdf'), width=LBL_W, anchor="w")
        lbl_pdf.pack(side="left")
        self._refs['lbl_tic_pdf'] = lbl_pdf
        self.tic_pdf_var = tk.StringVar()
        ctk.CTkEntry(r, textvariable=self.tic_pdf_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r, text="...", width=36,
                       command=self._browse_pdf).pack(side="left")

        _div(self)
        self._btn = ctk.CTkButton(self, text=t('btn_tic_gen'),
                                   command=self._generate,
                                   height=44,
                                   font=ctk.CTkFont(size=13, weight="bold"))
        self._btn.pack(pady=(4, 8), padx=30, fill="x")
        self._refs['btn_tic_gen'] = self._btn

        self._status_lbl = ctk.CTkLabel(self, text="", text_color=C_HINT,
                                         font=ctk.CTkFont(size=10))
        self._status_lbl.pack(anchor="w", padx=18, pady=(0, 14))
        for v in (self.tic_from_var, self.tic_to_var):
            v.trace_add("write", self._update_auto_pdf_output)
        self._update_auto_pdf_output()
        self.after(150, self._use_next_serial_from_github)

    def _frow(self, key, default, attr, w=None):
        r = _row(self)
        lbl = ctk.CTkLabel(r, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._refs[key] = lbl
        var = tk.StringVar(value=default)
        setattr(self, f"{attr}_var", var)
        if w:
            ctk.CTkEntry(r, textvariable=var, width=w).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkEntry(r, textvariable=var).pack(
                side="left", fill="x", expand=True, padx=(4, 0))

    def _refresh_lang(self):
        self._lbl_title.configure(text=t(self._title_key))
        for key, w in self._refs.items():
            w.configure(text=t(key))
        self._update_preview()

    def _browse_pdf(self):
        p = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")])
        if p:
            self.tic_pdf_var.set(p)
            self._pdf_output_auto = False

    def _suggest_pdf_output_path(self):
        try:
            start_raw = self.tic_from_var.get().strip()
            end_raw = self.tic_to_var.get().strip()
            start_num = int(start_raw)
            end_num = int(end_raw)
            if end_num < start_num:
                return ""
            width = max(len(start_raw), len(end_raw), SERIAL_FAMILY_SETTINGS[self._family]["number_width"])
            start_value = f"{start_num:0{width}d}"
            end_value = f"{end_num:0{width}d}"
            label_name = "TIC12" if self._family == "TIC12" else "I-TIC"
            return _default_label_pdf_path(label_name, start_value, end_value)
        except Exception:
            return ""

    def _update_auto_pdf_output(self, *_):
        suggested = self._suggest_pdf_output_path()
        current = self.tic_pdf_var.get().strip()
        if suggested and (self._pdf_output_auto or not current or current == self._last_auto_pdf_path):
            self.tic_pdf_var.set(suggested)
            self._pdf_output_auto = True
        if suggested:
            self._last_auto_pdf_path = suggested

    def _handle_serial_registry_changed(self):
        self.after(0, self._use_next_serial_from_github)

    def _update_preview(self, *_):
        try:
            n = int(self.tic_to_var.get()) - int(self.tic_from_var.get()) + 1
            pages = -(-n // 45)   # ceiling division
            self._prev_lbl.configure(
                text=f"  \u2192  {n} etiquetas  |  {pages} p\u00e1gina(s)  (45 por p\u00e1gina)")
        except ValueError:
            self._prev_lbl.configure(text="")

    def _current_count(self):
        start = int(self.tic_from_var.get().strip())
        end = int(self.tic_to_var.get().strip())
        if end < start:
            raise ValueError("'Hasta' debe ser â‰¥ 'Desde'")
        return start, end, end - start + 1

    def _use_next_serial_from_github(self):
        try:
            _, _, count = self._current_count()
            next_start, next_end = _next_available_serial(self._family, count=count, settings=_load_serial_settings())
            width = max(len(self.tic_from_var.get().strip()), SERIAL_FAMILY_SETTINGS[self._family]["number_width"])
            self.tic_from_var.set(f"{next_start:0{width}d}")
            self.tic_to_var.set(f"{next_end:0{width}d}")
            self._update_auto_pdf_output()
            self._status_lbl.configure(
                text=t("serial_next_status").format(
                    family=_serial_family_name(self._family),
                    value=f"{next_start:0{width}d}",
                )
            )
        except Exception as exc:
            self._status_lbl.configure(text=str(exc))

    def _generate(self):
        try:
            start_raw = self.tic_from_var.get().strip()
            start     = int(start_raw)
            end       = int(self.tic_to_var.get().strip())
            year      = self.tic_yr_var.get().strip()
            fw        = self.tic_fw_var.get().strip()
            out_pdf   = self.tic_pdf_var.get().strip()

            if end < start:
                messagebox.showerror("Error", "'Hasta' debe ser \u2265 'Desde'"); return
            if not out_pdf:
                self._update_auto_pdf_output()
                out_pdf = self.tic_pdf_var.get().strip()
            if not out_pdf:
                messagebox.showerror("Error", "Selecciona un archivo de salida PDF"); return
            if not year:
                messagebox.showerror("Error", "Escribe el a\u00f1o"); return

            nw = max(5, len(str(end)))
            labels = [
                {'serial': f"{i:0{nw}d}/{year}", 'fw': fw}
                for i in range(start, end + 1)
            ]

            self._status_lbl.configure(text="\u23f3  Generando\u2026")
            self.update()

            _make_tic_pdf(labels, out_pdf, self._product_name)
            settings = _prepare_serial_settings_for_write(self)
            if settings is None:
                return
            self._status_lbl.configure(text=t("serial_repo_sync_after_generate"))
            self.update()
            try:
                _serial_registry_update_last(settings, self._family, start, end, year, end - start + 1)
            except Exception as exc:
                self._status_lbl.configure(text=str(exc))
                _notify_registry_update_failure(self, exc)
                return

            n = len(labels)
            pages = -(-n // 45)
            self._status_lbl.configure(text=t("serial_repo_reserved").format(
                family=_serial_family_name(self._family),
                start=f"{start:0{nw}d}",
                end=f"{end:0{nw}d}",
                year=year,
            ))
            _notify_serial_registry_changed()
            messagebox.showinfo("Exito",
                f"PDF generado correctamente.\n\n"
                f"Etiquetas: {n}\n"
                f"P\u00e1ginas:   {pages}\n\n"
                f"Archivo:\n{out_pdf}")

        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica los campos num\u00e9ricos.\n{e}")
        except ImportError as e:
            messagebox.showerror("Librer\u00eda faltante", str(e))
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# App
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
GW_COL_WIDTHS_PT = [114.75, 157.50, 180.75]
GW_ROW_HEIGHTS_PT = [21.0, 16.9, 9.0, 12.0, 10.9, 3.6, 15.0, 15.0, 15.0]
GW_GAPS_PT = [24.6, 27.6, 27.0, 30.0]
GW_PAGE_LEFT_PT = 0.7 * 72.0
GW_PAGE_TOP_PT = 0.75 * 72.0
GW_PAGE_BOTTOM_PT = 0.75 * 72.0
GW_LABEL_WIDTH_PT = sum(GW_COL_WIDTHS_PT)
GW_LABEL_HEIGHT_PT = sum(GW_ROW_HEIGHTS_PT)


def _normalize_hex(value, expected_len, field_name, lowercase=False):
    cleaned = "".join(ch for ch in value.strip() if ch.isalnum())
    if len(cleaned) != expected_len:
        raise ValueError(f"{field_name} debe tener {expected_len} caracteres hexadecimales.")
    int(cleaned, 16)
    return cleaned.lower() if lowercase else cleaned.upper()


def _register_pdf_font(font_name, filename, fallback):
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return fallback

    font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", filename)
    if not os.path.isfile(font_path):
        return fallback

    try:
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        return font_name
    except Exception:
        return fallback


def _wrap_pdf_text(text, font_name, font_size, max_width):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    words = text.split()
    if not words:
        return [""]

    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_pdf_text(text, font_name, max_size, min_size, max_width, max_lines=1):
    size = max_size
    while size >= min_size:
        lines = _wrap_pdf_text(text, font_name, size, max_width)
        if len(lines) <= max_lines:
            return size, lines
        size -= 0.5
    return min_size, _wrap_pdf_text(text, font_name, min_size, max_width)


def _draw_text_in_box(canvas_obj, text, x, y, width, height, font_name, font_size,
                      align="center", bold=False, valign="center"):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    lines = _wrap_pdf_text(text, font_name, font_size, max(width - 4, 10))
    leading = font_size * 1.15
    total_h = len(lines) * leading

    if valign == "top":
        base_y = y + height - font_size - 1.2
    else:
        base_y = y + (height + total_h) / 2.0 - leading

    canvas_obj.setFont(font_name, font_size)
    for idx, line in enumerate(lines):
        yy = base_y - idx * leading
        if align == "right":
            xx = x + width - 2
            canvas_obj.drawRightString(xx, yy, line)
        elif align == "left":
            xx = x + 2
            canvas_obj.drawString(xx, yy, line)
        else:
            text_w = stringWidth(line, font_name, font_size)
            xx = x + (width - text_w) / 2.0
            canvas_obj.drawString(xx, yy, line)


def _make_gateway_pdf(gateways, output_path, serial_year):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as rl_canvas
    except ImportError:
        raise ImportError("La libreria 'reportlab' no esta instalada.\nEjecuta: pip install reportlab")

    regular_font = _register_pdf_font("CalibriGW", "calibri.ttf", "Helvetica")
    bold_font = _register_pdf_font("CalibriGW-Bold", "calibrib.ttf", "Helvetica-Bold")

    page_w, page_h = A4
    row_edges = [0.0]
    for row_h in GW_ROW_HEIGHTS_PT:
        row_edges.append(row_edges[-1] + row_h)

    block_offsets = [0.0]
    acc = 0.0
    for gap in GW_GAPS_PT:
        acc += GW_LABEL_HEIGHT_PT + gap
        block_offsets.append(acc)

    tecnidro_path = _resource("gw_logo_tecnidro.png")
    if not os.path.isfile(tecnidro_path):
        tecnidro_path = _resource("logo.png")
    lorawan_path = _resource("gw_logo_lorawan.jpeg")

    tecnidro_img = ImageReader(tecnidro_path) if os.path.isfile(tecnidro_path) else None
    lorawan_img = ImageReader(lorawan_path) if os.path.isfile(lorawan_path) else None

    c = rl_canvas.Canvas(output_path, pagesize=A4)
    per_page = 5

    for idx, gateway in enumerate(gateways):
        if idx > 0 and idx % per_page == 0:
            c.showPage()

        slot = idx % per_page
        top = page_h - GW_PAGE_TOP_PT - block_offsets[slot]
        left = GW_PAGE_LEFT_PT
        bottom = top - GW_LABEL_HEIGHT_PT
        border_top = top - 10.0

        x0 = left
        x1 = x0 + GW_COL_WIDTHS_PT[0]
        x2 = x1 + GW_COL_WIDTHS_PT[1]
        x3 = x2 + GW_COL_WIDTHS_PT[2]

        table_top = top - row_edges[6]
        r7_bottom = top - row_edges[7]
        r8_bottom = top - row_edges[8]

        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(0.45)
        c.line(left, border_top, x3, border_top)
        c.line(left, border_top, left, bottom)
        c.line(x3, border_top, x3, bottom)
        c.line(left, bottom, x3, bottom)
        c.line(left, table_top, x3, table_top)
        c.line(left, r7_bottom, x3, r7_bottom)
        c.line(left, r8_bottom, x2, r8_bottom)
        c.line(x1, bottom, x1, table_top)
        c.line(x2, bottom, x2, table_top)

        if tecnidro_img:
            c.drawImage(
                tecnidro_img,
                left + 18.0,
                top - 60.0,
                width=50.0,
                height=50.0,
                mask="auto",
                preserveAspectRatio=True,
                anchor="sw",
            )
        if lorawan_img:
            c.drawImage(
                lorawan_img,
                left + 96.0,
                top - 44.0,
                width=118.0,
                height=22.8,
                mask="auto",
                preserveAspectRatio=True,
                anchor="sw",
            )

        _draw_text_in_box(c, "HYDRONET", left + 176.0, top - 50.0, 172.0, 26.0,
                          bold_font, 20, align="left")
        _draw_text_in_box(c, "GATEWAY LTE", x2, top - row_edges[2], GW_COL_WIDTHS_PT[2], GW_ROW_HEIGHTS_PT[1],
                          bold_font, 18, align="center")
        _draw_text_in_box(c, "TECNIDRO srl - GENOVA", left, top - row_edges[4], GW_LABEL_WIDTH_PT,
                          GW_ROW_HEIGHTS_PT[3], bold_font, 9.5, align="center", valign="top")
        _draw_text_in_box(c, "w w w . t e c n i d r o . c o m", left, top - row_edges[5], GW_LABEL_WIDTH_PT,
                          GW_ROW_HEIGHTS_PT[4], regular_font, 9.5, align="center", valign="top")

        label_font = 10
        value_font = 10
        model_font, model_lines = _fit_pdf_text(
            f"MODEL: {gateway['model']}",
            regular_font,
            10,
            7,
            GW_COL_WIDTHS_PT[2] - 4,
            max_lines=2,
        )
        alias_font, alias_lines = _fit_pdf_text(
            gateway["alias"],
            bold_font,
            10,
            7,
            GW_COL_WIDTHS_PT[2] - 4,
            max_lines=3,
        )

        row7_y = top - row_edges[7]
        row8_y = top - row_edges[8]
        row9_y = bottom

        _draw_text_in_box(c, "SERIAL N.", x0, row7_y, GW_COL_WIDTHS_PT[0], GW_ROW_HEIGHTS_PT[6],
                          bold_font, label_font)
        serial_value = f"{gateway['serial']}/{serial_year}"
        _draw_text_in_box(c, serial_value, x1, row7_y, GW_COL_WIDTHS_PT[1], GW_ROW_HEIGHTS_PT[6],
                          regular_font, value_font)
        _draw_text_in_box(c, "MODEL: " + gateway["model"], x2, row7_y, GW_COL_WIDTHS_PT[2], GW_ROW_HEIGHTS_PT[6],
                          regular_font, model_font)

        _draw_text_in_box(c, "GW MAC", x0, row8_y, GW_COL_WIDTHS_PT[0], GW_ROW_HEIGHTS_PT[7],
                          bold_font, label_font)
        _draw_text_in_box(c, gateway["mac"], x1, row8_y, GW_COL_WIDTHS_PT[1], GW_ROW_HEIGHTS_PT[7],
                          regular_font, value_font)
        _draw_text_in_box(c, gateway["alias"], x2, row9_y, GW_COL_WIDTHS_PT[2],
                          GW_ROW_HEIGHTS_PT[7] + GW_ROW_HEIGHTS_PT[8], bold_font, alias_font)

        _draw_text_in_box(c, "GW EUI/ID", x0, row9_y, GW_COL_WIDTHS_PT[0], GW_ROW_HEIGHTS_PT[8],
                          bold_font, label_font)
        _draw_text_in_box(c, gateway["dev_eui"], x1, row9_y, GW_COL_WIDTHS_PT[1], GW_ROW_HEIGHTS_PT[8],
                          regular_font, value_font)

    c.save()


class GatewayDialog(ctk.CTkToplevel):
    def __init__(self, parent, gateway=None, initial_serial=""):
        super().__init__(parent)
        self.title(t("gw_dialog_title"))
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.result = None

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.grid_columnconfigure(1, weight=1)

        fields = [
            (t("gw_field_model"), gateway.get("model", "") if gateway else ""),
            (t("gw_field_alias"), gateway.get("alias", "") if gateway else ""),
            (t("gw_field_serial"), gateway.get("serial", "") if gateway else initial_serial),
            (t("gw_field_mac"), gateway.get("mac", "") if gateway else ""),
            (t("gw_field_deveui"), gateway.get("dev_eui", "") if gateway else ""),
        ]

        self.vars = {}
        for row, (label, default) in enumerate(fields):
            ctk.CTkLabel(container, text=label, width=160, anchor="w").grid(
                row=row, column=0, sticky="w", padx=(0, 12), pady=(0 if row == 0 else 10, 0)
            )
            var = tk.StringVar(value=default)
            self.vars[label] = var
            ctk.CTkEntry(container, textvariable=var, width=420).grid(
                row=row, column=1, sticky="ew", pady=(0 if row == 0 else 10, 0)
            )

        btns = ctk.CTkFrame(container, fg_color="transparent")
        btns.grid(row=len(fields), column=0, columnspan=2, sticky="e", pady=(18, 0))
        ctk.CTkButton(btns, text=t("gw_cancel"), width=110, command=self.destroy).pack(side="right")
        ctk.CTkButton(btns, text=t("gw_accept"), width=110, command=self._accept).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(50, lambda: self.focus_force())

    def _accept(self):
        model = self.vars[t("gw_field_model")].get().strip()
        alias = self.vars[t("gw_field_alias")].get().strip()
        serial = self.vars[t("gw_field_serial")].get().strip()
        mac_raw = self.vars[t("gw_field_mac")].get().strip()
        dev_eui_raw = self.vars[t("gw_field_deveui")].get().strip()

        if not all([model, alias, serial, mac_raw, dev_eui_raw]):
            messagebox.showerror("Error", t("gw_error_complete"))
            return

        try:
            mac = _normalize_hex(mac_raw, 12, "MAC", lowercase=False)
            dev_eui = _normalize_hex(dev_eui_raw, 16, "DevEUI", lowercase=True)
        except ValueError as exc:
            messagebox.showerror("Error", str(exc))
            return

        self.result = {
            "model": model,
            "alias": alias,
            "serial": serial,
            "mac": mac,
            "dev_eui": dev_eui,
        }
        self.destroy()


class GatewayTab(ctk.CTkScrollableFrame):
    X4S_LTE_SHUTDOWN_CMD = "curl -s update.resiot.io/extra/armshipmodegwsolar.sh | bash"

    def __init__(self, master):
        super().__init__(master, fg_color=C_BODY_BG, corner_radius=0, border_width=0, label_text="")
        self._gateways = []
        self._refs = {}
        self._pdf_output_auto = True
        self._last_auto_pdf_path = ""
        self._build()
        _lang_cbs.append(self._refresh_lang)
        _register_serial_refresh_callback(self._handle_serial_registry_changed)

    def _build(self):
        title = ctk.CTkLabel(self, text=t("gw_title"), font=ctk.CTkFont(size=18, weight="bold"))
        title.pack(pady=(12, 6))
        self._refs["gw_title"] = title

        desc = ctk.CTkLabel(
            self,
            text=t("gw_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        desc.pack(anchor="w", padx=18, pady=(0, 8))
        self._refs["gw_desc"] = desc

        _sec(self, "gw_section_tools", self._refs)
        self._gw_cmd_title = ctk.CTkLabel(
            self,
            text=t("gw_shutdown_title"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self._gw_cmd_title.pack(anchor="w", padx=18, pady=(2, 2))

        self._gw_cmd_desc = ctk.CTkLabel(
            self,
            text=t("gw_shutdown_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=880,
        )
        self._gw_cmd_desc.pack(anchor="w", padx=18, pady=(0, 6))

        self._gw_cmd_btn = ctk.CTkButton(
            self,
            text=t("gw_shutdown_copy"),
            width=190,
            command=self._copy_shutdown_command,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._gw_cmd_btn.pack(anchor="w", padx=18, pady=(0, 10))

        _sec(self, "gw_section_list", self._refs)
        list_frame = _row(self)
        list_frame.pack(fill="both", expand=False, padx=12, pady=(2, 6))

        self.gateway_list = tk.Listbox(
            list_frame,
            height=8,
            activestyle="none",
            exportselection=False,
            font=("Segoe UI", 10),
        )
        self.gateway_list.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.gateway_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.gateway_list.configure(yscrollcommand=scrollbar.set)

        btn_row = _row(self)
        btn_add = ctk.CTkButton(btn_row, text=t("gw_add"), width=150, command=self._add_gateway)
        btn_add.pack(side="left")
        self._refs["gw_add"] = btn_add
        btn_edit = ctk.CTkButton(btn_row, text=t("gw_edit"), width=160, command=self._edit_gateway)
        btn_edit.pack(side="left", padx=(8, 0))
        self._refs["gw_edit"] = btn_edit
        btn_delete = ctk.CTkButton(btn_row, text=t("gw_delete"), width=170, command=self._delete_gateway)
        btn_delete.pack(side="left", padx=(8, 0))
        self._refs["gw_delete"] = btn_delete

        self._count_lbl = ctk.CTkLabel(self, text=t("gw_count").format(total=0, pages=0), text_color=C_HINT)
        self._count_lbl.pack(anchor="w", padx=18, pady=(2, 10))

        year_row = _row(self)
        lbl_year = ctk.CTkLabel(year_row, text=t("gw_year"), width=LBL_W, anchor="w")
        lbl_year.pack(side="left")
        self._refs["gw_year"] = lbl_year
        self.serial_year_var = tk.StringVar(value=str(datetime.now().year))
        ctk.CTkEntry(year_row, textvariable=self.serial_year_var, width=120).pack(side="left", padx=(4, 0))

        _div(self)
        output_row = _row(self)
        lbl_output = ctk.CTkLabel(output_row, text=t("gw_output"), width=LBL_W, anchor="w")
        lbl_output.pack(side="left")
        self._refs["gw_output"] = lbl_output
        self.pdf_output_var = tk.StringVar()
        ctk.CTkEntry(output_row, textvariable=self.pdf_output_var).pack(side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(output_row, text="...", width=36, command=self._browse_pdf).pack(side="left")

        btn_generate = ctk.CTkButton(
            self,
            text=t("gw_generate"),
            command=self._generate_pdf,
            height=44,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        btn_generate.pack(pady=(16, 6), padx=30, fill="x")
        self._refs["gw_generate"] = btn_generate

        self._status_lbl = ctk.CTkLabel(self, text=t("gw_ready"), text_color=C_HINT)
        self._status_lbl.pack(anchor="w", padx=18, pady=(0, 14))
        self.after(150, self._show_next_gateway_serial_status)

    def _refresh_list(self):
        self.gateway_list.delete(0, tk.END)
        for idx, gateway in enumerate(self._gateways, 1):
            self.gateway_list.insert(
                tk.END,
                f"{idx:02d}. {gateway['serial']}  |  {gateway['alias']}  |  {gateway['mac']}",
            )
        total = len(self._gateways)
        pages = (total + 4) // 5 if total else 0
        self._count_lbl.configure(text=t("gw_count").format(total=total, pages=pages))

    def _refresh_lang(self):
        for key, widget in self._refs.items():
            widget.configure(text=t(key[5:]) if key.startswith("_sec_") else t(key))
        self._gw_cmd_title.configure(text=t("gw_shutdown_title"))
        self._gw_cmd_desc.configure(text=t("gw_shutdown_desc"))
        self._gw_cmd_btn.configure(text=t("gw_shutdown_copy"))
        total = len(self._gateways)
        pages = (total + 4) // 5 if total else 0
        self._count_lbl.configure(text=t("gw_count").format(total=total, pages=pages))
        self._update_auto_pdf_output()
        self._status_lbl.configure(text=t("gw_ready"))

    def _copy_shutdown_command(self):
        self.clipboard_clear()
        self.clipboard_append(self.X4S_LTE_SHUTDOWN_CMD)
        self._status_lbl.configure(text=t("gw_shutdown_copied"))

    def _selected_index(self):
        selected = self.gateway_list.curselection()
        if not selected:
            return None
        return int(selected[0])

    def _add_gateway(self):
        try:
            initial_serial = self._next_gateway_serial()
        except Exception as exc:
            initial_serial = ""
        dlg = GatewayDialog(self, initial_serial=initial_serial)
        self.wait_window(dlg)
        if dlg.result:
            self._gateways.append(dlg.result)
            self._refresh_list()
            self._show_next_gateway_serial_status()

    def _gateway_serial_numbers(self):
        serials = []
        for idx, gateway in enumerate(self._gateways, 1):
            value = str(gateway.get("serial", "")).strip()
            if not value.isdigit():
                raise ValueError(t("gw_error_serial_numeric").format(index=idx, value=value or "-"))
            serials.append(int(value))
        return serials

    def _next_gateway_serial(self):
        repo_last = _next_available_serial("GW", settings=_load_serial_settings())[0] - 1
        local_serials = self._gateway_serial_numbers()
        next_value = max([repo_last, *local_serials] if local_serials else [repo_last]) + 1
        width = max(SERIAL_FAMILY_SETTINGS["GW"]["number_width"], len(str(next_value)))
        return f"{next_value:0{width}d}"

    def _show_next_gateway_serial_status(self):
        try:
            next_value = self._next_gateway_serial()
            self._update_auto_pdf_output()
            self._status_lbl.configure(
                text=t("serial_next_status").format(
                    family=_serial_family_name("GW"),
                    value=next_value,
                )
            )
        except Exception as exc:
            self._status_lbl.configure(text=str(exc))

    def _edit_gateway(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showerror("Error", t("gw_error_select_edit"))
            return
        dlg = GatewayDialog(self, gateway=self._gateways[idx])
        self.wait_window(dlg)
        if dlg.result:
            self._gateways[idx] = dlg.result
            self._refresh_list()
            self.gateway_list.selection_set(idx)
            self._show_next_gateway_serial_status()

    def _delete_gateway(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showerror("Error", t("gw_error_select_delete"))
            return
        del self._gateways[idx]
        self._refresh_list()
        self._show_next_gateway_serial_status()

    def _browse_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Guardar PDF GW como...",
        )
        if path:
            self.pdf_output_var.set(path)
            self._pdf_output_auto = False

    def _suggest_pdf_output_path(self):
        try:
            if self._gateways:
                serials = self._gateway_serial_numbers()
                start_value = str(min(serials))
                end_value = str(max(serials))
            else:
                next_value = self._next_gateway_serial()
                start_value = next_value
                end_value = next_value
            return _default_label_pdf_path("GW", start_value, end_value)
        except Exception:
            return ""

    def _update_auto_pdf_output(self, *_):
        suggested = self._suggest_pdf_output_path()
        current = self.pdf_output_var.get().strip()
        if suggested and (self._pdf_output_auto or not current or current == self._last_auto_pdf_path):
            self.pdf_output_var.set(suggested)
            self._pdf_output_auto = True
        if suggested:
            self._last_auto_pdf_path = suggested

    def _handle_serial_registry_changed(self):
        self.after(0, self._show_next_gateway_serial_status)

    def _generate_pdf(self):
        output_path = self.pdf_output_var.get().strip()
        if not output_path:
            self._update_auto_pdf_output()
            output_path = self.pdf_output_var.get().strip()
        serial_year = self.serial_year_var.get().strip()
        if not output_path:
            messagebox.showerror("Error", t("gw_error_output"))
            return
        if not self._gateways:
            messagebox.showerror("Error", t("gw_error_need_gateway"))
            return
        if not serial_year:
            messagebox.showerror("Error", t("gw_error_need_year"))
            return

        try:
            gateway_serials = self._gateway_serial_numbers()
            self._status_lbl.configure(text=t("gw_status_generating"))
            self.update()
            _make_gateway_pdf(self._gateways, output_path, serial_year)
            settings = _prepare_serial_settings_for_write(self)
            if settings is None:
                return
            self._status_lbl.configure(text=t("serial_repo_sync_after_generate"))
            self.update()
            try:
                _serial_registry_update_gateways(settings, gateway_serials, serial_year)
            except Exception as exc:
                self._status_lbl.configure(text=str(exc))
                _notify_registry_update_failure(self, exc)
                return
            total = len(self._gateways)
            pages = (total + 4) // 5
            width = max(SERIAL_FAMILY_SETTINGS["GW"]["number_width"], len(str(max(gateway_serials))))
            self._status_lbl.configure(text=t("serial_repo_reserved").format(
                family=_serial_family_name("GW"),
                start=f"{min(gateway_serials):0{width}d}",
                end=f"{max(gateway_serials):0{width}d}",
                year=serial_year,
            ))
            _notify_serial_registry_changed()
            messagebox.showinfo(
                "Exito",
                t("gw_pdf_ok").format(total=total, pages=pages, path=output_path),
            )
        except ImportError as exc:
            messagebox.showerror("Libreria faltante", str(exc))
        except PermissionError:
            messagebox.showerror("Error de permisos", "No se pudo escribir el PDF.")
        except Exception as exc:
            self._status_lbl.configure(text=t("gw_status_error"))
            messagebox.showerror("Error inesperado", str(exc))


FW_SECTION_KEYS = {
    "RTU": "fw_section_rtu",
    "TIC12": "fw_section_tic12",
    "FUNGHI": "fw_section_fungi",
    "INSTANTANEI": "fw_section_instantanei",
}

FW_DOWNLOADS = {
    "RTU": [
        {
            "label_key": "fw_item_3c1s_4c",
            "pic": "PIC18LF26K80",
            "firmwares": [("V_1_4.X_11", "V_1_4.X_11_k80.production_MOS.hex")],
        },
        {
            "label_key": "fw_item_1v1c_k40",
            "pic": "PIC18LF26K40",
            "firmwares": [("V_1_4.X_21", "V_1_4.X_21_K40_ABP_OTAA_BREAK.production.hex")],
        },
        {
            "label_key": "fw_item_8v_rev4_blte",
            "pic": "PIC24FJ128GL306",
            "firmwares": [
                ("BLE v1.27", "pic24_Radio_Rev04_02_Marzo_2026_Offset_V1.27.production.BLE.hex"),
                ("NOBLE v1.27", "pic24_Radio_Rev04_02_Marzo_2026_Offset_V1.27.production.NOBLE.hex"),
            ],
        },
        {
            "label_key": "fw_item_loracont",
            "pic": "PIC24FJ128GL302",
            "firmwares": [("1.0.5_REV2.15.06.2026", "CONTATORE_REL.1.0.5_REV2.15.06.2026.production.INFO.hex")],
        },
        {
            "label_key": "fw_item_rn2483",
            "pic": "PIC18LF46K22",
            "firmwares": [("v1.0.6", "RN2483_Parser.production.unified.hex")],
        },
        {
            "label_key": "fw_item_external_protection",
            "pic": "PIC16F15213",
            "firmwares": [("wd_reset_24H", "wd_reset_24H.hex")],
        },
    ],
    "TIC12": [
        {
            "label_key": "fw_item_tic12_control_unit",
            "pic": "PIC18F47Q84",
            "firmwares": [
                ("AC/NOROLL 02.00.02", "Master.15.03.2025.Ver_02.00.02.production.AC.NO_ROLLINGVALVES.hex.hex"),
                ("DC/NOROLL 02.00.02", "Master.15.03.2025.Ver_02.00.02.production.DC.NO_ROLLINGVALVES.hex"),
            ],
        },
        {
            "label_key": "fw_item_expansion_acdc",
            "pic": "PIC16F15324",
            "firmwares": [
                ("AC", "MainEspansione.2.0.0.X.production.AC.hex"),
                ("DC", "MainEspansione.2.0.0.X.production.DC.hex"),
            ],
        },
    ],
    "FUNGHI": [
        {
            "label_key": "fw_item_rev6",
            "pic": "PIC18F15Q40",
            "firmwares": [("V04.00.05", "BTLE_V1.production 04.00.05.hex")],
        },
        {
            "label_key": "fw_item_rev4",
            "pic": "PIC18F15Q40",
            "firmwares": [("V04.00.03", "BTLE_V1.production.04.00.03_HWREV4.hex")],
        },
    ],
    "INSTANTANEI": [
        {
            "label_key": "fw_item_new",
            "pic": "PIC18F65K90",
            "firmwares": [("Istantaneo ultima versionhe", "Istantaneo ultima versionhe.hex")],
        },
        {
            "label_key": "fw_item_old_100l",
            "pic": "PIC16LF1937",
            "firmwares": [("Litri_100", "Litri_100.hex")],
        },
        {
            "label_key": "fw_item_old_1000l",
            "pic": "PIC16LF1937",
            "firmwares": [("Litri_1000", "Litri_1000.hex")],
        },
    ],
}


class FWVersionTab(ctk.CTkScrollableFrame):
    PIC_BUTTON_COLORS = {
        "fg_color": ("#223145", "#223145"),
        "hover_color": ("#2A3B52", "#2A3B52"),
        "text_color": ("#F2F6FB", "#F2F6FB"),
    }
    PIC_BUTTON_ACTIVE_COLORS = {
        "fg_color": ("#1F8F5F", "#1F8F5F"),
        "hover_color": ("#18724C", "#18724C"),
        "text_color": ("#FFFFFF", "#FFFFFF"),
    }
    FIRMWARE_BUTTON_COLORS = {
        "fg_color": ("#89AEDD", "#89AEDD"),
        "hover_color": ("#739DD3", "#739DD3"),
        "text_color": ("#FFFFFF", "#FFFFFF"),
    }

    def __init__(self, master):
        super().__init__(master, fg_color=("white", "#1e1e2e"), corner_radius=0, border_width=0, label_text="")
        self._pic_buttons = []
        self._title_lbl = None
        self._desc_lbl = None
        self._status_lbl = None
        self._section_labels = []
        self._item_labels = []
        self._no_hex_labels = []
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        self._title_lbl = ctk.CTkLabel(self, text=t("fw_title"), font=ctk.CTkFont(size=18, weight="bold"))
        self._title_lbl.pack(pady=(12, 6))

        self._desc_lbl = ctk.CTkLabel(
            self,
            text=t("fw_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._desc_lbl.pack(anchor="w", padx=18, pady=(0, 8))

        for section, rows in FW_DOWNLOADS.items():
            self._add_section(section, rows)

        self._status_lbl = ctk.CTkLabel(self, text=t("fw_status_ready"), text_color=C_HINT)
        self._status_lbl.pack(anchor="w", padx=18, pady=(4, 14))

    def _refresh_lang(self):
        self._title_lbl.configure(text=t("fw_title"))
        self._desc_lbl.configure(text=t("fw_desc"))
        for widget, key in self._section_labels:
            widget.configure(text=t(key))
        for widget, key, pic in self._item_labels:
            widget.configure(text=f"{t(key)} - {pic}")
        for widget in self._no_hex_labels:
            widget.configure(text=t("fw_no_hex"))
        if self._status_lbl is not None:
            self._status_lbl.configure(text=t("fw_status_ready"))

    def _reset_pic_buttons(self):
        for _, button in self._pic_buttons:
            button.configure(**self.PIC_BUTTON_COLORS)

    def _copy_pic(self, pic_name):
        self.clipboard_clear()
        self.clipboard_append(pic_name)
        self._reset_pic_buttons()
        for current_pic, button in self._pic_buttons:
            if current_pic != pic_name:
                continue
            button.configure(**self.PIC_BUTTON_ACTIVE_COLORS)
        self._status_lbl.configure(text=t("fw_status_pic_copied").format(value=pic_name))

    def _save_firmware(self, filename):
        source = _resource(os.path.join("fw", filename))
        if not os.path.isfile(source):
            source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fw", filename)
        if not os.path.isfile(source):
            messagebox.showerror(t("fw_error_missing_title"), t("fw_error_missing_hex").format(filename=filename))
            return

        target = filedialog.asksaveasfilename(
            title=t("fw_save_title"),
            initialfile=filename,
            defaultextension=".hex",
            filetypes=[("HEX", "*.hex"), ("All files", "*.*")],
        )
        if not target:
            return

        shutil.copyfile(source, target)
        self._status_lbl.configure(text=t("fw_status_saved").format(value=os.path.basename(target)))

    def _add_section(self, section, items):
        bar = ctk.CTkFrame(self, fg_color=C_SEC_BG, corner_radius=6, height=30)
        bar.pack(fill="x", padx=18, pady=(10, 4))
        bar.pack_propagate(False)
        section_label = ctk.CTkLabel(
            bar,
            text=t(FW_SECTION_KEYS.get(section, section)),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_SEC_TEXT,
        )
        section_label.pack(side="left", padx=12)
        self._section_labels.append((section_label, FW_SECTION_KEYS.get(section, section)))

        card = ctk.CTkFrame(self, corner_radius=10, fg_color=("white", "#16202d"))
        card.pack(fill="x", padx=18, pady=(0, 10))

        for idx, item in enumerate(items):
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.pack(fill="x", padx=14, pady=6)

            item_label = ctk.CTkLabel(
                row_frame,
                text=f"{t(item['label_key'])} - {item['pic']}",
                anchor="w",
                justify="left",
                wraplength=420,
                font=ctk.CTkFont(size=13),
            )
            item_label.pack(side="left", fill="x", expand=True)
            self._item_labels.append((item_label, item['label_key'], item['pic']))

            pic_button = ctk.CTkButton(
                row_frame,
                text=item["pic"],
                width=160,
                command=lambda p=item["pic"]: self._copy_pic(p),
                font=ctk.CTkFont(size=12, weight="bold"),
                **self.PIC_BUTTON_COLORS,
            )
            pic_button._dm_style_locked = True
            pic_button.pack(side="right", padx=(8, 0))
            self._pic_buttons.append((item["pic"], pic_button))

            for fw_label, fw_file in reversed(item["firmwares"]):
                fw_button = ctk.CTkButton(
                    row_frame,
                    text=fw_label,
                    width=150,
                    command=lambda f=fw_file: self._save_firmware(f),
                    font=ctk.CTkFont(size=11, weight="bold"),
                    **self.FIRMWARE_BUTTON_COLORS,
                )
                fw_button._dm_style_locked = True
                fw_button.pack(side="right", padx=(8, 0))

            if not item["firmwares"]:
                no_hex_label = ctk.CTkLabel(
                    row_frame,
                    text=t("fw_no_hex"),
                    text_color=C_HINT,
                    font=ctk.CTkFont(size=11),
                )
                no_hex_label.pack(side="right", padx=(8, 0))
                self._no_hex_labels.append(no_hex_label)

            if idx < len(items) - 1:
                ctk.CTkFrame(card, height=1, fg_color=C_DIV).pack(fill="x", padx=12, pady=(0, 0))


class SerialTab(ctk.CTkScrollableFrame):
    PACKAGE_FILE = "Hyperterminal.zip"
    TERMINAL_ANTONIO_FILE = "APP_BLE_SERIAL__25_01_2026_wx.zip"

    def __init__(self, master):
        super().__init__(master, fg_color=C_BODY_BG, corner_radius=0, border_width=0, label_text="")
        self._serial_settings = _load_serial_settings()
        self._title_lbl = None
        self._desc_lbl = None
        self._section_lbl = None
        self._tool_title_lbl = None
        self._tool_desc_lbl = None
        self._save_btn = None
        self._tool2_title_lbl = None
        self._tool2_desc_lbl = None
        self._save2_btn = None
        self._repo_title_lbl = None
        self._repo_desc_lbl = None
        self._repo_refs = {}
        self._repo_path_var = tk.StringVar(value=self._serial_settings.get("registry_url", DEFAULT_SERIAL_SETTINGS["registry_url"]))
        self._repo_branch_var = tk.StringVar(value=self._serial_settings.get("branch", "main"))
        self._repo_file_var = tk.StringVar(value=self._serial_settings.get("api_url", DEFAULT_SERIAL_SETTINGS["api_url"]))
        self._repo_token_var = tk.StringVar(value=self._serial_settings.get("token", ""))
        self._repo_station_var = tk.StringVar(value=self._serial_settings.get("station_name", DEFAULT_SERIAL_SETTINGS["station_name"]))
        self._family_vars = {family: tk.StringVar(value="0") for family in SERIAL_FAMILY_ORDER}
        self._family_labels = {}
        self._registry_status_lbl = None
        self._status_lbl = None
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        self._title_lbl = ctk.CTkLabel(self, text=t("serial_title"), font=ctk.CTkFont(size=18, weight="bold"))
        self._title_lbl.pack(pady=(12, 6))

        self._desc_lbl = ctk.CTkLabel(
            self,
            text=t("serial_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._desc_lbl.pack(anchor="w", padx=18, pady=(0, 10))

        bar = ctk.CTkFrame(self, fg_color=C_SEC_BG, corner_radius=6, height=30)
        bar.pack(fill="x", padx=18, pady=(8, 4))
        bar.pack_propagate(False)
        self._section_lbl = ctk.CTkLabel(
            bar,
            text=t("serial_section_tools"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_SEC_TEXT,
        )
        self._section_lbl.pack(side="left", padx=12)

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=C_CARD_BG, border_width=1, border_color=C_CARD_BORDER)
        card.pack(fill="x", padx=18, pady=(0, 10))

        self._tool_title_lbl = ctk.CTkLabel(
            card,
            text=t("serial_hyperterminal_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self._tool_title_lbl.pack(anchor="w", padx=14, pady=(14, 4))

        self._tool_desc_lbl = ctk.CTkLabel(
            card,
            text=t("serial_hyperterminal_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._tool_desc_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        self._save_btn = ctk.CTkButton(
            card,
            text=t("serial_hyperterminal_button"),
            width=220,
            command=self._save_hyperterminal,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._save_btn.pack(anchor="w", padx=14, pady=(0, 14))

        ctk.CTkFrame(card, height=1, fg_color=C_DIV).pack(fill="x", padx=12, pady=(0, 0))

        self._tool2_title_lbl = ctk.CTkLabel(
            card,
            text=t("serial_terminal_antonio_title"),
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self._tool2_title_lbl.pack(anchor="w", padx=14, pady=(14, 4))

        self._tool2_desc_lbl = ctk.CTkLabel(
            card,
            text=t("serial_terminal_antonio_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._tool2_desc_lbl.pack(anchor="w", padx=14, pady=(0, 10))

        self._save2_btn = ctk.CTkButton(
            card,
            text=t("serial_terminal_antonio_button"),
            width=260,
            command=lambda: self._save_package(self.TERMINAL_ANTONIO_FILE),
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._save2_btn.pack(anchor="w", padx=14, pady=(0, 14))

        repo_bar = ctk.CTkFrame(self, fg_color=C_SEC_BG, corner_radius=6, height=30)
        repo_bar.pack(fill="x", padx=18, pady=(8, 4))
        repo_bar.pack_propagate(False)
        self._repo_title_lbl = ctk.CTkLabel(
            repo_bar,
            text=t("serial_repo_title"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_SEC_TEXT,
        )
        self._repo_title_lbl.pack(side="left", padx=12)

        self._repo_desc_lbl = ctk.CTkLabel(
            self,
            text=t("serial_repo_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._repo_desc_lbl.pack(anchor="w", padx=18, pady=(0, 8))

        family_card = ctk.CTkFrame(self, corner_radius=16, fg_color=C_CARD_BG, border_width=1, border_color=C_CARD_BORDER)
        family_card.pack(fill="x", padx=18, pady=(10, 8))
        self._family_save_buttons = {}
        for idx, family in enumerate(SERIAL_FAMILY_ORDER):
            row = ctk.CTkFrame(family_card, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=6)
            lbl = ctk.CTkLabel(
                row,
                text=_serial_family_name(family),
                width=180,
                anchor="w",
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            lbl.pack(side="left")
            self._family_labels[family] = lbl
            ctk.CTkEntry(row, textvariable=self._family_vars[family], width=120).pack(side="left", padx=(4, 10))
            btn = ctk.CTkButton(
                row,
                text=t("serial_repo_save_value").format(family=_serial_family_name(family)),
                width=220,
                command=lambda fam=family: self._save_single_family(fam),
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            btn.pack(side="left", padx=(6, 0))
            self._family_save_buttons[family] = btn
            if idx < len(SERIAL_FAMILY_ORDER) - 1:
                ctk.CTkFrame(family_card, height=1, fg_color=C_DIV).pack(fill="x", padx=12)

        self._save_all_btn = ctk.CTkButton(
            self,
            text=t("serial_repo_save_all"),
            width=240,
            command=self._save_all_families,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._save_all_btn.pack(anchor="w", padx=18, pady=(0, 8))

        self._registry_status_lbl = ctk.CTkLabel(self, text=t("serial_repo_ready"), text_color=C_HINT)
        self._status_lbl = ctk.CTkLabel(self, text=t("serial_status"), text_color=C_HINT)
        self._load_registry_values(_default_serial_registry())
        self.after(150, self._auto_load_registry)

    def _repo_field(self, key, variable, width=None, masked=False):
        row = _row(self)
        lbl = ctk.CTkLabel(row, text=t(key), width=LBL_W, anchor="w")
        lbl.pack(side="left")
        self._repo_refs[key] = lbl
        entry_kwargs = {"show": "*"} if masked else {}
        if width:
            ctk.CTkEntry(row, textvariable=variable, width=width, **entry_kwargs).pack(side="left", padx=(4, 0))
        else:
            ctk.CTkEntry(row, textvariable=variable, **entry_kwargs).pack(side="left", fill="x", expand=True, padx=(4, 4))

    def _save_package(self, filename):
        source = _resource(filename)
        if not os.path.isfile(source):
            source = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        if not os.path.isfile(source):
            messagebox.showerror(
                t("serial_error_title"),
                t("serial_error_missing").format(filename=filename),
            )
            return

        target = filedialog.asksaveasfilename(
            title=t("serial_save_title"),
            initialfile=filename,
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip"), ("All files", "*.*")],
        )
        if not target:
            return

        shutil.copyfile(source, target)
        self._status_lbl.configure(text=t("serial_status_saved").format(value=os.path.basename(target)))

    def _save_hyperterminal(self):
        self._save_package(self.PACKAGE_FILE)

    
    def _collect_settings(self):
        current = dict(self._serial_settings or _load_serial_settings())
        return {
            "registry_url": DEFAULT_SERIAL_SETTINGS["registry_url"],
            "branch": str(current.get("branch", "")).strip() or "main",
            "api_url": DEFAULT_SERIAL_SETTINGS["api_url"],
            "token": (
                str(current.get("token", "")).strip()
                or _load_embedded_serial_token()
                or os.environ.get("DEVICE_MANAGER_GITHUB_TOKEN", "").strip()
            ),
            "station_name": os.environ.get("COMPUTERNAME", str(current.get("station_name", "")).strip() or DEFAULT_SERIAL_SETTINGS["station_name"]),
        }

    def _save_repo_settings(self):
        self._serial_settings = self._collect_settings()
        if self._registry_status_lbl is not None:
            self._registry_status_lbl.configure(text=t("serial_repo_ready"))

    def _load_registry_values(self, registry):
        registry = _normalize_serial_registry(registry)
        for family in SERIAL_FAMILY_ORDER:
            self._family_vars[family].set(str(registry["families"][family]["last_serial"]))
        self._status_lbl.configure(text=t("serial_status"))

    def _auto_load_registry(self):
        try:
            self._serial_settings = self._collect_settings()
            registry = _serial_registry_fetch_cached(settings=self._serial_settings, force=True)
            self._load_registry_values(registry)
            self._registry_status_lbl.configure(text=t("serial_repo_synced"))
        except Exception as exc:
            self._registry_status_lbl.configure(text=str(exc))

    def _build_updated_registry(self, families):
        registry = _serial_registry_fetch(self._serial_settings)
        station = self._serial_settings.get("station_name", DEFAULT_SERIAL_SETTINGS["station_name"])
        for family in families:
            entry = registry["families"][family]
            value = int(self._family_vars[family].get().strip() or "0")
            width = SERIAL_FAMILY_SETTINGS[family]["number_width"]
            entry["last_serial"] = value
            entry["updated_by"] = station
            entry["updated_at"] = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
            entry["last_count"] = 0
            entry["last_range"] = f"{value:0{width}d}-{value:0{width}d}"
            registry["families"][family] = entry
        return registry

    def _save_single_family(self, family):
        try:
            if not _prompt_serial_password(self):
                return
            self._save_repo_settings()
            ensured = _ensure_serial_token(self, dict(self._serial_settings))
            if ensured is None:
                return
            self._serial_settings = ensured
            registry = self._build_updated_registry([family])
            _serial_registry_push(self._serial_settings, registry, f"Manual serial registry update: {family}")
            self._load_registry_values(_serial_registry_fetch_cached(settings=self._serial_settings, force=True))
            self._registry_status_lbl.configure(
                text=t("serial_repo_value_saved").format(
                    family=_serial_family_name(family),
                    value=self._family_vars[family].get().strip() or "0",
                )
            )
            _notify_serial_registry_changed()
            messagebox.showinfo(
                t("serial_repo_saved_title"),
                t("serial_repo_value_saved").format(
                    family=_serial_family_name(family),
                    value=self._family_vars[family].get().strip() or "0",
                ),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(t("serial_error_title"), str(exc))

    def _save_all_families(self):
        try:
            if not _prompt_serial_password(self):
                return
            self._save_repo_settings()
            ensured = _ensure_serial_token(self, dict(self._serial_settings))
            if ensured is None:
                return
            self._serial_settings = ensured
            registry = self._build_updated_registry(SERIAL_FAMILY_ORDER)
            _serial_registry_push(self._serial_settings, registry, "Manual serial registry update: all families")
            self._load_registry_values(_serial_registry_fetch_cached(settings=self._serial_settings, force=True))
            self._registry_status_lbl.configure(text=t("serial_repo_all_saved"))
            _notify_serial_registry_changed()
            messagebox.showinfo(
                t("serial_repo_saved_title"),
                t("serial_repo_all_saved"),
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror(t("serial_error_title"), str(exc))

    def _refresh_lang(self):
        self._title_lbl.configure(text=t("serial_title"))
        self._desc_lbl.configure(text=t("serial_desc"))
        self._section_lbl.configure(text=t("serial_section_tools"))
        self._tool_title_lbl.configure(text=t("serial_hyperterminal_title"))
        self._tool_desc_lbl.configure(text=t("serial_hyperterminal_desc"))
        self._save_btn.configure(text=t("serial_hyperterminal_button"))
        self._tool2_title_lbl.configure(text=t("serial_terminal_antonio_title"))
        self._tool2_desc_lbl.configure(text=t("serial_terminal_antonio_desc"))
        self._save2_btn.configure(text=t("serial_terminal_antonio_button"))
        self._repo_title_lbl.configure(text=t("serial_repo_title"))
        self._repo_desc_lbl.configure(text=t("serial_repo_desc"))
        for key, widget in self._repo_refs.items():
            widget.configure(text=t(key))
        for family, widget in self._family_labels.items():
            widget.configure(text=_serial_family_name(family))
        for family, button in self._family_save_buttons.items():
            button.configure(text=t("serial_repo_save_value").format(family=_serial_family_name(family)))
        self._save_all_btn.configure(text=t("serial_repo_save_all"))
        self._registry_status_lbl.configure(text=t("serial_repo_ready"))
        self._status_lbl.configure(text=t("serial_status"))


class ManualsTab(ctk.CTkScrollableFrame):
    MANUAL_GROUPS = [
        (
            "manuals_group_itic",
            [
                os.path.join("Manuali", "ITIC", "I-TIC1 manuale utente rev.0.3 ITA.pdf"),
                os.path.join("Manuali", "ITIC", "I-TIC1 user manual rev.0.3 ENG.pdf"),
            ],
        ),
        (
            "manuals_group_loracont",
            [
                os.path.join("Manuali", "LoraCont", "Guida_collegamento_RTU_LoraCont_1C.pdf"),
                os.path.join("Manuali", "LoraCont", "Guia_conexion_RTU_LoraCont_1C_ES.pdf"),
            ],
        ),
        (
            "manuals_group_hydronet",
            [
                os.path.join("Manuali", "Piattaforma Hydronet", "Manuale_Hydronet_Generico.pdf"),
            ],
        ),
        (
            "manuals_group_tic12",
            [
                os.path.join("Manuali", "TIC12", "Centralina Controlavaggio TIC12 - Istruzioni operative e connessioni - rev 0.3c ITA-ENG tuv-nord.pdf"),
            ],
        ),
    ]

    def __init__(self, master):
        super().__init__(master, fg_color=C_BODY_BG, corner_radius=0, border_width=0, label_text="")
        self._title_lbl = None
        self._desc_lbl = None
        self._section_lbl = None
        self._group_labels = {}
        self._item_labels = []
        self._save_buttons = []
        self._status_lbl = None
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        self._title_lbl = ctk.CTkLabel(self, text=t("manuals_title"), font=ctk.CTkFont(size=18, weight="bold"))
        self._title_lbl.pack(pady=(12, 6))

        self._desc_lbl = ctk.CTkLabel(
            self,
            text=t("manuals_desc"),
            text_color=C_HINT,
            justify="left",
            wraplength=900,
        )
        self._desc_lbl.pack(anchor="w", padx=18, pady=(0, 10))

        bar = ctk.CTkFrame(self, fg_color=C_SEC_BG, corner_radius=6, height=30)
        bar.pack(fill="x", padx=18, pady=(8, 4))
        bar.pack_propagate(False)
        self._section_lbl = ctk.CTkLabel(
            bar,
            text=t("manuals_section_library"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=C_SEC_TEXT,
        )
        self._section_lbl.pack(side="left", padx=12)

        card = ctk.CTkFrame(self, corner_radius=16, fg_color=C_CARD_BG, border_width=1, border_color=C_CARD_BORDER)
        card.pack(fill="x", padx=18, pady=(0, 10))

        for group_key, files in self.MANUAL_GROUPS:
            group_frame = ctk.CTkFrame(card, fg_color=C_SEC_BG, corner_radius=14, border_width=1, border_color=C_CARD_BORDER)
            group_frame.pack(fill="x", padx=14, pady=10)

            title = ctk.CTkLabel(
                group_frame,
                text=t(group_key),
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=C_TEXT,
            )
            title.pack(anchor="w", padx=14, pady=(12, 6))
            self._group_labels[group_key] = title

            for relpath in files:
                row = ctk.CTkFrame(group_frame, fg_color="transparent")
                row.pack(fill="x", padx=14, pady=(0, 10))
                filename = os.path.basename(relpath)
                item = ctk.CTkLabel(
                    row,
                    text=filename,
                    text_color=C_TEXT,
                    anchor="w",
                    justify="left",
                    wraplength=680,
                )
                item.pack(side="left", fill="x", expand=True)
                self._item_labels.append(item)
                btn = ctk.CTkButton(
                    row,
                    text=t("manuals_button_save"),
                    width=120,
                    command=lambda p=relpath: self._save_manual(p),
                    font=ctk.CTkFont(size=12, weight="bold"),
                )
                btn.pack(side="right", padx=(12, 0))
                self._save_buttons.append(btn)

        self._status_lbl = ctk.CTkLabel(card, text="", text_color=C_HINT, anchor="w")
        self._status_lbl.pack(fill="x", padx=16, pady=(0, 14))

    def _save_manual(self, relative_path):
        source = _resource(relative_path)
        if not os.path.isfile(source):
            source = os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
        filename = os.path.basename(relative_path)
        if not os.path.isfile(source):
            messagebox.showerror(t("serial_error_title"), t("manuals_missing").format(name=filename), parent=self)
            return

        target = filedialog.asksaveasfilename(
            title=t("manuals_save_title"),
            initialfile=filename,
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        )
        if not target:
            return

        shutil.copyfile(source, target)
        self._status_lbl.configure(text=t("manuals_saved").format(name=os.path.basename(target)))
        messagebox.showinfo(t("manuals_title"), t("manuals_saved").format(name=os.path.basename(target)), parent=self)

    def _refresh_lang(self):
        self._title_lbl.configure(text=t("manuals_title"))
        self._desc_lbl.configure(text=t("manuals_desc"))
        self._section_lbl.configure(text=t("manuals_section_library"))
        for group_key, widget in self._group_labels.items():
            widget.configure(text=t(group_key))
        for button in self._save_buttons:
            button.configure(text=t("manuals_button_save"))


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        root.title("Device Manager - TECNIDRO")
        root.configure(fg_color=C_APP_BG)
        self._window_icon = None
        try:
            icon_path = _resource("tecnidro_app_icon.png")
            self._window_icon = tk.PhotoImage(file=icon_path)
            root.iconphoto(True, self._window_icon)
        except Exception:
            pass
        # Centrar en pantalla al 90% del monitor disponible (mÃ¡x 1200Ã—960)
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w  = min(int(sw * 0.90), 1200)
        h  = min(int(sh * 0.90), 960)
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(820, 640)

        self._nav_buttons = {}
        self._views = {}
        self._rtu_views = {}
        self._active_section = None
        self._active_rtu_section = "Proyecto"
        self._section_meta = {
            "RTU": ("RTU Workspace", "CSV, JSON, progetto completo ed etichette in un unico flusso."),
            "GW": ("Gateway", "Gestione etichette Gateway e strumenti rapidi per X4S LTE."),
            "I-TIC": ("I-TIC", "Etichette e seriali per dispositivi I-TIC."),
            "TIC12": ("TIC12", "Etichette, seriali e stampa per TIC12."),
            "FW Version": ("FW Version", "Libreria firmware con copia PIC ed export HEX."),
            "Serial": ("Serial Registry", "Controllo centralizzato dei seriali via GitHub."),
            "Manuales": ("header_manuals_title", "header_manuals_subtitle"),
            "Language": ("header_language_title", "header_language_subtitle"),
        }
        self._nav_text_keys = {
            "Manuales": "nav_manuals",
            "Language": "nav_language",
        }

        shell = ctk.CTkFrame(root, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=14, pady=14)

        workspace = ctk.CTkFrame(shell, fg_color=C_SHELL_BG, corner_radius=28, border_width=1, border_color=C_CARD_BORDER)
        workspace.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(workspace, fg_color=("#dde5ef", "#111823"), corner_radius=24, width=240)
        sidebar.pack(side="left", fill="y", padx=(14, 10), pady=14)
        sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=18, pady=(18, 18))
        img_l, img_d, dw, dh = _make_logo_images(display_h=40)
        if img_l and img_d:
            logo_ctk = ctk.CTkImage(light_image=img_l, dark_image=img_d, size=(dw, dh))
            self._logo_ctk = logo_ctk
            ctk.CTkLabel(brand, image=logo_ctk, text="", fg_color="transparent").pack(anchor="w")
        ctk.CTkLabel(
            brand,
            text="Device Manager",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=C_TEXT,
        ).pack(anchor="w", pady=(12, 0))
        ctk.CTkLabel(
            brand,
            text="TECNIDRO SRL",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        nav_wrap = ctk.CTkFrame(sidebar, fg_color="transparent")
        nav_wrap.pack(fill="x", padx=14, pady=(4, 10))
        for name in ("RTU", "GW", "I-TIC", "TIC12", "FW Version", "Serial", "Manuales", "Language"):
            btn = ctk.CTkButton(
                nav_wrap,
                text=name,
                anchor="w",
                height=44,
                corner_radius=14,
                fg_color="transparent",
                hover_color=C_ACCENT_SOFT,
                text_color=C_TEXT,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda n=name: self._show_section(n),
            )
            btn.pack(fill="x", pady=4)
            self._nav_buttons[name] = btn

        side_footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        side_footer.pack(side="bottom", fill="x", padx=18, pady=18)
        badge = ctk.CTkFrame(side_footer, fg_color=C_ACCENT_SOFT, corner_radius=14)
        badge.pack(anchor="w")
        ctk.CTkLabel(
            badge,
            text=f"Versione {APP_VERSION}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C_SEC_TEXT,
        ).pack(padx=12, pady=8)

        main_area = ctk.CTkFrame(workspace, fg_color="transparent")
        main_area.pack(side="left", fill="both", expand=True, padx=(0, 14), pady=14)

        topbar = ctk.CTkFrame(main_area, fg_color=C_HDR_BG, corner_radius=22, height=92, border_width=1, border_color=C_CARD_BORDER)
        topbar.pack(fill="x", pady=(0, 12))
        topbar.pack_propagate(False)

        title_box = ctk.CTkFrame(topbar, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True, padx=24, pady=18)
        self._header_title = ctk.CTkLabel(
            title_box,
            text="",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=C_HDR_TEXT,
        )
        self._header_title.pack(anchor="w")
        self._header_subtitle = ctk.CTkLabel(
            title_box,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=C_HINT,
        )
        self._header_subtitle.pack(anchor="w", pady=(4, 0))

        self._rtu_segment_var = tk.StringVar(value="Proyecto")
        self._rtu_segment = ctk.CTkSegmentedButton(
            topbar,
            values=["Proyecto", "CSV", "JSON", "Etichette"],
            variable=self._rtu_segment_var,
            command=self._show_rtu_section,
            fg_color=C_TAB_BG,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_TAB_BG,
            unselected_hover_color=C_ACCENT_SOFT,
            text_color=C_TAB_TEXT,
            corner_radius=14,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=36,
        )

        content_host = ctk.CTkFrame(main_area, fg_color=C_CARD_BG, corner_radius=24, border_width=1, border_color=C_CARD_BORDER)
        content_host.pack(fill="both", expand=True)

        for section in ("RTU", "GW", "I-TIC", "TIC12", "FW Version", "Serial", "Manuales", "Language"):
            frame = ctk.CTkFrame(content_host, fg_color="transparent")
            self._views[section] = frame

        # RTU workspace with subnavigation
        rtu_shell = self._views["RTU"]
        self._rtu_content_host = ctk.CTkFrame(rtu_shell, fg_color="transparent")
        self._rtu_content_host.pack(fill="both", expand=True)
        for sub in ("Proyecto", "CSV", "JSON", "Etichette"):
            subframe = ctk.CTkFrame(self._rtu_content_host, fg_color="transparent")
            self._rtu_views[sub] = subframe
        ProjectTab(self._rtu_views["Proyecto"]).pack(fill="both", expand=True)
        CSVTab(self._rtu_views["CSV"]).pack(fill="both", expand=True)
        JSONTab(self._rtu_views["JSON"]).pack(fill="both", expand=True)
        EtichetteTab(self._rtu_views["Etichette"]).pack(fill="both", expand=True)

        GatewayTab(self._views["GW"]).pack(fill="both", expand=True)
        TICLabelTab(self._views["I-TIC"], product_name="I-TIC 1V", title_key="itic_title").pack(fill="both", expand=True)
        TICLabelTab(self._views["TIC12"], product_name="TIC12", title_key="tic12_title").pack(fill="both", expand=True)
        FWVersionTab(self._views["FW Version"]).pack(fill="both", expand=True)
        SerialTab(self._views["Serial"]).pack(fill="both", expand=True)
        ManualsTab(self._views["Manuales"]).pack(fill="both", expand=True)
        LangTab(self._views["Language"]).pack(fill="both", expand=True)

        self._status_bar = ctk.CTkFrame(main_area, corner_radius=18, height=34, fg_color=C_BAR_BG, border_width=1, border_color=C_CARD_BORDER)
        self._status_bar.pack(fill="x", pady=(12, 0))
        self._status_bar.pack_propagate(False)
        ctk.CTkLabel(
            self._status_bar,
            text=f"  Device Manager · Tecnidro · v{APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color=C_BAR_TEXT,
        ).pack(side="left", padx=8)
        ctk.CTkLabel(
            self._status_bar,
            text="by Manuel Rodriguez  ",
            font=ctk.CTkFont(size=10),
            text_color=C_BAR_TEXT,
        ).pack(side="right", padx=8)

        _apply_premium_theme(main_area)
        _lang_cbs.append(self._refresh_lang)
        self._refresh_lang()
        self._show_section("RTU")

        if _load_update_settings().get("auto_check") and str(_load_update_settings().get("manifest_url", "")).strip():
            root.after(1500, lambda: check_for_updates(root, interactive=False))

    def _show_section(self, section_name):
        if section_name not in self._views:
            return
        for name, frame in self._views.items():
            frame.pack_forget()
            btn = self._nav_buttons.get(name)
            if btn is not None:
                btn.configure(
                    fg_color="transparent",
                    hover_color=C_ACCENT_SOFT,
                    text_color=C_TEXT,
                )
        self._views[section_name].pack(fill="both", expand=True, padx=14, pady=14)
        selected_btn = self._nav_buttons.get(section_name)
        if selected_btn is not None:
            selected_btn.configure(
                fg_color=C_ACCENT,
                hover_color=C_ACCENT_HOVER,
                text_color=("white", "#f7fbff"),
            )
        self._active_section = section_name
        title, subtitle = self._section_header(section_name)
        self._header_title.configure(text=title)
        self._header_subtitle.configure(text=subtitle)
        if section_name == "RTU":
            self._rtu_segment.pack(side="right", padx=22, pady=26)
            self._show_rtu_section(self._active_rtu_section)
        else:
            self._rtu_segment.pack_forget()

    def _show_rtu_section(self, section_name):
        self._active_rtu_section = section_name
        if self._active_section != "RTU":
            return
        for name, frame in self._rtu_views.items():
            frame.pack_forget()
        frame = self._rtu_views.get(section_name)
        if frame is not None:
            frame.pack(fill="both", expand=True)
        self._rtu_segment_var.set(section_name)

    def _section_header(self, section_name):
        title, subtitle = self._section_meta.get(section_name, (section_name, ""))
        if title in TRANSLATIONS[_cur_lang[0]]:
            title = t(title)
        if subtitle in TRANSLATIONS[_cur_lang[0]]:
            subtitle = t(subtitle)
        return title, subtitle

    def _refresh_lang(self):
        for name, btn in self._nav_buttons.items():
            btn.configure(text=t(self._nav_text_keys.get(name, name)))
        if self._active_section:
            title, subtitle = self._section_header(self._active_section)
            self._header_title.configure(text=title)
            self._header_subtitle.configure(text=subtitle)


def main():
    root = ctk.CTk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()

