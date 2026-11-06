"""Keep the single-file build small without losing image/PDF support."""

import ast
from contextlib import contextmanager
import importlib.abc
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image
from device_manager_preview import render_pdf


ROOT = Path(__file__).resolve().parent
SPEC = ast.parse((ROOT / "Device_Manager_v132.spec").read_text(encoding="utf-8"))
OPTIONAL = next(ast.literal_eval(node.value) for node in SPEC.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "OPTIONAL_MODULES" for target in node.targets))


@contextmanager
def without_optional_modules():
    class BlockOptional(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if any(fullname == name or fullname.startswith(name + ".") for name in OPTIONAL):
                raise ModuleNotFoundError(fullname, name=fullname)

    blocker = BlockOptional()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)


class PackagingTests(unittest.TestCase):
    def test_all_core_files_are_embedded_in_the_single_visible_executable(self):
        calls = [node.value for node in SPEC.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)]
        collection = next(call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "COLLECT")
        self.assertTrue(any(isinstance(arg, ast.Attribute) and arg.attr == "datas" for arg in collection.args))
        builder = (ROOT / "portable_launcher/build_portable.py").read_text(encoding="utf-8")
        self.assertIn('",DM.Payload"', builder)
        self.assertIn('",DM.Manifest"', builder)
        self.assertIn("numpy", OPTIONAL)
        self.assertNotIn("PIL.PngImagePlugin", OPTIONAL)
        self.assertNotIn("PIL.JpegImagePlugin", OPTIONAL)

    def test_preview_without_numpy_and_optional_codecs(self):
        from reportlab.pdfgen.canvas import Canvas
        with tempfile.TemporaryDirectory(prefix="DeviceManager_package_") as directory, without_optional_modules():
            path = Path(directory) / "preview.pdf"
            canvas = Canvas(str(path))
            canvas.drawString(20, 100, "Device Manager PDF preview")
            canvas.save()
            image, pages = render_pdf(path, width=320)
            self.assertEqual(pages, 1)
            self.assertEqual(image.width, 320)
            self.assertGreater(image.height, 0)
            self.assertIsNone(sys.modules.get("numpy"))

    def test_app_images_without_optional_codecs(self):
        names = ("logo.png", "gw_logo_tecnidro.png", "gw_logo_lorawan.jpeg",
                 "tecnidro_app_icon.png", "assets/guided/products_reference.png",
                 "label_assets/manual_tic12.png", "label_assets/manual_itic.png")
        with without_optional_modules():
            Image.init()
            for name in names:
                with self.subTest(name=name), Image.open(ROOT / name) as image:
                    image.load()
                    self.assertGreater(image.width, 0)


if __name__ == "__main__":
    unittest.main()
