"""Guided routes and bindings to the existing, format-stable generators."""

from dataclasses import dataclass
from datetime import datetime
import copy
import csv
import json
import os
from pathlib import Path
import tempfile
import tkinter as tk


PRODUCTS = ("RTU", "LORACONT", "Gateway", "I-TIC", "TIC12", "Istantaneo")
VARIANTS = {
    "RTU": ("blte", "nortu", "tubo", "nbiot"),
    "I-TIC": ("rev6", "rev4"),
    "TIC12": ("AC", "DC"),
    "Istantaneo": ("new", "old"),
}
NBIOT_FILE = "pic24_Radio_NBIOT_2CH.Xver_1.6_02.11.2026.production.hex"


def actions_for(product, variant=""):
    if product == "RTU":
        return ("firmware",) if variant == "nbiot" else ("project", "csv", "json", "labels", "firmware")
    if product == "LORACONT":
        return ("project", "csv", "json", "labels", "firmware", "guide")
    if product == "Gateway":
        return ("labels", "shutdown")
    if product in ("I-TIC", "TIC12"):
        return ("labels", "firmware", "manual")
    if product == "Istantaneo":
        return ("labels", "firmware")
    raise ValueError("Unknown device: " + product)


def firmware_for(api, product, variant=""):
    if product == "Gateway":
        return []
    if product == "RTU" and variant == "nbiot":
        return [{"label_key": "NBIoT", "pic": "PIC24FJ128GL306",
                 "firmwares": [("NBIoT 1.6 - 02.11.2026", NBIOT_FILE)]}]
    if product in ("RTU", "LORACONT"):
        return [copy.deepcopy(item) for item in api.FW_DOWNLOADS["RTU"]
                if (item["label_key"] == "fw_item_loracont") == (product == "LORACONT")]
    if product == "TIC12":
        groups = copy.deepcopy(api.FW_DOWNLOADS["TIC12"])
        for item in groups:
            item["firmwares"] = [(label, path) for label, path in item["firmwares"]
                                 if not variant or label.split("/")[0].split()[0] == variant]
        return groups
    if product == "I-TIC":
        return [copy.deepcopy(item) for item in api.FW_DOWNLOADS["FUNGHI"]
                if item["label_key"] == ("fw_item_rev4" if variant == "rev4" else "fw_item_rev6")]
    if product == "Istantaneo":
        return [copy.deepcopy(item) for item in api.FW_DOWNLOADS["INSTANTANEI"]
                if (item["label_key"] == "fw_item_new") == (variant != "old")]
    return []


def manuals_for(api, product):
    key = {"I-TIC": "manuals_group_itic", "TIC12": "manuals_group_tic12",
           "LORACONT": "manuals_group_loracont"}.get(product)
    return next((list(paths) for group, paths in api.ManualsTab.MANUAL_GROUPS if group == key), [])


@dataclass(frozen=True)
class Field:
    attr: str
    label: str
    kind: str = "text"
    choices: tuple = ()
    required: bool = True
    minimum: int = 0
    maximum: int = 999999999


@dataclass(frozen=True)
class Step:
    key: str
    fields: tuple


