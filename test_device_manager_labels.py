import ast
import hashlib
import json
import math
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader
from pypdf.generic import ContentStream

from device_manager_labels import (
    MM, PAGE_H, StickerAssets, STICKER_SHEETS, tic_page_capacity,
)


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "tmp/pdfs/label_tests"
OUTPUT.mkdir(parents=True, exist_ok=True)
VARIANTS = {
    "RTU_BT": ({"include_bluetooth": True}, 22),
    "RTU_NO_BT": ({"include_bluetooth": False}, 28),
    "RTU_TUBO": ({"rtu_header": True}, 14),
    "LORACONT": ({"loraconta": True}, 20),
}


def resource(name):
    return str(ROOT / name)


def functions(path):
    names = {"_make_pdf", "_make_tic_pdf", "_make_qr_image", "_make_black_logo_reader"}
    source = Path(path).read_text(encoding="utf-8-sig")
    nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = {"os": os, "Image": Image, "_resource": resource}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def devices(count):
    return [{"serial": f"{i:05d}/2026", "name": f"TEST_{i:02d}",
             "dev_eui": f"512345678B3A{i:04X}", "dev_addr": f"8B3A{i:04X}"}
            for i in range(1, count + 1)]


def equipment_rectangles(page, minimum_width=0):
    return [tuple(map(float, args)) for args, op in ContentStream(page.get_contents(), page.pdf).operations
            if op == b"re" and float(args[2]) > minimum_width]


def draw_with_footer_records(draw, *args, **kwargs):
    records = []
    original = StickerAssets.draw_batteries

    def record(self, canvas, count, top):
        rectangles = original(self, canvas, count, top)
        records.append((canvas.getPageNumber(), count, rectangles))
        return rectangles

    with patch.object(StickerAssets, "draw_batteries", record):
        draw(*args, **kwargs)
    return records


class LabelPdfTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = functions(ROOT / "generador_csv.py")
        cls.legacy = functions(ROOT / "tests/fixtures/labels_v125.py")
        cls.battery = StickerAssets(resource).battery

    def assert_footer(self, page, count, records):
        commands = self.battery["commands"].encode("ascii")
        self.assertEqual(page.get_contents().get_data().count(commands), count)
        self.assertEqual(records[1], count)
        for x0, y0, x1, y1 in records[2]:
            self.assertAlmostEqual((x1 - x0) / MM, 15, places=4)
            self.assertAlmostEqual((y1 - y0) / MM, 15, places=4)
            self.assertGreaterEqual(y0, 10 * MM - 0.001)

    def test_exact_integrated_download_sheets(self):
        expected = {
            "QR_Manuale_ITIC.pdf": "37800cbc5e7f0a2f715843a6ecc581a33d694a34897f63d78c10aae861cd3a23",
            "QR_Manuale_TIC12.pdf": "be814e5ca1940166bf12ee496db46e9039a6e9d0f49cdc37c57a4ba4999bf5d4",
            "Sticker_batteria_15x15mm.pdf": "58338f757dd0dac26ff4300d2a9b11fa4583589fd9c61e16c6322e4be024c694",
        }
        for _, target in STICKER_SHEETS:
            self.assertEqual(hashlib.sha256((ROOT / target).read_bytes()).hexdigest(), expected[Path(target).name])

    def test_tic12_compact_manual_sheet_matches_label_accessory(self):
        reader = PdfReader(ROOT / "Manuali/Fogli adesivi/QR_Manuale_TIC12.pdf")
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(float(page.mediabox.width) / MM, 210, places=4)
        self.assertAlmostEqual(float(page.mediabox.height) / MM, 297, places=4)
        self.assertEqual(page.extract_text().count("Manual ITA-ENG"), 130)
        boxes = equipment_rectangles(page)
        self.assertEqual(len(boxes), 130)
        for x, y, width, height in boxes:
            self.assertAlmostEqual(width / MM, 18, places=4)
            self.assertAlmostEqual(height / MM, 20, places=4)
            self.assertGreaterEqual(x, 10 * MM)
            self.assertGreaterEqual(y, 10 * MM)
            self.assertLessEqual(x + width, 200 * MM)
            self.assertLessEqual(y + height, 287 * MM)
        with Image.open(ROOT / "label_assets/manual_tic12.png") as qr:
            self.assertTrue(any(image.image.tobytes() == qr.tobytes() for image in page.images))
        matrices = [args for args, op in ContentStream(page.get_contents(), page.pdf).operations
                    if op == b"cm" and abs(float(args[0])-15*MM) < .001 and abs(float(args[3])-15*MM) < .001]
        self.assertEqual(len(matrices), 130)

    def test_tic_capacity_and_partial_last_page(self):
        for product, capacity, fw in (("TIC12", 27, "03.02.03"), ("I-TIC 1V", 21, "04.00.05")):
            with self.subTest(product=product):
                self.assertEqual(tic_page_capacity(product), capacity)
                output = OUTPUT / ("TIC12.pdf" if product == "TIC12" else "ITIC.pdf")
                labels = [{"serial": f"{i:04d}/2026", "fw": fw} for i in range(1, capacity + 6)]
                records = draw_with_footer_records(self.app["_make_tic_pdf"], labels, str(output), product)
                reader = PdfReader(output)
                self.assertEqual(len(reader.pages), 2)
                for page, expected, record in zip(reader.pages, (capacity, 5), records):
                    text = page.extract_text()
                    self.assertEqual(text.count("SERIAL N."), expected)
                    self.assertEqual(text.count("Manual"), expected)
                    self.assert_footer(page, expected, record)
                    manual_name = "manual_tic12.png" if product == "TIC12" else "manual_itic.png"
                    with Image.open(ROOT / "label_assets" / manual_name) as qr:
                        self.assertTrue(any(image.image.tobytes() == qr.tobytes() for image in page.images))

    def test_single_and_exactly_full_tic_pages(self):
        for product in ("TIC12", "I-TIC 1V"):
            for count in (1, tic_page_capacity(product)):
                with self.subTest(product=product, count=count):
                    output = OUTPUT / "tic_boundary.pdf"
                    labels = [{"serial": f"{i:04d}/2026", "fw": "TEST"} for i in range(count)]
                    records = draw_with_footer_records(self.app["_make_tic_pdf"], labels, str(output), product)
                    reader = PdfReader(output)
                    self.assertEqual(len(reader.pages), 1)
                    self.assert_footer(reader.pages[0], count, records[0])

    def test_istantaneo_versions_full_and_partial_pages(self):
        self.assertEqual(tic_page_capacity("ISTANTANEO"), 36)
        for version in ("100L", "1000L"):
            output = OUTPUT / ("Istantaneo_" + version + ".pdf")
            labels = [{"serial": f"{i:04d}/2026", "fw": version} for i in range(1, 42)]
            records = draw_with_footer_records(self.app["_make_tic_pdf"], labels, str(output), "ISTANTANEO")
            reader = PdfReader(output)
            self.assertEqual(len(reader.pages), 2)
            for page, count, record in zip(reader.pages, (36, 5), records):
                text = page.extract_text()
                self.assertEqual(text.count("Misuratore di Portata"), count)
                self.assertEqual(text.count("Istantaneo"), count)
                self.assertEqual(text.count("Versione: " + version), count)
                self.assertNotIn("FW:", text)
                self.assertNotIn("Manual", text)
                self.assert_footer(page, count, record)
                boxes = equipment_rectangles(page, 49 * MM)
                self.assertEqual(len(boxes), count)
                for x, y, width, height in boxes:
                    self.assertAlmostEqual(width / MM, 50, places=4)
                    self.assertAlmostEqual(height, 48, places=4)

    def test_gateway_approved_four_cell_header(self):
        source = (ROOT / "generador_csv.py").read_text(encoding="utf-8-sig")
        names = {"_register_pdf_font", "_wrap_pdf_text", "_fit_pdf_text", "_draw_text_in_box", "_make_gateway_pdf"}
        nodes = [node for node in ast.parse(source).body
                 if (isinstance(node, ast.FunctionDef) and node.name in names)
                 or (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith("GW_") for t in node.targets))]
        namespace = {"os": os, "_resource": resource}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / "generador_csv.py"), "exec"), namespace)
        output = OUTPUT / "Gateway.pdf"
        gateways = [{"model": "GW X4S LTE", "alias": f"Gateway {i}", "serial": str(i),
                     "mac": f"0011223344{i:02X}", "dev_eui": f"70B3D57ED007{i:04X}"} for i in range(1, 7)]
        namespace["_make_gateway_pdf"](gateways, str(output), "2026")
        reader = PdfReader(output)
        self.assertEqual(len(reader.pages), 2)
        glyph = self.battery["commands"][self.battery["commands"].index("\nq\n") + 1:].encode("ascii")
        for page, count in zip(reader.pages, (5, 1)):
            text = page.extract_text()
            self.assertEqual(text.count("HYDRONET"), count)
            self.assertEqual(text.count("GATEWAY"), count)
            self.assertEqual(text.count("GW MAC"), count)
            self.assertEqual(page.get_contents().get_data().count(glyph), count)
            self.assertEqual(len(page.images), 2)

    def test_all_rtu_models_keep_dimensions_and_match_stickers_per_page(self):
        for name, (options, capacity) in VARIANTS.items():
            with self.subTest(model=name):
                output = OUTPUT / (name + ".pdf")
                baseline = OUTPUT / (name + "_original.pdf")
                records = draw_with_footer_records(self.app["_make_pdf"], devices(capacity + 5), str(output), **options)
                self.legacy["_make_pdf"](devices(1), str(baseline), **options)
                baseline_box = equipment_rectangles(PdfReader(baseline).pages[0], 80 * MM)[0]
                reader = PdfReader(output)
                self.assertEqual(len(reader.pages), 2)
                for page, count, record in zip(reader.pages, (capacity, 5), records):
                    text = page.extract_text()
                    self.assertEqual(text.count("SERIAL N."), count)
                    self.assertNotIn("Manual", text)
                    self.assert_footer(page, count, record)
                    boxes = equipment_rectangles(page, 80 * MM)
                    self.assertEqual(len(boxes), count)
                    for x, y, width, height in boxes:
                        self.assertAlmostEqual(width, baseline_box[2], places=4)
                        self.assertAlmostEqual(height, baseline_box[3], places=4)
                        self.assertLessEqual(y + height, PAGE_H - 10 * MM + 0.001)
                        for ax, ay, bx, by in record[2]:
                            self.assertTrue(bx <= x or ax >= x + width or by <= y or ay >= y + height)

    def test_single_and_full_rtu_page_boundaries(self):
        for name, (options, capacity) in VARIANTS.items():
            for count in (1, capacity):
                with self.subTest(model=name, count=count):
                    output = OUTPUT / "rtu_boundary.pdf"
                    records = draw_with_footer_records(self.app["_make_pdf"], devices(count), str(output), **options)
                    reader = PdfReader(output)
                    self.assertEqual(len(reader.pages), 1)
                    self.assert_footer(reader.pages[0], count, records[0])


if __name__ == "__main__":
    unittest.main()
