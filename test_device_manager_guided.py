"""Route, wizard and generation checks without touching the live registry."""

from contextlib import ExitStack
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import generador_csv as api
from device_manager_flow import PRODUCTS, VARIANTS, WizardSession, actions_for, firmware_for, manuals_for, NBIOT_FILE
from device_manager_ui import ProductImages
from device_manager_ui_text import TEXT


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "tmp/v128_tests"


class GuidedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.stack = ExitStack()
        cls.saved_callbacks = (list(api._lang_cbs), list(api._serial_refresh_callbacks), list(api._rtu_deveui_refresh_callbacks))
        cls.registry = api._default_serial_registry()
        cls.registry["families"]["RTU"]["last_serial"] = 7997
        cls.registry["families"]["GW"]["last_serial"] = 121
        cls.stack.enter_context(patch.object(api, "_load_update_settings", return_value={"auto_check": False}))
        cls.stack.enter_context(patch.object(api, "_load_serial_settings", return_value=dict(api.DEFAULT_SERIAL_SETTINGS, token="test")))
        cls.stack.enter_context(patch.object(api, "_serial_registry_fetch", return_value=copy.deepcopy(cls.registry)))
        cls.stack.enter_context(patch.object(api, "_serial_registry_fetch_cached", return_value=copy.deepcopy(cls.registry)))
        cls.stack.enter_context(patch.object(api, "_prepare_serial_settings_for_write", return_value={}))
        cls.record = cls.stack.enter_context(patch.object(api, "_serial_registry_update_last", return_value=cls.registry))
        cls.gwrecord = cls.stack.enter_context(patch.object(api, "_serial_registry_update_gateways", return_value=cls.registry))
        cls.stack.enter_context(patch.object(api, "_notify_serial_registry_changed"))
        cls.stack.enter_context(patch.object(api, "_set_next_rtu_deveui"))
        cls.stack.enter_context(patch.object(api, "_desktop_dir", return_value=str(OUT)))
        cls.stack.enter_context(patch.object(api.messagebox, "showinfo"))
        cls.errors = cls.stack.enter_context(patch.object(api.messagebox, "showerror"))
        cls.root = api.ctk.CTk()
        cls.root.withdraw()
        cls.callback_errors = []
        cls.root.report_callback_exception = lambda *args: cls.callback_errors.append(str(args))
        cls.engine = api.App(cls.root)
        cls.engine.prefs_path = OUT / "ui_preferences.json"
        cls.sessions = []

    @classmethod
    def tearDownClass(cls):
        cls.engine.closed = True
        for identifier in cls.root.tk.call("after", "info"):
            cls.root.after_cancel(identifier)
        cls.root.destroy()
        for callbacks, saved in zip((api._lang_cbs, api._serial_refresh_callbacks, api._rtu_deveui_refresh_callbacks), cls.saved_callbacks):
            callbacks[:] = saved
        cls.stack.close()

    def session(self, product, variant, action):
        session = WizardSession(api, self.engine.hidden_forms, product, variant, action)
        session.sync_serial(copy.deepcopy(self.registry))
        self.sessions.append(session)
        return session

    def test_01_device_actions_match_approved_scope(self):
        self.assertEqual(actions_for("RTU", "nbiot"), ("firmware",))
        self.assertEqual(actions_for("Gateway"), ("labels", "shutdown"))
        self.assertEqual(actions_for("Istantaneo"), ("labels", "firmware"))
        for product in ("I-TIC", "TIC12"):
            self.assertEqual(actions_for(product), ("labels", "firmware", "manual"))
        self.assertIn("guide", actions_for("LORACONT"))
        self.assertNotIn("manual", actions_for("LORACONT"))
        self.assertEqual(VARIANTS["RTU"], ("blte", "nortu", "tubo", "nbiot"))

    def test_02_firmware_filtering(self):
        for variant in ("AC", "DC"):
            for item in firmware_for(api, "TIC12", variant):
                self.assertTrue(item["firmwares"])
                self.assertTrue(all(label.startswith(variant) for label, _ in item["firmwares"]))
        self.assertEqual(firmware_for(api, "RTU", "nbiot")[0]["pic"], "PIC24FJ128GL306")
        self.assertEqual(firmware_for(api, "RTU", "nbiot")[0]["firmwares"][0][1], NBIOT_FILE)
        self.assertEqual(len(firmware_for(api, "I-TIC", "rev4")), 1)
        self.assertEqual(firmware_for(api, "I-TIC", "rev4")[0]["label_key"], "fw_item_rev4")
        self.assertTrue(all(item["label_key"] != "fw_item_loracont" for item in firmware_for(api, "RTU", "blte")))
        self.assertEqual(len(firmware_for(api, "LORACONT")), 1)
        for variant, new in (("new", True), ("old", False)):
            self.assertTrue(all((item["label_key"] == "fw_item_new") == new for item in firmware_for(api, "Istantaneo", variant)))

    def test_03_manual_scope(self):
        self.assertFalse(manuals_for(api, "Gateway"))
        self.assertFalse(manuals_for(api, "Istantaneo"))
        self.assertEqual(len(manuals_for(api, "LORACONT")), 2)
        self.assertEqual(len(manuals_for(api, "I-TIC")), 2)
        self.assertEqual(len(manuals_for(api, "TIC12")), 1)

    def test_04_every_form_has_valid_bindings(self):
        for product in PRODUCTS:
            variants = VARIANTS.get(product, ("",))
            for variant in variants:
                for action in actions_for(product, variant):
                    if action not in ("project", "csv", "json", "labels"):
                        continue
                    with self.subTest(product=product, variant=variant, action=action):
                        session = self.session(product, variant, action)
                        for step in session.steps():
                            for field in step.fields:
                                self.assertIsNotNone(session.field_var(field))
                                self.assertTrue(field.label in TEXT or field.label in api.TRANSLATIONS["it"], field.label)
                        if session.kind == "loracont":
                            attrs = [field.attr for step in session.steps() for field in step.fields]
                            self.assertNotIn("p_json_valves", attrs)
                            self.assertNotIn("json_valves", attrs)

    def test_05_counter_and_quantity_behavior(self):
        for variant in ("new", "old"):
            session = self.session("Istantaneo", variant, "labels")
            self.assertEqual(session.value("tic_from"), "0001")
            session.quantity_var.set("5")
            self.assertEqual(session.value("tic_to"), "0005")
            self.assertEqual(session.serial_range(), "0001 - 0005")
            session.tool.tic_fw_var.set("1000L")
            self.assertEqual(session.family, "Istantaneo")
        for product in ("RTU", "LORACONT"):
            session = self.session(product, "blte" if product == "RTU" else "", "project")
            self.assertEqual(session.value("p_ser_start"), "07998")

    def test_06_generation_and_preview_do_not_change_formats(self):
        for product, variant in (("RTU", "blte"), ("LORACONT", "")):
            for action in ("project", "csv", "json", "labels"):
                with self.subTest(product=product, action=action):
                    session = self.session(product, variant, action)
                    if action == "project":
                        session.tool.proj_name_var.set(f"test_{product}_project")
                        session.tool.p_to_var.set(session.tool.p_from_var.get())
                    elif action == "csv":
                        session.tool.end_number_var.set(session.tool.start_number_var.get())
                    elif action == "json":
                        session.tool.j_to_var.set(session.tool.j_from_var.get())
                    self.errors.reset_mock()
                    self.record.reset_mock()
                    preview, text = session.preview(str(OUT))
                    self.record.assert_not_called()
                    self.assertTrue(preview or text)
                    result = session.generate()
                    self.errors.assert_not_called()
                    self.assertIsNotNone(result)
                    self.assertEqual(result["count"], 1)
                    for path in result["files"]:
                        self.assertTrue(Path(path).exists())
                    if action in ("project", "csv"):
                        csv_path = result["files"][0]
                        with open(csv_path, encoding="utf-8", newline="") as stream:
                            row = next(csv.DictReader(stream, delimiter=";"))
                        self.assertEqual(row["Model"], "297" if product == "LORACONT" else "210")
                    if action in ("project", "json"):
                        folder = result["files"][1] if action == "project" else result["files"][0]
                        data = json.loads(next(Path(folder).glob("*.JSON")).read_text())
                        self.assertNotIn("childnumber", json.dumps(data))
                        self.assertEqual(data["device"]["numvalves"], 0 if product == "LORACONT" else 1)

    def test_07_gateway_data_independent_and_serials_shared(self):
        session = self.session("Gateway", "", "labels")
        session.quantity_var.set("2")
        session.ensure_gateways()
        for index, values in enumerate(session.gateway_vars):
            values["alias"].set(f"Gateway Test {index}")
            values["mac"].set(f"0011223344{index:02X}")
            values["dev_eui"].set(f"70B3D57ED007{index:04X}")
        self.assertEqual(session.gateway_vars[0]["serial"].get(), "122")
        self.assertEqual(session.gateway_vars[1]["serial"].get(), "123")
        session.tool.pdf_output_var.set(str(OUT / "Gateway.pdf"))
        self.gwrecord.reset_mock()
        session.preview(str(OUT))
        self.gwrecord.assert_not_called()
        result = session.generate()
        self.assertEqual(result["count"], 2)
        self.assertEqual(self.gwrecord.call_args.args[1], [122, 123])

    def test_08_labels_both_istantaneo_variants(self):
        for product, variant in (("I-TIC", "rev4"), ("I-TIC", "rev6"), ("TIC12", "AC"),
                                 ("TIC12", "DC"), ("Istantaneo", "new"), ("Istantaneo", "old")):
            session = self.session(product, variant, "labels")
            session.quantity_var.set("5")
            session.tool.tic_pdf_var.set(str(OUT / f"Labels_{product}_{variant}.pdf"))
            self.errors.reset_mock()
            self.record.reset_mock()
            session.preview(str(OUT))
            self.record.assert_not_called()
            result = session.generate()
            self.errors.assert_not_called()
            self.assertEqual(result["count"], 5)
            self.assertEqual(self.record.call_args.args[1], product)

    def test_09_offline_blocks_label_generation(self):
        session = self.session("Istantaneo", "new", "labels")
        session.serial_ready = False
        with self.assertRaisesRegex(RuntimeError, "serial_not_ready"):
            session.generate()

    def test_10_screen_navigation_and_translation(self):
        self.engine.registry = copy.deepcopy(self.registry)
        self.engine.show_home()
        for product in PRODUCTS:
            self.engine.choose_product(product)
            for variant in VARIANTS.get(product, ("",)):
                self.engine.show_actions(product, variant)
                for action in actions_for(product, variant):
                    if product == "Gateway" and action == "labels":
                        continue
                    self.engine.start_action(product, variant, action)
                    self.root.update_idletasks()
        self.engine.show_utility("terminals")
        self.engine.show_settings()
        for language in ("es", "en", "it"):
            api._cur_lang[0] = language
            self.engine.language_refresh()
            self.engine.show_home()
            self.root.update_idletasks()
        self.engine.toggle_theme()
        self.engine.toggle_theme()
        self.assertFalse(self.callback_errors, self.callback_errors)

    def test_11_previous_menu_every_route_preserves_draft(self):
        engine = self.engine
        engine.show_home()
        self.assertEqual(engine.previous_menu_button.cget("state"), "disabled")
        engine.choose_product("TIC12")
        engine.previous_menu_button.invoke()
        self.assertEqual(engine.active_route, ("home",))
        engine.show_actions("TIC12", "AC")
        engine.previous_menu_button.invoke()
        self.assertEqual(engine.active_route, ("variants", "TIC12"))
        engine.start_action("TIC12", "AC", "labels")
        key = ("TIC12", "AC", "labels")
        engine.sessions[key].quantity_var.set("7")
        engine.previous_menu_button.invoke()
        self.assertEqual(engine.active_route, ("actions", "TIC12", "AC"))
        engine.start_action("TIC12", "AC", "labels")
        self.assertEqual(engine.sessions[key].quantity_var.get(), "7")
        for action in ("firmware", "manual"):
            engine.start_action("TIC12", "DC", action)
            engine.previous_menu_button.invoke()
            self.assertEqual(engine.active_route, ("actions", "TIC12", "DC"))
        engine.show_shutdown()
        engine.previous_menu_button.invoke()
        self.assertEqual(engine.active_route, ("actions", "Gateway", ""))
        engine.previous_menu_button.invoke()
        self.assertEqual(engine.active_route, ("home",))
        for utility in ("firmwares", "manuals", "terminals", "settings"):
            engine.show_utility(utility)
            engine.previous_menu_button.invoke()
            self.assertEqual(engine.active_route, ("home",))

    def test_12_icons_and_product_buttons_in_all_languages(self):
        for language in ("it", "es", "en"):
            api._cur_lang[0] = language
            self.engine.language_refresh()
            self.engine.show_home()
            self.assertEqual(set(self.engine.product_buttons), set(PRODUCTS))
            for button in self.engine.product_buttons.values():
                self.assertEqual(button.cget("text"), self.engine.tr("open_device"))
                self.assertIsNotNone(button.cget("image"))
            for key in ("firmwares", "manuals", "terminals", "settings"):
                button = self.engine.utility_buttons[key]
                self.assertIsNotNone(button.cget("image"))
                self.assertEqual(button.cget("text"), self.engine.tr(key))
            self.assertEqual(self.engine.previous_menu_button.cget("text"), self.engine.tr("previous_menu"))
        api._cur_lang[0] = "it"

    def test_13_firmware_library_compact_and_complete(self):
        self.engine.show_firmware()
        self.assertEqual(self.engine.firmware_section_names, ["RTU", "LORACONT", "RTU NBIoT", "TIC12", "I-TIC", "Istantaneo"])
        expected = [filename for section in api.FW_DOWNLOADS.values() for item in section for _, filename in item["firmwares"]]
        actual = [filename for _, filename, _ in self.engine.firmware_row_buttons]
        self.assertCountEqual(actual, expected + [NBIOT_FILE])
        self.assertTrue(all(button.cget("height") <= 34 for _, _, button in self.engine.firmware_row_buttons))
        self.engine.show_firmware("TIC12", "DC")
        self.assertEqual(self.engine.firmware_section_names, ["TIC12"])
        self.assertTrue(all("DC" in filename for _, filename, _ in self.engine.firmware_row_buttons))
        first, second = self.engine.pic_buttons[:2]
        self.engine.copy_pic(first.cget("text"), first)
        self.assertEqual(first.cget("fg_color"), "#1f8f5f")
        self.assertEqual(second.cget("fg_color"), "#223145")
        self.engine.copy_pic(second.cget("text"), second)
        self.assertEqual(first.cget("fg_color"), "#223145")
        self.assertEqual(second.cget("fg_color"), "#1f8f5f")
        self.root.update_idletasks()
        self.assertFalse(self.callback_errors, self.callback_errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
