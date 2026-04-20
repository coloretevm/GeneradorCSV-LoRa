import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
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

APP_VERSION = "1.45"
APP_BUILD_NAME = "Device_Manager_v45"
UPDATE_SETTINGS_FILE = "update_settings.json"
DEFAULT_UPDATE_SETTINGS = {
    "manifest_url": "",
    "auto_check": True,
}

# ─────────────────────────────────────────────────────────────────────────────
def _resource(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _runtime_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _update_settings_path():
    return os.path.join(_runtime_dir(), UPDATE_SETTINGS_FILE)


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
    except Exception:
        pass
    return settings


def _save_update_settings(settings):
    path = _update_settings_path()
    merged = dict(DEFAULT_UPDATE_SETTINGS)
    merged.update(settings or {})
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)


def _parse_version(value):
    parts = []
    for chunk in str(value).strip().replace("-", ".").split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def _download_json(url):
    req = urlrequest.Request(url, headers={"User-Agent": f"{APP_BUILD_NAME}/{APP_VERSION}"})
    with urlrequest.urlopen(req, timeout=12) as response:
        return json.loads(response.read().decode("utf-8"))


def _download_binary(url, target_path):
    req = urlrequest.Request(url, headers={"User-Agent": f"{APP_BUILD_NAME}/{APP_VERSION}"})
    with urlrequest.urlopen(req, timeout=60) as response, open(target_path, "wb") as fh:
        shutil.copyfileobj(response, fh)


def _launch_windows_updater(downloaded_exe, current_exe):
    bat_path = os.path.join(tempfile.gettempdir(), "generadorcsv_update.bat")
    script = (
        "@echo off\n"
        "ping 127.0.0.1 -n 4 > nul\n"
        f'copy /Y "{downloaded_exe}" "{current_exe}" > nul\n'
        f'start "" "{current_exe}"\n'
        f'del "{downloaded_exe}"\n'
        'del "%~f0"\n'
    )
    with open(bat_path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(script)
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=creation_flags)

def _make_logo_images(display_h=52):
    """Carga logo.png a alta resolución y devuelve (img_light, img_dark).
    Trabaja en 2× para HiDPI y usa LANCZOS para suavizado óptimo.
    Light: fondo blanco removido, colores originales.
    Dark:  mismos pixels recoloreados a blanco puro, fondo transparente.
    """
    try:
        src = Image.open(_resource("logo.png")).convert("RGBA")
        # Escalar a 2× resolución interna para HiDPI (CTkImage lo gestiona)
        w, h = src.size
        render_h = display_h * 2
        render_w = int(w * render_h / h)
        src = src.resize((render_w, render_h), Image.LANCZOS)

        pixels = list(src.getdata())
        light_px, dark_px = [], []
        for r, g, b, a in pixels:
            lum = 0.299*r + 0.587*g + 0.114*b   # luminancia perceptual
            if lum > 220 and a > 200:            # fondo blanco → transparente
                light_px.append((255, 255, 255, 0))
                dark_px.append((0, 0, 0, 0))
            else:
                light_px.append((r, g, b, a))          # color original
                dark_px.append((255, 255, 255, a))      # blanco para dark

        img_light = Image.new("RGBA", src.size)
        img_light.putdata(light_px)
        img_dark = Image.new("RGBA", src.size)
        img_dark.putdata(dark_px)
        # display_size en píxeles lógicos (CTkImage usará el doble en HiDPI)
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

