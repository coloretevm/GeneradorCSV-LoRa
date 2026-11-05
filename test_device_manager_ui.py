"""Hidden-window integration checks; never write to the live GitHub counters."""

from contextlib import ExitStack
import csv
import json
from pathlib import Path
import traceback
import unittest
from unittest.mock import patch

import generador_csv as app


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "tmp/v127_ui"


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.stack = ExitStack()
        cls.registry = app._default_serial_registry()
        cls.registry["families"]["RTU"]["last_serial"] = 7997
        cls.stack.enter_context(patch.object(app, "_load_update_settings", return_value={"auto_check": False}))
        cls.stack.enter_context(patch.object(app, "_load_serial_settings", return_value=dict(app.DEFAULT_SERIAL_SETTINGS, token="test")))
        cls.stack.enter_context(patch.object(app, "_serial_registry_fetch_cached", return_value=cls.registry))
        cls.stack.enter_context(patch.object(app, "_serial_registry_fetch", return_value=cls.registry))
        cls.stack.enter_context(patch.object(app, "_prepare_serial_settings_for_write", return_value={}))
        cls.record = cls.stack.enter_context(patch.object(app, "_serial_registry_update_last", return_value=cls.registry))
        cls.stack.enter_context(patch.object(app, "_notify_serial_registry_changed"))
        cls.stack.enter_context(patch.object(app, "_set_next_rtu_deveui"))
        cls.info = cls.stack.enter_context(patch.object(app.messagebox, "showinfo"))
        cls.errors = cls.stack.enter_context(patch.object(app.messagebox, "showerror"))
        cls.root = app.ctk.CTk()
        cls.root.withdraw()
        cls.callback_errors = []
        cls.root.report_callback_exception = lambda *args: cls.callback_errors.append("".join(traceback.format_exception(*args)))
        cls.engine = app.App(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.root.destroy()
        cls.stack.close()

    def tool(self, workspace, sub):
        self.engine._show_section(workspace)
        self.engine._show_rtu_section(sub)
        frame = self.engine._workspace_views[workspace][sub]
        return next(widget for widget in descendants(frame)
                    if isinstance(widget, (app.ProjectTab, app.CSVTab, app.JSONTab, app.EtichetteTab)))

    def test_01_lazy_start_and_sidebar(self):
        self.assertEqual(self.engine._loaded_tabs, {("RTU", "Proyecto")})
        self.assertFalse(self.engine._loaded_sections)
        self.assertEqual(list(self.engine._views)[:2], ["RTU", "LORACONT"])
        self.assertIn("Istantaneo", self.engine._views)

    def test_02_separate_workspace_models_and_controls(self):
        for workspace, kind, model in (("RTU", "rtu", "210"), ("LORACONT", "loracont", "297")):
            project = self.tool(workspace, "Proyecto")
            csv_tool = self.tool(workspace, "CSV")
            json_tool = self.tool(workspace, "JSON")
            label_tool = self.tool(workspace, "Etichette")
            self.assertEqual(project.p_model_var.get(), model)
            self.assertEqual(csv_tool.model_var.get(), model)
            self.assertEqual(json_tool.json_model_var.get(), kind)
            expected = "loracont" if kind == "loracont" else "nortu"
            self.assertEqual(project.p_label_var.get(), expected)
            self.assertEqual(label_tool.label_type_var.get(), expected)
            options = [widget.cget("value") for widget in label_tool.winfo_children()
                       if isinstance(widget, app.ctk.CTkRadioButton)]
            self.assertEqual(options, ["loracont"] if kind == "loracont" else ["nortu", "blte", "tubo"])
            self.assertEqual(json_tool._json_counters_menu.cget("values"), ["0", "1"] if kind == "loracont" else list(map(str, range(9))))
            self.assertEqual(json_tool.json_valves_var.get(), "0" if kind == "loracont" else "1")

    def test_03_csv_and_json_output(self):
        for workspace, model in (("RTU", "210"), ("LORACONT", "297")):
            self.errors.reset_mock()
            csv_tool = self.tool(workspace, "CSV")
            path = OUT / (workspace + ".csv")
            csv_tool.csv_output_var.set(str(path))
            csv_tool.end_number_var.set(csv_tool.start_number_var.get())
            csv_tool._generate()
            self.errors.assert_not_called()
            with path.open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream, delimiter=";"))
            self.assertEqual(row["Model"], model)
            self.assertEqual(row["childnumber"], "0" if workspace == "LORACONT" else "1")
            json_tool = self.tool(workspace, "JSON")
            folder = OUT / workspace
            folder.mkdir(exist_ok=True)
            json_tool.out_folder_var.set(str(folder))
            json_tool.j_to_var.set(json_tool.j_from_var.get())
            json_tool._generate()
            self.errors.assert_not_called()
            data = json.loads(next(folder.glob("*.JSON")).read_text(encoding="utf-8"))
            self.assertNotIn("childnumber", json.dumps(data).lower())
            self.assertEqual(data["device"]["numvalves"], 0 if workspace == "LORACONT" else 1)

    def test_04_project_outputs_keep_context(self):
        for workspace, model in (("RTU", "210"), ("LORACONT", "297")):
            self.errors.reset_mock()
            project = self.tool(workspace, "Proyecto")
            project.root_folder_var.set(str(OUT))
            project.proj_name_var.set(workspace + "_Project")
            project.p_to_var.set(project.p_from_var.get())
            project._generate_all()
            self.errors.assert_not_called()
            folder = OUT / (workspace + "_Project")
            with next((folder / "CSV").glob("*.csv")).open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream, delimiter=";"))
            self.assertEqual(row["Model"], model)
            data = json.loads(next((folder / "JSON").glob("*.JSON")).read_text(encoding="utf-8"))
            self.assertEqual(data["device"]["numvalves"], 0 if workspace == "LORACONT" else 1)
            self.assertTrue(list((folder / "etiquette").glob("*.pdf")))
            self.assertEqual(self.record.call_args.args[1], "RTU")

    def test_05_istantaneo_and_all_translations(self):
        for section in self.engine._views:
            self.engine._show_section(section)
        self.root.update()
        instant = next(widget for widget in descendants(self.engine._views["Istantaneo"])
                       if isinstance(widget, app.TICLabelTab))
        self.assertEqual(instant._family, "Istantaneo")
        self.assertEqual(instant.tic_from_var.get(), "0001")
        self.assertEqual(instant.tic_fw_var.get(), "100L")
        self.assertIn("100L", instant.tic_pdf_var.get())
        instant.tic_fw_var.set("1000L")
        self.assertIn("1000L", instant.tic_pdf_var.get())
        instant.tic_to_var.set("0005")
        instant.tic_pdf_var.set(str(OUT / "Istantaneo_5.pdf"))
        self.errors.reset_mock()
        instant._generate()
        self.errors.assert_not_called()
        self.assertEqual(self.record.call_args.args[1], "Istantaneo")
        for language in ("es", "en", "it"):
            app._cur_lang[0] = language
            for callback in list(app._lang_cbs):
                callback()
            self.root.update_idletasks()
            self.assertEqual(instant._refs["lbl_istantaneo_version"].cget("text"), app.t("lbl_istantaneo_version"))
        self.assertEqual(self.engine._nav_buttons["Manuales"].cget("text"), "Manuali")
        self.assertEqual(self.engine._nav_buttons["Language"].cget("text"), "Lingue")
        self.assertFalse(self.callback_errors, self.callback_errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