class WizardSession:
    def __init__(self, api, parent, product, variant, action):
        if action not in actions_for(product, variant) or action not in ("project", "csv", "json", "labels"):
            raise ValueError("This device does not support the requested generator.")
        self.api, self.product, self.variant, self.action = api, product, variant, action
        self.kind = "loracont" if product == "LORACONT" else "rtu"
        self.quantity_var = tk.StringVar(master=parent, value="1")
        self.gateway_vars = []
        self.serial_ready = False
        self.result = None
        self._csv_loaded = ""
        self._temporary = None
        if action == "project":
            self.tool = api.ProjectTab(parent, device_kind=self.kind, auto_sync=False)
        elif action == "csv":
            self.tool = api.CSVTab(parent, device_kind=self.kind)
        elif action == "json":
            self.tool = api.JSONTab(parent, device_kind=self.kind)
        elif product == "Gateway":
            self.tool = api.GatewayTab(parent, auto_sync=False)
        elif product in ("RTU", "LORACONT"):
            self.tool = api.EtichetteTab(parent, device_kind=self.kind, auto_sync=False)
        else:
            name, title = {"I-TIC": ("I-TIC 1V", "itic_title"), "TIC12": ("TIC12", "tic12_title"),
                           "Istantaneo": ("ISTANTANEO", "istantaneo_title")}[product]
            self.tool = api.TICLabelTab(parent, name, title, auto_sync=False)
        self.tool._guided_mode = True
        self._defaults()

    @property
    def needs_serial(self):
        return self.action in ("project", "labels")

    @property
    def family(self):
        return "RTU" if self.product in ("RTU", "LORACONT") else "GW" if self.product == "Gateway" else self.product

    def var(self, attr):
        return self.quantity_var if attr == "quantity" else getattr(self.tool, attr + "_var")

    def value(self, attr):
        return str(self.var(attr).get()).strip()

    def _defaults(self):
        t = self.tool
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.default_name = f"{self.product}_{self.variant or '1'}_{stamp}"
        if self.action == "project":
            t.root_folder_var.set(self.api._desktop_dir())
            t.proj_name_var.set("Progetto_" + self.default_name)
            t.p_label_var.set("loracont" if self.kind == "loracont" else self.variant)
            t.p_ser_year_var.set(str(datetime.now().year))
        elif self.action == "csv":
            t.csv_output_var.set(os.path.join(self.api._desktop_dir(), "CSV Nodi " + self.default_name + ".csv"))
        elif self.action == "json":
            t.out_folder_var.set(os.path.join(self.api._desktop_dir(), "JSON_" + self.default_name))
        elif self.product in ("RTU", "LORACONT"):
            t.label_type_var.set("loracont" if self.kind == "loracont" else self.variant)
            t.m_to_var.set(t.m_from_var.get())
            t.serial_year_var.set(str(datetime.now().year))
        elif self.product == "Gateway":
            self.ensure_gateways()
        else:
            t.tic_yr_var.set(str(datetime.now().year))
            if self.product == "I-TIC":
                item = firmware_for(self.api, self.product, self.variant)[0]
                t.tic_fw_var.set(item["firmwares"][0][0].lstrip("Vv"))
            t.tic_to_var.set(t.tic_from_var.get())
            self.quantity_var.trace_add("write", self._update_quantity)
            t.tic_from_var.trace_add("write", self._update_quantity)

    def _update_quantity(self, *_):
        try:
            start, count = int(self.value("tic_from")), int(self.quantity_var.get())
            if count > 0:
                self.tool.tic_to_var.set(f"{start + count - 1:04d}")
        except ValueError:
            pass

    def sync_serial(self, registry):
        if not self.needs_serial or self.result:
            return
        start = int(registry["families"][self.family]["last_serial"]) + 1
        width = self.api.SERIAL_FAMILY_SETTINGS[self.family]["number_width"]
        if self.action == "project":
            self.tool.p_ser_start_var.set(f"{start:0{width}d}")
            self.tool._apply_next_rtu_deveui(self.api._get_next_rtu_deveui())
        elif self.product in ("RTU", "LORACONT"):
            self.tool.serial_start_var.set(f"{start:0{width}d}")
        elif self.product == "Gateway":
            self._gateway_start = start
            self.ensure_gateways()
            for index, variables in enumerate(self.gateway_vars):
                variables["serial"].set(str(start + index))
        else:
            self.tool.tic_from_var.set(f"{start:0{width}d}")
        self.serial_ready = True

    def ensure_gateways(self):
        try:
            count = int(self.quantity_var.get())
        except ValueError:
            return
        if not 1 <= count <= 500:
            return
        while len(self.gateway_vars) < count:
            index = len(self.gateway_vars)
            self.gateway_vars.append({key: tk.StringVar(master=self.tool, value=value) for key, value in {
                "model": "GW X4S LTE", "alias": "", "serial": str(getattr(self, "_gateway_start", 1) + index),
                "mac": "", "dev_eui": "",
            }.items()})
        self.tool._gateways = [{key: var.get().strip() for key, var in row.items()}
                               for row in self.gateway_vars[:count]]
        self.tool._update_auto_pdf_output()

    def steps(self):
        F = Field
        if self.product == "Gateway":
            self.ensure_gateways()
            steps = [Step("quantity", (F("quantity", "quantity", "integer", minimum=1, maximum=500),
                                       F("serial_year", "gw_year", "year")))]
            try:
                count = max(1, min(500, int(self.quantity_var.get())))
            except ValueError:
                count = 1
            for index in range(count):
                steps.append(Step(f"gateway:{index}", tuple(F(f"gw:{index}:{key}", label, kind) for key, label, kind in (
                    ("model", "gw_field_model", "text"), ("alias", "gw_field_alias", "text"),
                    ("serial", "gw_field_serial", "readonly"), ("mac", "gw_field_mac", "hex12"),
                    ("dev_eui", "gw_field_deveui", "hex16")))))
            steps.append(Step("output", (F("pdf_output", "gw_output", "pdf"),)))
            return steps
        if self.action == "project":
            return [Step("project", (F("root_folder", "lbl_root_fld", "folder"), F("proj_name", "lbl_proj_nm"))),
                    Step("devices", self._name_fields("p_prefix", "p_from", "p_to", "p_deveui")),
                    Step("radio", self._radio_fields("p_model", "p_newskey", "p_appskey", "p_lat", "p_lon", "p_childnumber")),
                    Step("serial", (F("p_ser_start", "lbl_ser_start", "readonly"), F("p_ser_year", "lbl_year", "year"))),
                    Step("configuration", self._json_fields(project=True))]
        if self.action == "csv":
            return [Step("devices", self._name_fields("name_prefix", "start_number", "end_number", "start_dev_eui")),
                    Step("radio", self._radio_fields("model", "new_skey", "app_skey", "latitude", "longitude", "childnumber")),
                    Step("output", (F("devstatusreqinterval", "devStatusReqInterval", "integer"),
                                    F("csv_output", "lbl_out_file", "csv")))]
        if self.action == "json":
            return [Step("devices", self._name_fields("j_prefix", "j_from", "j_to", "j_deveui")),
                    Step("configuration", self._json_fields(project=False)),
                    Step("output", (F("out_folder", "lbl_out_folder", "folder"),))]
        if self.product in ("RTU", "LORACONT"):
            return [Step("devices", (F("csv_input", "optional_csv", "csv_input", required=False),) +
                         self._name_fields("m_prefix", "m_from", "m_to", "m_deveui")),
                    Step("serial", (F("serial_start", "lbl_ser_start", "readonly"), F("serial_year", "lbl_year", "year"))),
                    Step("output", (F("pdf_output", "lbl_pdf_out", "pdf"),))]
        return [Step("labels_data", (F("tic_from", "lbl_tic_from", "readonly"),
                                     F("quantity", "quantity", "integer", minimum=1, maximum=100000),
                                     F("tic_yr", "lbl_tic_yr", "year"),
                                     F("tic_fw", "lbl_istantaneo_version" if self.product == "Istantaneo" else "lbl_tic_fw",
                                       "choice" if self.product == "Istantaneo" else "text",
                                       ("100L", "1000L") if self.product == "Istantaneo" else ()))),
                Step("output", (F("tic_pdf", "lbl_tic_pdf", "pdf"),))]

    def _name_fields(self, prefix, start, end, deveui):
        return (Field(prefix, "lbl_prefix"), Field(start, "lbl_from", "integer"),
                Field(end, "lbl_to", "integer"), Field(deveui, "lbl_deveui", "hex16"))

    def _radio_fields(self, model, nwk, app, lat, lon, child):
        fields = [Field(model, "lbl_model", "readonly"), Field(nwk, "lbl_newskey", "hex32"),
                  Field(app, "lbl_appskey", "hex32"), Field(lat, "lbl_lat", required=False),
                  Field(lon, "lbl_lon", required=False)]
        if self.kind != "loracont":
            fields.append(Field(child, "csv_valves", "integer", maximum=8))
        return tuple(fields)

    def _json_fields(self, project):
        prefix = "p_json_" if project else "json_"
        attr = lambda name: prefix + name
        fields = [Field(attr("adc"), "lbl_json_adc", "choice", ("0", "1")),
                  Field(attr("counters"), "lbl_json_counters", "choice",
                        tuple(map(str, range(2 if self.kind == "loracont" else 9))))]
        if self.kind != "loracont":
            fields.extend((Field("p_valve" if project else "valve", "sec_valve", "choice", ("motorizzata", "elba")),
                           Field(attr("valves"), "lbl_json_valves", "choice", tuple(map(str, range(9)))),
                           Field(attr("valvestatus"), "lbl_json_valvestatus", "choice", ("0", "1")),
                           Field("p_motorduration" if project else "j_motorduration", "lbl_motorduration", "integer")))
        fields.extend((Field("p_allarme" if project else "allarme", "sec_allarme", "choice", ("on", "off")),
                       Field("p_sendinterval" if project else "j_sendinterval", "lbl_sendinterval", "integer")))
        return tuple(fields)

    def field_var(self, field):
        if field.attr.startswith("gw:"):
            _, index, key = field.attr.split(":")
            return self.gateway_vars[int(index)][key]
        return self.var(field.attr)

    def validate_step(self, step):
        for field in step.fields:
            value = str(self.field_var(field).get()).strip()
            if not value:
                if field.required:
                    raise ValueError(field.label)
                continue
            if field.kind == "integer":
                if not value.isdecimal() or not field.minimum <= int(value) <= field.maximum:
                    raise ValueError(field.label)
            elif field.kind.startswith("hex"):
                value = value.replace(":", "").replace("-", "").replace(" ", "")
                if len(value) != int(field.kind[3:]) or any(c not in "0123456789abcdefABCDEF" for c in value):
                    raise ValueError(field.label)
                self.field_var(field).set(value.upper())
            elif field.kind == "year" and (len(value) != 4 or not value.isdecimal()):
                raise ValueError(field.label)
            elif field.kind == "choice" and value not in field.choices:
                raise ValueError(field.label)
            elif field.kind == "csv_input" and not os.path.isfile(value):
                raise ValueError(field.label)
        if step.key == "devices":
            start, end = self.device_range()
            if end < start or end - start + 1 > 100000:
                raise ValueError("lbl_to")
        if self.action == "project" and step.key == "project":
            name = self.value("proj_name")
            if name in (".", "..") or any(c in name for c in '<>:"/\\|?*'):
                raise ValueError("lbl_proj_nm")

    def validate_all(self):
        for step in self.steps():
            self.validate_step(step)
        if self.product == "Gateway":
            macs, euis = [], []
            for values in self.gateway_vars[:int(self.quantity_var.get())]:
                macs.append(values["mac"].get().upper())
                euis.append(values["dev_eui"].get().upper())
            if len(set(macs)) != len(macs):
                raise ValueError("gw_field_mac")
            if len(set(euis)) != len(euis):
                raise ValueError("gw_field_deveui")

    def device_range(self):
        first, last = {"project": ("p_from", "p_to"), "csv": ("start_number", "end_number"),
                       "json": ("j_from", "j_to"), "labels": ("m_from", "m_to")}[self.action]
        return int(self.value(first)), int(self.value(last))

    def _manual_devices(self):
        t = self.tool
        if self.action == "project":
            prefix, first, last, eui = (self.value(x) for x in ("p_prefix", "p_from", "p_to", "p_deveui"))
        else:
            path = self.value("csv_input")
            if path:
                with open(path, newline="", encoding="utf-8-sig") as stream:
                    records = list(csv.DictReader(stream, delimiter=";"))
                if not records or not all(row.get("Name") and len(row.get("DevEUI", "")) == 16 for row in records):
                    raise ValueError("optional_csv")
                for row in records:
                    int(row["DevEUI"], 16)
                t._devices = [{"name": row["Name"], "dev_eui": row["DevEUI"].upper(),
                               "dev_addr": row.get("DevAddr") or row["DevEUI"][-8:]} for row in records]
                return t._devices
            t._devices = []
            prefix, first, last, eui = (self.value(x) for x in ("m_prefix", "m_from", "m_to", "m_deveui"))
        return [{"name": f"{prefix}{number:0{len(first)}d}", "dev_eui": f"{int(eui,16)+i:016X}",
                 "dev_addr": f"{int(eui,16)+i:016X}"[-8:]} for i, number in enumerate(range(int(first), int(last)+1))]

    def prepare(self):
        self.validate_all()
        if self.product == "Gateway":
            self.tool._gateways = [{key: var.get().strip() for key, var in row.items()}
                                   for row in self.gateway_vars[:int(self.quantity_var.get())]]
        elif self.action == "labels" and self.product in ("RTU", "LORACONT"):
            self._manual_devices()

    def count(self):
        if self.product == "Gateway" or self.product in ("I-TIC", "TIC12", "Istantaneo"):
            return int(self.quantity_var.get())
        if self.action == "labels" and self.value("csv_input"):
            return len(self._manual_devices())
        start, end = self.device_range()
        return end - start + 1

    def output_paths(self):
        if self.action == "project":
            directory = os.path.join(self.value("root_folder"), self.value("proj_name"))
            name = self.value("proj_name")
            return [os.path.join(directory, "CSV", name + ".csv"), os.path.join(directory, "JSON"),
                    os.path.join(directory, "etiquette", name + ".pdf")]
        attr = "csv_output" if self.action == "csv" else "out_folder" if self.action == "json" else (
            "pdf_output" if self.product in ("RTU", "LORACONT", "Gateway") else "tic_pdf")
        return [self.value(attr)]

    def serial_range(self):
        if not self.needs_serial:
            return ""
        if self.product == "Gateway":
            return f"{self.gateway_vars[0]['serial'].get()} - {self.gateway_vars[self.count()-1]['serial'].get()}"
        attr = "p_ser_start" if self.action == "project" else "serial_start" if self.product in ("RTU", "LORACONT") else "tic_from"
        first = self.value(attr)
        return f"{first} - {int(first) + self.count() - 1:0{len(first)}d}"

    def preview(self, folder):
        """Render only a first-page sample. Never touch counters or customer address blocks."""
        self.prepare()
        if self.action in ("csv", "json"):
            return None, self.preview_text()
        path = str(Path(folder) / "anteprima.pdf")
        if self.product == "Gateway":
            self.api._make_gateway_pdf(self.tool._gateways[:5], path, self.value("serial_year"))
        elif self.product in ("RTU", "LORACONT"):
            records = self._manual_devices()
            capacity = 20 if self.kind == "loracont" else {"blte": 22, "nortu": 28, "tubo": 14}[self.variant]
            serial_attr, year_attr = ("p_ser_start", "p_ser_year") if self.action == "project" else ("serial_start", "serial_year")
            raw, year = self.value(serial_attr), self.value(year_attr)
            devices = [dict(row, serial=f"{int(raw)+i:0{len(raw)}d}/{year}") for i, row in enumerate(records[:capacity])]
            self.api._make_pdf(devices, path, include_bluetooth=self.variant == "blte",
                               rtu_header=self.variant == "tubo", loraconta=self.kind == "loracont")
        else:
            name = {"I-TIC": "I-TIC 1V", "TIC12": "TIC12", "Istantaneo": "ISTANTANEO"}[self.product]
            width = 4 if self.product == "Istantaneo" else 5
            records = [{"serial": f"{int(self.value('tic_from'))+i:0{width}d}/{self.value('tic_yr')}",
                        "fw": self.value("tic_fw")} for i in range(min(self.count(), self.api.tic_page_capacity(name)))]
            self.api._make_tic_pdf(records, path, name)
        return path, ""

    def preview_text(self):
        if self.action == "project":
            prefix, first, eui = (self.value(x) for x in ("p_prefix", "p_from", "p_deveui"))
            root = "p_"
        elif self.action == "json":
            prefix, first, eui = (self.value(x) for x in ("j_prefix", "j_from", "j_deveui"))
            root = ""
        else:
            attrs = ("name_prefix", "start_number", "start_dev_eui")
            prefix, first, eui = (self.value(x) for x in attrs)
            lines = ["Name;Model;DevEUI;DevAddr"]
            for i in range(min(5, self.count())):
                de = f"{int(eui,16)+i:016X}"
                lines.append(f"{prefix}{int(first)+i:0{len(first)}d};{self.value('model')};{de};{de[-8:]}")
            return "\n".join(lines)
        project = self.action == "project"
        get = lambda key: self.value(("p_json_" if project else "json_") + key)
        de = f"{int(eui,16):016X}"
        data = self.api._build_json(de, de[-8:], self.kind,
            self.value("p_allarme" if project else "allarme") == "on",
            int(self.value("p_sendinterval" if project else "j_sendinterval")),
            get("adc"), get("counters"), "0" if self.kind == "loracont" else get("valves"),
            self.value("p_valve" if project else "valve"), get("valvestatus"),
            int(self.value("p_motorduration" if project else "j_motorduration")))
        return f"{prefix}{first}.JSON\n\n" + json.dumps(data, indent=2)

    def generate(self):
        self.prepare()
        if self.needs_serial and not self.serial_ready:
            raise RuntimeError("serial_not_ready")
        for path in self.output_paths():
            if self.action == "json" or path.endswith(os.sep + "JSON"):
                os.makedirs(path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        method = {"project": "_generate_all", "csv": "_generate", "json": "_generate",
                  "labels": "_generate_pdf" if self.product in ("RTU", "LORACONT", "Gateway") else "_generate"}[self.action]
        self.result = getattr(self.tool, method)()
        return self.result