# ═════════════════════════════════════════════════════════════════════════════
# Traducciones
# ═════════════════════════════════════════════════════════════════════════════
TRANSLATIONS = {
    'es': {
        'csv_title':     'Generador de CSV — Dispositivos LoRa',
        'sec_name':      'Nombre del dispositivo',
        'lbl_prefix':    'Prefijo:',
        'lbl_from':      'Desde:',
        'lbl_to':        'Hasta:',
        'prev_error':    "['hasta' debe ser ≥ 'desde']",
        'prev_fmt':      '→ {n} dispositivos:  {a}  …  {b}',
        'sec_lora':      'Configuración de red LoRa',
        'lbl_model':     'Modelo (Model):',
        'lbl_deveui':    'DevEUI inicial (16 hex):',
        'lbl_devaddr_i': 'DevAddr: extraído automáticamente de los últimos 8 caracteres del DevEUI',
        'lbl_newskey':   'NewSKey (32 hex):',
        'lbl_appskey':   'AppSKey (32 hex):',
        'sec_coords':    'Coordenadas (mismas para todos)',
        'lbl_lat':       'Latitud:',
        'lbl_lon':       'Longitud:',
        'sec_extra':     'Parámetros adicionales',
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'Archivo de salida:',
        'btn_gen_csv':   'Generar CSV',
        'lbl_ready':     'Listo.',
        'labels_title':  'Generador de Etichette — PDF A4',
        'sec_opt1':      'Opción 1 – Cargar desde CSV generado',
        'lbl_csv_file':  'Archivo CSV:',
        'btn_load':      'Cargar',
        'sec_opt2':      'Opción 2 – Ingresar datos manualmente',
        'lbl_name_pfx':  'Prefijo nombre:',
        'lbl_deveui_m':  'DevEUI inicial (16 hex):',
        'sec_serial':    'Serial number',
        'lbl_ser_start': 'Serial inicio:',
        'lbl_year':      'Año:',
        'lbl_ser_fmt':   'Formato en la etiqueta: 04906/2026  →  04907/2026  →  ...',
        'sec_opts':      'Opciones de la etiqueta',
        'chk_bt':        'Incluir fila BLUETOOTH  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'Etichetta RTU in tubo  (header TECNIDRO / HYDRONET-RTU, sin Bluetooth)',
        'chk_lc':        'Etichetta RTU LORACONT  (23mm × 87mm, header TECNIDRO / LORACONT-RTU)',
        'lbl_pdf_out':   'Archivo PDF de salida:',
        'btn_gen_pdf':   'Generar PDF Etichette',
        'lang_title':    'Seleccionar idioma',
        'lang_sub':      'Idioma de la interfaz:',
        'theme_label':   'Tema de la aplicación:',
        'theme_dark':    '🌙  Oscuro',
        'theme_light':   '☀  Claro',
        'upd_title':     'Actualizaciones',
        'upd_version':   'Versión actual:',
        'upd_source':    'URL del manifiesto:',
        'upd_auto':      'Buscar actualizaciones al abrir',
        'upd_save':      'Guardar configuración',
        'upd_check':     'Buscar actualizaciones',
        'upd_saved':     'Configuración de actualización guardada.',
        'upd_status_idle':'Configura una URL de manifiesto para activar las actualizaciones online.',
        'upd_status_checking':'Comprobando actualizaciones...',
        'upd_status_latest':'Ya tienes la versión más reciente.',
        'upd_status_available':'Nueva versión disponible: {version}',
        'upd_status_disabled':'Las actualizaciones online están desactivadas.',
        'upd_error_title':'Actualización',
        'upd_error_no_url':'Escribe la URL del manifiesto de actualización.',
        'upd_error_bad_manifest':'El manifiesto no es válido o le faltan datos.',
        'upd_error_network':'No se pudo comprobar la actualización.\n{error}',
        'upd_error_download':'No se pudo descargar la actualización.\n{error}',
        'upd_confirm_title':'Nueva versión disponible',
        'upd_confirm_body':'Versión actual: {current}\nNueva versión: {latest}\n\n¿Quieres descargarla e instalarla ahora?',
        'upd_download_title':'Guardar actualización como...',
        'upd_success_restart':'La actualización se descargó. El programa se cerrará para instalar la nueva versión.',
        'json_title':    'Generador de archivos JSON',
        'sec_valve':     'Tipo de válvula',
        'sec_allarme':   'Allarme Sportello',
        'sec_adc':       'ADC',
        'sec_deveui_j':  'Parámetros de radio',
        'lbl_deveui_j':  'DevEUI inicial (16 hex):',
        'lbl_devaddr_j': 'DevAddr: extraído automáticamente de los últimos 8 caracteres del DevEUI',
        'sec_send_params': 'Parámetros de envío',
        'lbl_sendinterval':'Send Interval (ms):',
        'sec_out_json':  'Carpeta de salida',
        'lbl_out_folder':'Carpeta:',
        'btn_gen_json':  'Generar archivos JSON',
        'tic12_title':  'Generador de Etiquetas TIC12',
        'itic_title':   'Generador de Etiquetas I-TIC',
        'sec_tic_dev':  'Dispositivos',
        'lbl_tic_from': 'Desde (número):',
        'lbl_tic_to':   'Hasta (número):',
        'lbl_tic_yr':   'Año:',
        'lbl_tic_fw':   'Versión FW:',
        'sec_tic_out':  'Archivo de salida',
        'lbl_tic_pdf':  'PDF de salida:',
        'btn_tic_gen':  'Generar PDF',
        'proj_title':   'Generador de Proyecto Completo',
        'sec_proj_loc': 'Ubicación del proyecto',
        'lbl_root_fld': 'Carpeta raíz:',
        'lbl_proj_nm':  'Nombre del proyecto:',
        'sec_proj_dev': 'Dispositivos',
        'sec_proj_csv': 'Parámetros CSV',
        'sec_proj_lbl': 'Tipo de etiqueta',
        'sec_proj_ser': 'Serial (para PDF)',
        'sec_proj_jsn': 'Parámetros JSON',
        'btn_gen_all':  '⚡  GENERAR TODO  —  CSV + JSON + Etichette',
        'proj_struct':  'Se creará la estructura:',
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
    },
    'en': {
        'csv_title':     'CSV Generator — LoRa Devices',
        'sec_name':      'Device name',
        'lbl_prefix':    'Prefix:',
        'lbl_from':      'From:',
        'lbl_to':        'To:',
        'prev_error':    "['to' must be ≥ 'from']",
        'prev_fmt':      '→ {n} devices:  {a}  …  {b}',
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
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'Output file:',
        'btn_gen_csv':   'Generate CSV',
        'lbl_ready':     'Ready.',
        'labels_title':  'Label Generator — PDF A4',
        'sec_opt1':      'Option 1 – Load from generated CSV',
        'lbl_csv_file':  'CSV file:',
        'btn_load':      'Load',
        'sec_opt2':      'Option 2 – Enter data manually',
        'lbl_name_pfx':  'Name prefix:',
        'lbl_deveui_m':  'Initial DevEUI (16 hex):',
        'sec_serial':    'Serial number',
        'lbl_ser_start': 'Serial start:',
        'lbl_year':      'Year:',
        'lbl_ser_fmt':   'Label format: 04906/2026  →  04907/2026  →  ...',
        'sec_opts':      'Label options',
        'chk_bt':        'Include BLUETOOTH row  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'RTU tube label  (TECNIDRO / HYDRONET-RTU header, no Bluetooth)',
        'chk_lc':        'RTU LORACONT label  (23mm × 87mm, TECNIDRO / LORACONT-RTU header)',
        'lbl_pdf_out':   'Output PDF file:',
        'btn_gen_pdf':   'Generate PDF Labels',
        'lang_title':    'Select language',
        'lang_sub':      'Interface language:',
        'theme_label':   'Application theme:',
        'theme_dark':    '🌙  Dark',
        'theme_light':   '☀  Light',
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
    },
    'it': {
        'csv_title':     'Generatore CSV — Dispositivi LoRa',
        'sec_name':      'Nome del dispositivo',
        'lbl_prefix':    'Prefisso:',
        'lbl_from':      'Da:',
        'lbl_to':        'A:',
        'prev_error':    "['a' deve essere ≥ 'da']",
        'prev_fmt':      '→ {n} dispositivi:  {a}  …  {b}',
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
        'lbl_tag':       'Tag:',
        'lbl_alias':     'Alias:',
        'lbl_out_file':  'File di output:',
        'btn_gen_csv':   'Genera CSV',
        'lbl_ready':     'Pronto.',
        'labels_title':  'Generatore Etichette — PDF A4',
        'sec_opt1':      'Opzione 1 – Carica da CSV generato',
        'lbl_csv_file':  'File CSV:',
        'btn_load':      'Carica',
        'sec_opt2':      'Opzione 2 – Inserisci dati manualmente',
        'lbl_name_pfx':  'Prefisso nome:',
        'lbl_deveui_m':  'DevEUI iniziale (16 hex):',
        'sec_serial':    'Numero seriale',
        'lbl_ser_start': 'Seriale inizio:',
        'lbl_year':      'Anno:',
        'lbl_ser_fmt':   'Formato etichetta: 04906/2026  →  04907/2026  →  ...',
        'sec_opts':      'Opzioni etichetta',
        'chk_bt':        'Includi riga BLUETOOTH  (TECNIDROBT + DevAddr)',
        'chk_rtu':       'Etichetta RTU in tubo  (header TECNIDRO / HYDRONET-RTU, senza Bluetooth)',
        'chk_lc':        'Etichetta RTU LORACONT  (23mm × 87mm, header TECNIDRO / LORACONT-RTU)',
        'lbl_pdf_out':   'File PDF di output:',
        'btn_gen_pdf':   'Genera PDF Etichette',
        'lang_title':    'Seleziona lingua',
        'lang_sub':      'Lingua interfaccia:',
        'theme_label':   'Tema applicazione:',
        'theme_dark':    '🌙  Scuro',
        'theme_light':   '☀  Chiaro',
        'upd_title':     'Aggiornamenti',
        'upd_version':   'Versione attuale:',
        'upd_source':    'URL del manifest:',
        'upd_auto':      'Controlla aggiornamenti all’avvio',
        'upd_save':      'Salva configurazione',
        'upd_check':     'Controlla aggiornamenti',
        'upd_saved':     'Configurazione aggiornamenti salvata.',
        'upd_status_idle':'Configura un URL del manifest per attivare gli aggiornamenti online.',
        'upd_status_checking':'Controllo aggiornamenti...',
        'upd_status_latest':'Hai già l’ultima versione.',
        'upd_status_available':'Nuova versione disponibile: {version}',
        'upd_status_disabled':'Gli aggiornamenti online sono disattivati.',
        'upd_error_title':'Aggiornamento',
        'upd_error_no_url':'Inserisci l’URL del manifest di aggiornamento.',
        'upd_error_bad_manifest':'Il manifest non è valido o mancano dei dati.',
        'upd_error_network':'Impossibile controllare gli aggiornamenti.\n{error}',
        'upd_error_download':'Impossibile scaricare l’aggiornamento.\n{error}',
        'upd_confirm_title':'Nuova versione disponibile',
        'upd_confirm_body':'Versione attuale: {current}\nNuova versione: {latest}\n\nVuoi scaricarla e installarla adesso?',
        'upd_download_title':'Salva aggiornamento come...',
        'upd_success_restart':'L’aggiornamento è stato scaricato. Il programma verrà chiuso per installare la nuova versione.',
        'json_title':    'Generatore file JSON',
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
        'btn_gen_all':  '⚡  GENERA TUTTO  —  CSV + JSON + Etichette',
        'proj_struct':  'Verrà creata la struttura:',
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
    },
}

_cur_lang = ['es']
_lang_cbs = []

def t(key):
    return TRANSLATIONS[_cur_lang[0]].get(key, key)

def set_lang(code):
    _cur_lang[0] = code
    for cb in _lang_cbs:
        cb()


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
        if getattr(sys, "frozen", False):
            current_exe = sys.executable
            temp_name = os.path.basename(download_url) or f"{APP_BUILD_NAME}_{latest_version}.exe"
            downloaded_exe = os.path.join(tempfile.gettempdir(), temp_name)
            _download_binary(download_url, downloaded_exe)
            _launch_windows_updater(downloaded_exe, current_exe)
            if status_cb:
                status_cb(t("upd_success_restart"))
            messagebox.showinfo(t("upd_title"), t("upd_success_restart"), parent=parent)
            parent.after(300, parent.destroy)
            return True

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
        if status_cb:
            status_cb(t("upd_status_available").format(version=latest_version))
        messagebox.showinfo(t("upd_title"), f"{latest_version}\n\n{target}", parent=parent)
        return True
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        if status_cb:
            status_cb(t("upd_status_idle"))
        messagebox.showerror(t("upd_error_title"), t("upd_error_download").format(error=exc), parent=parent)
        return False

# ─────────────────────────────────────────────────────────────────────────────
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


# ═════════════════════════════════════════════════════════════════════════════
# PDF – sin cambios
# ═════════════════════════════════════════════════════════════════════════════
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
        raise ImportError("La librería 'reportlab' no está instalada.\nEjecuta:  pip install reportlab")

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


# ═════════════════════════════════════════════════════════════════════════════
# GUI helpers
# ═════════════════════════════════════════════════════════════════════════════
LBL_W = 200

# Colores adaptativos  (light_mode, dark_mode)
C_SEC_BG   = ("#cce0f5", "#162d4a")   # azul claro     / navy oscuro
C_SEC_TEXT = ("#0d3060", "#82bcff")   # azul oscuro     / azul claro
C_HINT     = ("#5577aa", "#8899aa")   # azul grisáceo   / gris-azul
C_STATUS   = ("#1a5a8a", "#6699bb")   # azul medio      / azul claro
C_HDR_BG   = ("#1a3a6a", "#0e1c30")  # navy (igual en ambos temas — barra top profesional)
C_HDR_TEXT = ("white",   "#82bcff")  # blanco / azul claro
C_BAR_BG   = ("#1a3a6a", "#090f1a")  # navy (igual en ambos)
C_BAR_TEXT = ("#aaccee", "#556677")  # azul pálido / gris
C_DIV      = ("#90b8d8", "#2a3a4a")  # azul gris claro / oscuro


def _sec(parent, key, refs=None):
    """Barra de sección."""
    f = ctk.CTkFrame(parent, fg_color=C_SEC_BG, corner_radius=6, height=30)
    f.pack(fill="x", padx=6, pady=(14, 4))
    f.pack_propagate(False)
    lbl = ctk.CTkLabel(f, text=t(key),
                       font=ctk.CTkFont(size=11, weight="bold"),
                       text_color=C_SEC_TEXT)
    lbl.pack(side="left", padx=12)
    if refs is not None:
        refs[f'_sec_{key}'] = lbl
    return lbl


def _div(parent):
    ctk.CTkFrame(parent, height=1, fg_color=C_DIV).pack(fill="x", padx=10, pady=(14, 6))


def _row(parent, pady=3):
    f = ctk.CTkFrame(parent, fg_color=("white", "#1e1e2e"))
    f.pack(fill="x", padx=10, pady=pady)
    return f


# ═════════════════════════════════════════════════════════════════════════════
# Tab 1: CSV
# ═════════════════════════════════════════════════════════════════════════════
class CSVTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=("white", "#1e1e2e"),
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        lbl_title = ctk.CTkLabel(self, text=t('csv_title'),
                                  font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(12, 6))
        self._refs['csv_title'] = lbl_title

        # ── Nombre ────────────────────────────────────────────────
        _sec(self, 'sec_name', self._refs)
        self._frow('lbl_prefix', "CBG_",  "name_prefix",  w=130)
        self._frow('lbl_from',   "1201",  "start_number", w=100)
        self._frow('lbl_to',     "1220",  "end_number",   w=100)

        # Preview (sin textvariable — se actualiza con trace)
        self._preview_lbl = ctk.CTkLabel(self, text="",
                                          text_color=C_HINT,
                                          font=ctk.CTkFont(size=10))
        self._preview_lbl.pack(anchor="w", padx=18, pady=(0, 4))
        for v in (self.name_prefix_var, self.start_number_var, self.end_number_var):
            v.trace_add("write", self._update_preview)
        self._update_preview()

        # ── LoRa ─────────────────────────────────────────────────
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

        # ── Coordenadas ───────────────────────────────────────────
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

        # ── Extra ─────────────────────────────────────────────────
        _sec(self, 'sec_extra', self._refs)
        re = _row(self)
        ctk.CTkLabel(re, text="childnumber:", width=LBL_W, anchor="w").pack(side="left")
        self.childnumber_var = tk.StringVar(value="1")
        ctk.CTkEntry(re, textvariable=self.childnumber_var, width=100).pack(side="left", padx=(4, 18))
        ctk.CTkLabel(re, text="devStatusReqInterval:", width=170, anchor="w").pack(side="left")
        self.devstatusreqinterval_var = tk.StringVar(value="0")
        ctk.CTkEntry(re, textvariable=self.devstatusreqinterval_var, width=80).pack(side="left", padx=4)
        self._frow('lbl_tag',   "", "tag")
        self._frow('lbl_alias', "", "alias")

        # ── Output ────────────────────────────────────────────────
        _div(self)
        ro = _row(self)
        lbl_out = ctk.CTkLabel(ro, text=t('lbl_out_file'), width=LBL_W, anchor="w")
        lbl_out.pack(side="left")
        self._refs['lbl_out_file'] = lbl_out
        self.csv_output_var = tk.StringVar()
        ctk.CTkEntry(ro, textvariable=self.csv_output_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(ro, text="…", width=36, command=self._browse_csv).pack(side="left")

        btn = ctk.CTkButton(self, text=t('btn_gen_csv'), command=self._generate,
                             height=44, font=ctk.CTkFont(size=13, weight="bold"))
        btn.pack(pady=(16, 16), padx=30, fill="x")
        self._refs['btn_gen_csv'] = btn

    # ── helpers ──────────────────────────────────────────────────────────────
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
            tag          = self.tag_var.get().strip()
            alias        = self.alias_var.get().strip()
            output_file  = self.csv_output_var.get().strip()

            if not output_file: messagebox.showerror("Error","Selecciona un archivo de salida."); return
            num_devices = end-start+1
            if num_devices <= 0: messagebox.showerror("Error","'Hasta' debe ser ≥ 'Desde'."); return
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
            messagebox.showinfo("Éxito",
                f"CSV generado correctamente.\n\n"
                f"  Dispositivos: {num_devices}\n"
                f"  DevEUI desde: {start_deveui}\n"
                f"  DevEUI hasta: {format(deveui_int+num_devices-1,'016X')}\n\n"
                f"Archivo:\n{output_file}")
        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numéricos/hex.\n\nDetalle: {e}")
        except PermissionError:
            messagebox.showerror("Error de permisos","No se pudo escribir el archivo.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Tab 2: Etichette PDF
# ═════════════════════════════════════════════════════════════════════════════
class EtichetteTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=("white", "#1e1e2e"),
                         corner_radius=0, border_width=0, label_text="")
        self._devices = []
        self._refs    = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        lbl_title = ctk.CTkLabel(self, text=t('labels_title'),
                                  font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(pady=(12, 6))
        self._refs['labels_title'] = lbl_title

        # ── Opción 1 ─────────────────────────────────────────────
        _sec(self, 'sec_opt1', self._refs)
        r1 = _row(self)
        lbl_cf = ctk.CTkLabel(r1, text=t('lbl_csv_file'), width=LBL_W, anchor="w")
        lbl_cf.pack(side="left")
        self._refs['lbl_csv_file'] = lbl_cf
        self.csv_input_var = tk.StringVar()
        ctk.CTkEntry(r1, textvariable=self.csv_input_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r1, text="…", width=36, command=self._browse_csv_in).pack(side="left", padx=(0,4))
        btn_load = ctk.CTkButton(r1, text=t('btn_load'), width=80, command=self._load_csv)
        btn_load.pack(side="left")
        self._refs['btn_load'] = btn_load

        # Status CSV (sin textvariable)
        self._csv_status_lbl = ctk.CTkLabel(self, text="",
                                             text_color=C_STATUS,
                                             font=ctk.CTkFont(size=10))
        self._csv_status_lbl.pack(anchor="w", padx=18, pady=(2, 4))

        # ── Opción 2 ─────────────────────────────────────────────
        _sec(self, 'sec_opt2', self._refs)
        self._frow('lbl_name_pfx', "CBG_",            "m_prefix", w=130)
        self._frow('lbl_from',     "1201",             "m_from",   w=100)
        self._frow('lbl_to',       "1220",             "m_to",     w=100)
        self._frow('lbl_deveui_m', "512345678B1904B1", "m_deveui")

        # ── Serial ───────────────────────────────────────────────
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

        # ── Opciones ─────────────────────────────────────────────
        _sec(self, 'sec_opts', self._refs)

        # Una sola variable — 4 opciones mutuamente exclusivas
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

        # ── Output ────────────────────────────────────────────────
        _div(self)
        rpo = _row(self)
        lbl_po = ctk.CTkLabel(rpo, text=t('lbl_pdf_out'), width=LBL_W, anchor="w")
        lbl_po.pack(side="left")
        self._refs['lbl_pdf_out'] = lbl_po
        self.pdf_output_var = tk.StringVar()
        ctk.CTkEntry(rpo, textvariable=self.pdf_output_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(rpo, text="…", width=36, command=self._browse_pdf).pack(side="left")

        btn_pdf = ctk.CTkButton(self, text=t('btn_gen_pdf'), command=self._generate_pdf,
                                 height=44, font=ctk.CTkFont(size=13, weight="bold"))
        btn_pdf.pack(pady=(16, 6), padx=30, fill="x")
        self._refs['btn_gen_pdf'] = btn_pdf

        # Status PDF (sin textvariable)
        self._pdf_status_lbl = ctk.CTkLabel(self, text=t('lbl_ready'),
                                             text_color=C_HINT,
                                             font=ctk.CTkFont(size=10))
        self._pdf_status_lbl.pack(anchor="w", padx=18, pady=(0, 14))

    # ── helpers ──────────────────────────────────────────────────────────────
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
        if p: self.pdf_output_var.set(p)

    def _load_csv(self):
        path = self.csv_input_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showerror("Error","Selecciona un archivo CSV válido."); return
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
            self._csv_status_lbl.configure(text=f"  ✓  {len(devices)} dispositivos cargados desde CSV.")
            if devices:
                fn = devices[0]['name']; ln = devices[-1]['name']
                np = ''.join(c for c in fn if c.isdigit())
                pp = fn[:len(fn)-len(np)]
                if np:
                    self.m_prefix_var.set(pp); self.m_from_var.set(np)
                    ln2 = ''.join(c for c in ln if c.isdigit())
                    if ln2: self.m_to_var.set(ln2)
                self.m_deveui_var.set(devices[0]['dev_eui'])
        except Exception as e:
            messagebox.showerror("Error al leer CSV", str(e))

    def _build_devices_manual(self):
        prefix = self.m_prefix_var.get().strip()
        sr = self.m_from_var.get().strip(); start = int(sr); nw = len(sr)
        end = int(self.m_to_var.get().strip())
        ds = self.m_deveui_var.get().strip().upper()
        if len(ds) != 16: raise ValueError(f"DevEUI debe tener 16 hex (tiene {len(ds)}).")
        int(ds, 16); di = int(ds,16); n = end-start+1
        if n <= 0: raise ValueError("'Hasta' debe ser ≥ 'Desde'.")
        devs = []
        for i in range(n):
            nm = f"{prefix}{start+i:0{nw}d}"; de = format(di+i,"016X"); da = de[-8:]
            devs.append({'name':nm,'dev_eui':de,'dev_addr':da})
        return devs

    def _generate_pdf(self):
        try:
            ssr = self.serial_start_var.get().strip()
            sy  = self.serial_year_var.get().strip()
            of  = self.pdf_output_var.get().strip()
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

            self._pdf_status_lbl.configure(text="Generando PDF…")
            self.update()
            _make_pdf(devices, of,
                      include_bluetooth=include_bluetooth,
                      rtu_header=rtu_header,
                      loraconta=loraconta)
            n = len(devices)
            self._pdf_status_lbl.configure(text=f"✓  {n} etiquetas  →  {os.path.basename(of)}")
            messagebox.showinfo("Éxito",
                f"PDF generado correctamente.\n\n"
                f"  Etiquetas:  {n}\n"
                f"  Primera:    {devices[0]['name']}  |  {devices[0]['serial']}\n"
                f"  Última:     {devices[-1]['name']}  |  {devices[-1]['serial']}\n\n"
                f"Archivo:\n{of}")
        except ValueError as e:
            messagebox.showerror("Error de valor", str(e))
        except ImportError as e:
            messagebox.showerror("Librería faltante", str(e))
        except PermissionError:
            messagebox.showerror("Error de permisos","No se pudo escribir el PDF.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Tab 3: Idioma + Tema
# ═════════════════════════════════════════════════════════════════════════════
class LangTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=("white", "#1e1e2e"))
        self._is_dark = True
        self._update_settings = _load_update_settings()
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        # Centrado vertical con spacer
        ctk.CTkFrame(self, fg_color=("white", "#1e1e2e"), height=50).pack()

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
            values=["🇪🇸  Español", "🇬🇧  English", "🇮🇹  Italiano"],
            command=self._on_lang,
            font=ctk.CTkFont(size=13),
            height=44, width=420,
        )
        self._lang_seg.set("🇪🇸  Español")
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
        code_map = {"🇪🇸  Español": "es", "🇬🇧  English": "en", "🇮🇹  Italiano": "it"}
        set_lang(code_map.get(value, "es"))
        # Actualizar el theme segmented button con los textos del nuevo idioma,
        # preservando la selección actual
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
        self._lbl_theme.configure(text=t('theme_label'))
        self._lbl_upd_title.configure(text=t('upd_title'))
        self._lbl_upd_ver.configure(text=f"{t('upd_version')} {APP_VERSION}")
        self._lbl_upd_source.configure(text=t('upd_source'))
        self._chk_upd_auto.configure(text=t('upd_auto'))
        self._btn_upd_save.configure(text=t('upd_save'))
        self._btn_upd_check.configure(text=t('upd_check'))
        self._lbl_upd_status.configure(text=t('upd_status_idle'))


# ═════════════════════════════════════════════════════════════════════════════
# Template JSON
# Todos los valores son fijos excepto: allarmi, valvetype, deui, daddr
# ═════════════════════════════════════════════════════════════════════════════
_JSON_BASE = {
    "device": {
        "allarmi":          None,   # 1=ON / 0=OFF  → desde UI
        "adc":              0,
        "minvddbat":        3000,
        "alarmbat":         3200,
        "vddbat":           3600,
        "cfm":              0,
        "alarmcycle":       16000,
        "valvestatuscycle": 120000,
        "payloadcycle":     0,
        "cfm_msg_cycle":    0,
        "valvetype":        None,   # 1=Motorizzata / 0=ELBA  → desde UI
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


def _build_json(dev_eui, dev_addr, valve_type, allarme_on, sendinterval=130000, adc_on=False):
    """Construye el dict JSON para un dispositivo.
    valve_type: 'motorizzata' → valvetype=1  |  'elba' → valvetype=0
    adc_on: True → adc=1  |  False → adc=0
    """
    data = copy.deepcopy(_JSON_BASE)
    data["device"]["allarmi"]      = 1 if allarme_on else 0
    data["device"]["adc"]          = 1 if adc_on else 0
    data["device"]["valvetype"]    = 1 if valve_type == "motorizzata" else 0
    data["device"]["sendinterval"] = int(sendinterval)
    data["radio"]["deui"]  = dev_eui
    data["radio"]["daddr"] = dev_addr
    data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


# ═════════════════════════════════════════════════════════════════════════════
# PDF: Etichette TIC12 / I-TIC
# ═════════════════════════════════════════════════════════════════════════════
def _make_tic_pdf(labels, output_path, product_name):
    """
    labels: list of dicts {'serial': '00001/2026', 'fw': '04.00.05'}
    product_name: 'TIC12' or 'I-TIC 1V'
    Generates A4 portrait PDF: 3 labels/row × 15 rows = 45 labels/page.
    Layout: logo on left | product/company/website on right | serial/FW bar bottom.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.units import mm
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise ImportError("La librería 'reportlab' no está instalada.\nEjecuta:  pip install reportlab")

    import io

    PW, PH = A4          # 595.28 × 841.89 pt  (portrait)

    # ── Margins (from Excel page setup) ──────────────────────────
    ML = 18 * mm
    MR = 14 * mm
    MT =  9 * mm
    MB =  4 * mm

    # ── Grid ─────────────────────────────────────────────────────
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

    LW = (AW - (N_COLS - 1) * COL_GAP) / N_COLS
    grid_h = N_ROWS * LH + (N_ROWS - 1) * GAP_V
    grid_top = PH - MT - max(0, (AH - grid_h) / 2.0) + (4.5 * mm)

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

    # ── Prepare black version of logo for labels ─────────────────
    logo_reader = None
    logo_path   = _resource("logo.png")
    if os.path.isfile(logo_path):
        try:
            src = Image.open(logo_path).convert("RGBA")
            px  = list(src.getdata())
            bpx = []
            for r, g, b, a in px:
                lum = 0.299*r + 0.587*g + 0.114*b
                if lum > 210 or a < 30:          # white / transparent → keep transparent
                    bpx.append((255, 255, 255, 0))
                else:                              # any colored pixel → black
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

        lx       = ML + ci * (LW + COL_GAP)
        slot_top = grid_top - ri * (LH + GAP_V)
        ly       = slot_top - LH

        row4_bot = ly
        row3_bot = ly + R4
        row2_bot = ly + R4 + R3
        row1_bot = ly + R4 + R3 + R2
        label_top = ly + LH

        serial  = lbl['serial']
        fw_text = f"FW: {lbl['fw']}"

        # ── Borders ──────────────────────────────────────────────
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

        # ── Logo negro (left section, rows 1-3) ─────────────────────
        if logo_reader:
            c.drawImage(logo_reader,
                        lx, row3_bot,
                        CA, (R1+R2+R3),
                        mask='auto', preserveAspectRatio=True, anchor='c')

        # ── Text section center x ─────────────────────────────────
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

        # ── Row 4 bottom bar ─────────────────────────────────────
        # Cell A — "SERIAL N."
        c.setFont("Helvetica", FS_SLBL)
        c.drawCentredString(lx + CA / 2, _cy(row4_bot, R4, FS_SLBL), "SERIAL N.")

        # Cell B — serial number
        c.setFont("Helvetica-Bold", FS_SVAL)
        c.drawCentredString(lx + CA + CB / 2, _cy(row4_bot, R4, FS_SVAL), serial)

        # Cell C — FW version
        c.setFont("Helvetica-Bold", FS_FW)
        c.drawCentredString(lx + CA + CB + CC / 2, _cy(row4_bot, R4, FS_FW), fw_text)

    c.save()


# ═════════════════════════════════════════════════════════════════════════════
# Tab 4: Generador JSON
# ═════════════════════════════════════════════════════════════════════════════
class JSONTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=("white", "#1e1e2e"),
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        # Título
        self._lbl_title = ctk.CTkLabel(self, text=t('json_title'),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 6))

        # ── Nombre del dispositivo ────────────────────────────────
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

        # ── Radio (DevEUI) ────────────────────────────────────────
        _sec(self, 'sec_deveui_j', self._refs)
        self._frow('lbl_deveui_j', "512345678B190051", "j_deveui")
        hint = ctk.CTkLabel(self, text=t('lbl_devaddr_j'),
                             text_color=C_HINT,
                             font=ctk.CTkFont(size=10, slant="italic"))
        hint.pack(anchor="w", padx=18, pady=(0, 4))
        self._refs['lbl_devaddr_j'] = hint

        # ── Tipo de válvula ───────────────────────────────────────
        _sec(self, 'sec_valve', self._refs)
        self.valve_var = tk.StringVar(value="motorizzata")
        for val, label in [("motorizzata", "Valvola Motorizzata"), ("elba", "ELBA")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.valve_var, value=val,
                               font=ctk.CTkFont(size=13)
                               ).pack(anchor="w", padx=28, pady=6)

        # ── Allarme Sportello ─────────────────────────────────────
        _sec(self, 'sec_allarme', self._refs)
        self.allarme_var = tk.StringVar(value="on")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.allarme_var, value=val,
                               font=ctk.CTkFont(size=13)
                               ).pack(anchor="w", padx=28, pady=6)

        # ── ADC ───────────────────────────────────────────────────
        _sec(self, 'sec_adc', self._refs)
        self.adc_var = tk.StringVar(value="off")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.adc_var, value=val,
                               font=ctk.CTkFont(size=13)
                               ).pack(anchor="w", padx=28, pady=6)

        # ── Parámetros de envío ───────────────────────────────────
        _sec(self, 'sec_send_params', self._refs)
        self._frow('lbl_sendinterval', "130000", "j_sendinterval", w=140)

        # ── Carpeta de salida ─────────────────────────────────────
        _sec(self, 'sec_out_json', self._refs)
        r_out = _row(self)
        lbl_fld = ctk.CTkLabel(r_out, text=t('lbl_out_folder'), width=LBL_W, anchor="w")
        lbl_fld.pack(side="left")
        self._refs['lbl_out_folder'] = lbl_fld
        self.out_folder_var = tk.StringVar()
        ctk.CTkEntry(r_out, textvariable=self.out_folder_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r_out, text="…", width=36,
                       command=self._browse_folder).pack(side="left")

        # ── Botón generar ─────────────────────────────────────────
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

    # ── helpers ──────────────────────────────────────────────────────────────
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
        self._lbl_title.configure(text=t('json_title'))
        for key, w in self._refs.items():
            w.configure(text=t(key[5:]) if key.startswith('_sec_') else t(key))
        self._update_preview()

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
            valve        = self.valve_var.get()
            allarme      = (self.allarme_var.get() == "on")
            adc_on       = (self.adc_var.get() == "on")
            sendinterval = int(self.j_sendinterval_var.get().strip())

            if not folder:
                messagebox.showerror("Error", "Selecciona una carpeta de salida."); return
            if not os.path.isdir(folder):
                messagebox.showerror("Error", "La carpeta no existe."); return
            if end < start:
                messagebox.showerror("Error", "'Hasta' debe ser ≥ 'Desde'."); return
            if len(deveui_s) != 16:
                messagebox.showerror("Error", f"DevEUI debe tener 16 hex (tiene {len(deveui_s)})."); return
            int(deveui_s, 16)

            deveui_int  = int(deveui_s, 16)
            num_devices = end - start + 1

            self._status_lbl.configure(text="Generando JSON…")
            self.update()

            for i in range(num_devices):
                name    = f"{prefix}{start + i:0{nw}d}"
                dev_eui = format(deveui_int + i, "016X")
                dev_addr = dev_eui[-8:]
                data = _build_json(dev_eui, dev_addr, valve, allarme, sendinterval, adc_on)
                filepath = os.path.join(folder, f"{name}.JSON")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)

            self._status_lbl.configure(
                text=f"✓  {num_devices} archivos JSON generados  →  {folder}")
            messagebox.showinfo("Éxito",
                f"JSON generados correctamente.\n\n"
                f"  Dispositivos:   {num_devices}\n"
                f"  Válvula:        {'Valvola Motorizzata' if valve=='motorizzata' else 'ELBA'}\n"
                f"  Allarme Sport.: {'ON' if allarme else 'OFF'}\n"
                f"  DevEUI desde:   {deveui_s}\n"
                f"  DevEUI hasta:   {format(deveui_int+num_devices-1,'016X')}\n\n"
                f"Carpeta:\n{folder}")

        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numéricos/hex.\n\nDetalle: {e}")
        except PermissionError:
            messagebox.showerror("Error de permisos", "No se pudo escribir en la carpeta.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Tab 5: Proyecto Completo
# ═════════════════════════════════════════════════════════════════════════════
class ProjectTab(ctk.CTkScrollableFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=("white", "#1e1e2e"),
                         corner_radius=0, border_width=0, label_text="")
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        # Título
        self._lbl_title = ctk.CTkLabel(self, text=t('proj_title'),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 4))

        # Preview estructura (se actualiza dinámicamente)
        self._struct_lbl = ctk.CTkLabel(self, text="",
                                         text_color=C_HINT,
                                         font=ctk.CTkFont(size=10),
                                         justify="left")
        self._struct_lbl.pack(anchor="w", padx=18, pady=(0, 6))

        # ── Ubicación del proyecto ────────────────────────────────
        _sec(self, 'sec_proj_loc', self._refs)

        r_root = _row(self)
        lbl_rf = ctk.CTkLabel(r_root, text=t('lbl_root_fld'), width=LBL_W, anchor="w")
        lbl_rf.pack(side="left")
        self._refs['lbl_root_fld'] = lbl_rf
        self.root_folder_var = tk.StringVar()
        self.root_folder_var.trace_add("write", self._update_struct)
        ctk.CTkEntry(r_root, textvariable=self.root_folder_var).pack(
            side="left", fill="x", expand=True, padx=(4, 4))
        ctk.CTkButton(r_root, text="…", width=36,
                       command=self._browse_root).pack(side="left")

        r_name = _row(self)
        lbl_pn = ctk.CTkLabel(r_name, text=t('lbl_proj_nm'), width=LBL_W, anchor="w")
        lbl_pn.pack(side="left")
        self._refs['lbl_proj_nm'] = lbl_pn
        self.proj_name_var = tk.StringVar(value="Proyecto_01")
        self.proj_name_var.trace_add("write", self._update_struct)
        ctk.CTkEntry(r_name, textvariable=self.proj_name_var).pack(
            side="left", fill="x", expand=True, padx=(4, 0))

        # ── Dispositivos ──────────────────────────────────────────
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

        # ── Parámetros CSV ────────────────────────────────────────
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

        # ── Tipo de etiqueta ──────────────────────────────────────
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

        # ── Serial (para PDF) ─────────────────────────────────────
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

        # ── Parámetros JSON ───────────────────────────────────────
        _sec(self, 'sec_proj_jsn', self._refs)

        ctk.CTkLabel(self, text="Valvola:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_SEC_TEXT).pack(anchor="w", padx=16, pady=(6, 2))
        self.p_valve_var = tk.StringVar(value="motorizzata")
        for val, label in [("motorizzata", "Valvola Motorizzata"), ("elba", "ELBA")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.p_valve_var, value=val,
                               font=ctk.CTkFont(size=12)
                               ).pack(anchor="w", padx=28, pady=3)

        ctk.CTkLabel(self, text="Allarme Sportello:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_SEC_TEXT).pack(anchor="w", padx=16, pady=(10, 2))
        self.p_allarme_var = tk.StringVar(value="on")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.p_allarme_var, value=val,
                               font=ctk.CTkFont(size=12)
                               ).pack(anchor="w", padx=28, pady=3)

        ctk.CTkLabel(self, text="ADC:",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=C_SEC_TEXT).pack(anchor="w", padx=16, pady=(10, 2))
        self.p_adc_var = tk.StringVar(value="off")
        for val, label in [("on", "ON"), ("off", "OFF")]:
            ctk.CTkRadioButton(self, text=label,
                               variable=self.p_adc_var, value=val,
                               font=ctk.CTkFont(size=12)
                               ).pack(anchor="w", padx=28, pady=3)

        self._frow('lbl_sendinterval', "130000", "p_sendinterval", w=140)

        # ── Botón principal ───────────────────────────────────────
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

    # ── helpers ──────────────────────────────────────────────────────────────
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
            w.configure(text=t(key[5:]) if key.startswith('_sec_') else t(key))
        self._update_struct()
        self._update_preview()
        self._btn_all.configure(text=t('btn_gen_all'))

    def _browse_root(self):
        p = filedialog.askdirectory(title="Seleccionar carpeta raíz")
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
        root   = self.root_folder_var.get().strip() or "…"
        name   = self.proj_name_var.get().strip()   or "NombreProyecto"
        try:
            n = int(self.p_to_var.get()) - int(self.p_from_var.get()) + 1
        except Exception:
            n = "?"
        pfx = self.p_prefix_var.get() if hasattr(self, 'p_prefix_var') else ""
        txt = (
            f"  📁  {root}/{name}/\n"
            f"       ├── CSV/         →  {name}.csv\n"
            f"       ├── JSON/        →  {n} archivos  ({pfx}…).JSON\n"
            f"       └── etiquette/   →  {name}.pdf"
        )
        self._struct_lbl.configure(text=txt)

    # ── Generación ────────────────────────────────────────────────────────────
    def _generate_all(self):
        try:
            # ── Validaciones básicas ──────────────────────────────
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
            adc_on       = (self.p_adc_var.get() == "on")
            sendinterval = int(self.p_sendinterval_var.get().strip())

            if not root:
                messagebox.showerror("Error", "Selecciona una carpeta raíz."); return
            if not proj_name:
                messagebox.showerror("Error", "Escribe un nombre de proyecto."); return
            if not os.path.isdir(root):
                messagebox.showerror("Error", "La carpeta raíz no existe."); return
            if end < start:
                messagebox.showerror("Error", "'Hasta' debe ser ≥ 'Desde'."); return
            if len(deveui_s) != 16:
                messagebox.showerror("Error", f"DevEUI debe tener 16 hex."); return
            int(deveui_s, 16)
            if len(new_skey) != 32:
                messagebox.showerror("Error", "NewSKey debe tener 32 hex."); return
            if len(app_skey) != 32:
                messagebox.showerror("Error", "AppSKey debe tener 32 hex."); return

            num_devices = end - start + 1
            deveui_int  = int(deveui_s, 16)
            ser_width   = len(ser_raw)
            ser_start   = int(ser_raw)

            # ── Crear estructura de carpetas ──────────────────────
            proj_dir  = os.path.join(root, proj_name)
            csv_dir   = os.path.join(proj_dir, "CSV")
            json_dir  = os.path.join(proj_dir, "JSON")
            label_dir = os.path.join(proj_dir, "etiquette")
            for d in (proj_dir, csv_dir, json_dir, label_dir):
                os.makedirs(d, exist_ok=True)

            self._status_lbl.configure(text="⏳  Generando…")
            self.update()

            # ── 1. CSV ────────────────────────────────────────────
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
                              "", "", FIXED_GROUP, "", "", "1", "0"])
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(hdr); w.writerows(rows)

            # ── 2. JSON ───────────────────────────────────────────
            for i, dev in enumerate(devices):
                data = _build_json(dev['dev_eui'], dev['dev_addr'], valve, allarme, sendinterval, adc_on)
                with open(os.path.join(json_dir, f"{dev['name']}.JSON"),
                          "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)

            # ── 3. PDF Etichette ──────────────────────────────────
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

            # ── Resultado ─────────────────────────────────────────
            self._status_lbl.configure(
                text=f"✓  Proyecto generado  →  {proj_dir}")
            messagebox.showinfo("Éxito",
                f"Proyecto generado correctamente.\n\n"
                f"  📁  {proj_name}/\n"
                f"  ├── CSV/       →  {proj_name}.csv\n"
                f"  ├── JSON/      →  {num_devices} archivos .JSON\n"
                f"  └── etiquette/ →  {proj_name}.pdf\n\n"
                f"  Dispositivos:  {num_devices}\n"
                f"  Válvula:       {'Motorizzata' if valve=='motorizzata' else 'ELBA'}\n"
                f"  Allarme:       {'ON' if allarme else 'OFF'}\n"
                f"  Etiqueta:      {label_opt.upper()}\n\n"
                f"Carpeta:\n{proj_dir}")

        except ValueError as e:
            messagebox.showerror("Error de valor", f"Verifica campos numéricos/hex.\n\nDetalle: {e}")
        except ImportError as e:
            messagebox.showerror("Librería faltante", str(e))
        except PermissionError:
            messagebox.showerror("Error de permisos", "No se pudo escribir en la carpeta.")
        except Exception as e:
            messagebox.showerror("Error inesperado", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# Tab: Etichette TIC12 / I-TIC
# ═════════════════════════════════════════════════════════════════════════════
class TICLabelTab(ctk.CTkScrollableFrame):
    def __init__(self, parent, product_name, title_key):
        super().__init__(parent, fg_color=("white", "#1e1e2e"),
                         corner_radius=0, border_width=0, label_text="")
        self._product_name = product_name
        self._title_key    = title_key
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

    def _build(self):
        fw_default = "03.02.03" if self._product_name == "TIC12" else "04.00.05"

        self._lbl_title = ctk.CTkLabel(self, text=t(self._title_key),
                                        font=ctk.CTkFont(size=15, weight="bold"))
        self._lbl_title.pack(pady=(12, 6))

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
        ctk.CTkButton(r, text="…", width=36,
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

    def _update_preview(self, *_):
        try:
            n = int(self.tic_to_var.get()) - int(self.tic_from_var.get()) + 1
            pages = -(-n // 48)   # ceiling division
            self._prev_lbl.configure(
                text=f"  \u2192  {n} etiquetas  |  {pages} p\u00e1gina(s)  (48 por p\u00e1gina)")
        except ValueError:
            self._prev_lbl.configure(text="")

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

            n = len(labels)
            pages = -(-n // 48)
            self._status_lbl.configure(text=f"\u2713  {n} etiquetas generadas  \u2192  {out_pdf}")
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


# ═════════════════════════════════════════════════════════════════════════════
# App
# ═════════════════════════════════════════════════════════════════════════════
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
    def __init__(self, parent, gateway=None):
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
            (t("gw_field_serial"), gateway.get("serial", "") if gateway else ""),
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
        super().__init__(master, fg_color=("white", "#1e1e2e"), corner_radius=0, border_width=0, label_text="")
        self._gateways = []
        self._refs = {}
        self._build()
        _lang_cbs.append(self._refresh_lang)

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
        dlg = GatewayDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            self._gateways.append(dlg.result)
            self._refresh_list()

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

    def _delete_gateway(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showerror("Error", t("gw_error_select_delete"))
            return
        del self._gateways[idx]
        self._refresh_list()

    def _browse_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Guardar PDF GW como...",
        )
        if path:
            self.pdf_output_var.set(path)

    def _generate_pdf(self):
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
            self._status_lbl.configure(text=t("gw_status_generating"))
            self.update()
            _make_gateway_pdf(self._gateways, output_path, serial_year)
            total = len(self._gateways)
            pages = (total + 4) // 5
            self._status_lbl.configure(text=t("gw_status_done").format(total=total, name=os.path.basename(output_path)))
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
            "firmwares": [("1.0.0_REV2.23.03.2026", "CONTATORE_REL.1.0.0_REV2.23.03.2026.production.INFO.hex")],
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
        "fg_color": ("#E7ECF3", "#223145"),
        "hover_color": ("#D7E0EB", "#2A3B52"),
        "text_color": ("#102235", "#F2F6FB"),
    }
    PIC_BUTTON_ACTIVE_COLORS = {
        "fg_color": ("#1F8F5F", "#1F8F5F"),
        "hover_color": ("#18724C", "#18724C"),
        "text_color": ("#FFFFFF", "#FFFFFF"),
    }

    def __init__(self, master):
        super().__init__(master, fg_color=("white", "#1e1e2e"), corner_radius=0, border_width=0, label_text="")
        self._pic_buttons = {}
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
        for button in self._pic_buttons.values():
            button.configure(**self.PIC_BUTTON_COLORS)

    def _copy_pic(self, pic_name):
        self.clipboard_clear()
        self.clipboard_append(pic_name)
        self._reset_pic_buttons()
        button = self._pic_buttons.get(pic_name)
        if button is not None:
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
            pic_button.pack(side="right", padx=(8, 0))
            self._pic_buttons[item["pic"]] = pic_button

            for fw_label, fw_file in reversed(item["firmwares"]):
                ctk.CTkButton(
                    row_frame,
                    text=fw_label,
                    width=150,
                    command=lambda f=fw_file: self._save_firmware(f),
                    font=ctk.CTkFont(size=11, weight="bold"),
                ).pack(side="right", padx=(8, 0))

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
        super().__init__(master, fg_color=("white", "#1e1e2e"), corner_radius=0, border_width=0, label_text="")
        self._title_lbl = None
        self._desc_lbl = None
        self._section_lbl = None
        self._tool_title_lbl = None
        self._tool_desc_lbl = None
        self._save_btn = None
        self._tool2_title_lbl = None
        self._tool2_desc_lbl = None
        self._save2_btn = None
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

        card = ctk.CTkFrame(self, corner_radius=10, fg_color=("white", "#16202d"))
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

        self._status_lbl = ctk.CTkLabel(self, text=t("serial_status"), text_color=C_HINT)
        self._status_lbl.pack(anchor="w", padx=18, pady=(4, 14))

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
        self._status_lbl.configure(text=t("serial_status"))


class App:
    def __init__(self, root: ctk.CTk):
        self.root = root
        root.title("Device Manager — TECNIDRO")
        # Centrar en pantalla al 90% del monitor disponible (máx 1200×960)
        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w  = min(int(sw * 0.90), 1200)
        h  = min(int(sh * 0.90), 960)
        x  = (sw - w) // 2
        y  = (sh - h) // 2
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(820, 640)

        # ── Header ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(root, corner_radius=0, height=60, fg_color=C_HDR_BG)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="  Device Manager",
                     font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=C_HDR_TEXT).pack(side="left", padx=16, pady=12)
        ctk.CTkLabel(hdr, text="TECNIDRO SRL",
                     font=ctk.CTkFont(size=11),
                     text_color=C_HINT).pack(side="left")

        # Logo — CTkImage cambia automáticamente entre light y dark
        img_l, img_d, dw, dh = _make_logo_images(display_h=52)
        if img_l and img_d:
            logo_ctk = ctk.CTkImage(light_image=img_l, dark_image=img_d,
                                    size=(dw, dh))
            ctk.CTkLabel(hdr, image=logo_ctk, text="",
                         fg_color="transparent").pack(side="right", padx=18)

        # ── Tabview  (nombres FIJOS — no se renombran) ────────────
        # Los tabs tienen nombres neutros cortos; el contenido se traduce.
        self.tabview = ctk.CTkTabview(root, corner_radius=8, border_width=0)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(6, 4))

        # Pestañas principales: RTU  |  GW  |  I-TIC  |  TIC12  |  FW Version  |  ⚙ Language
        T_RTU   = "RTU"
        T_GW    = "GW"
        T_ITIC  = "I-TIC"
        T_TIC12 = "TIC12"
        T_FW    = "FW Version"
        T_SERIAL = "Serial"
        T_LANG  = "⚙  Language"

        for name in (T_RTU, T_GW, T_ITIC, T_TIC12, T_FW, T_SERIAL, T_LANG):
            self.tabview.add(name)

        # GW, I-TIC, TIC12 y FW Version directamente en la barra principal
        GatewayTab(self.tabview.tab(T_GW)).pack(fill="both", expand=True)
        TICLabelTab(self.tabview.tab(T_ITIC),  product_name="I-TIC 1V", title_key="itic_title").pack(fill="both", expand=True)
        TICLabelTab(self.tabview.tab(T_TIC12), product_name="TIC12",    title_key="tic12_title").pack(fill="both", expand=True)
        FWVersionTab(self.tabview.tab(T_FW)).pack(fill="both", expand=True)
        SerialTab(self.tabview.tab(T_SERIAL)).pack(fill="both", expand=True)
        LangTab(self.tabview.tab(T_LANG)).pack(fill="both", expand=True)

        # ── Sub-tabview dentro de RTU: CSV | Etiquetas | JSON | Proyecto ──
        rtu_sub = ctk.CTkTabview(self.tabview.tab(T_RTU),
                                  corner_radius=6, border_width=0)
        rtu_sub.pack(fill="both", expand=True, padx=4, pady=4)
        for sub in ("Proyecto", "CSV", "JSON", "Etichette"):
            rtu_sub.add(sub)
        ProjectTab(rtu_sub.tab("Proyecto")).pack(fill="both", expand=True)
        CSVTab(rtu_sub.tab("CSV")).pack(fill="both", expand=True)
        JSONTab(rtu_sub.tab("JSON")).pack(fill="both", expand=True)
        EtichetteTab(rtu_sub.tab("Etichette")).pack(fill="both", expand=True)

        # ── Status bar ────────────────────────────────────────────
        bar = ctk.CTkFrame(root, corner_radius=0, height=24, fg_color=C_BAR_BG)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text=f"  Generador CSV & Etichette PDF  —  v{APP_VERSION}",
                     font=ctk.CTkFont(size=10),
                     text_color=C_BAR_TEXT).pack(side="left", padx=8)
        ctk.CTkLabel(bar, text="by Manuel Rodriguez  ",
                     font=ctk.CTkFont(size=10),
                     text_color=C_BAR_TEXT).pack(side="right")

        if _load_update_settings().get("auto_check") and str(_load_update_settings().get("manifest_url", "")).strip():
            root.after(1500, lambda: check_for_updates(root, interactive=False))


def main():
    root = ctk.CTk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
