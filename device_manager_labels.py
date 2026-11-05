"""Print approved equipment labels with one set of stickers per device/page."""

import json
import math
import os


MM = 72 / 25.4
PAGE_W, PAGE_H = 210 * MM, 297 * MM
BOTTOM = 10 * MM
LABEL_W, BODY_H = 50 * MM, 48
LABEL_GAP = 0.8 * MM
TAIL_H = 15.5 * MM
SECTION_GAP = 4 * MM
BATTERY_GAP = 1 * MM
BATTERY_COLS = 12
STICKER_SHEETS = (
    ("sheet_manual_tic12", os.path.join("Manuali", "Fogli adesivi", "QR_Manuale_TIC12.pdf")),
    ("sheet_manual_itic", os.path.join("Manuali", "Fogli adesivi", "QR_Manuale_ITIC.pdf")),
    ("sheet_battery", os.path.join("Manuali", "Fogli adesivi", "Sticker_batteria_15x15mm.pdf")),
)


def battery_height(count):
    rows = math.ceil(count / BATTERY_COLS)
    return rows * 15 * MM + max(0, rows - 1) * BATTERY_GAP


class StickerAssets:
    def __init__(self, resource):
        self.resource = resource
        with open(resource(os.path.join("label_assets", "raee.json")), encoding="utf-8") as stream:
            self.battery = json.load(stream)
        for dimension in ("width", "height"):
            if not math.isclose(self.battery[dimension] / MM, 15, abs_tol=0.00001):
                raise ValueError("The battery sticker must remain 15 x 15 mm.")

    def manual_qr(self, product_name):
        from reportlab.lib.utils import ImageReader
        filename = "manual_tic12.png" if product_name == "TIC12" else "manual_itic.png"
        return ImageReader(self.resource(os.path.join("label_assets", filename)))

    def draw_batteries(self, canvas, count, top):
        battery = self.battery
        rectangles = []
        for index in range(count):
            row, column = divmod(index, BATTERY_COLS)
            cells = min(BATTERY_COLS, count - row * BATTERY_COLS)
            row_w = cells * battery["width"] + (cells - 1) * BATTERY_GAP
            x = (PAGE_W - row_w) / 2 + column * (battery["width"] + BATTERY_GAP)
            y = top - battery["height"] - row * (battery["height"] + BATTERY_GAP)
            if y < BOTTOM - 0.001:
                raise ValueError("The battery stickers exceed the printable page area.")
            canvas.saveState()
            canvas.translate(x - battery["source_x"], y - battery["source_y"])
            canvas._code.append(battery["commands"])
            canvas.restoreState()
            rectangles.append((x, y, x + battery["width"], y + battery["height"]))
        return rectangles


def rtu_page_layout(original_rows, label_h, slot_h, columns=2):
    """Reserve a separate footer without rescaling the existing RTU labels."""
    usable_h = PAGE_H - 2 * BOTTOM
    for rows in range(original_rows, 0, -1):
        grid_h = label_h + (rows - 1) * slot_h
        total_h = grid_h + 2 * MM + battery_height(rows * columns)
        if total_h <= usable_h:
            top = PAGE_H - BOTTOM - (usable_h - total_h) / 2
            return rows, top
    raise ValueError("The equipment label and its battery sticker do not fit on A4.")


def _is_itic(product_name):
    if product_name not in ("TIC12", "I-TIC 1V", "ISTANTANEO"):
        raise ValueError("Unsupported equipment label: " + product_name)
    return product_name == "I-TIC 1V"


def _manual_height(count):
    rows = math.ceil(count / 10)
    return rows * 20 * MM + max(0, rows - 1) * MM


def tic_page_capacity(product_name):
    itic = _is_itic(product_name)
    label_h = BODY_H + (TAIL_H if itic else 0)
    top = (10 if product_name == "TIC12" else 12) * MM
    for count in range(45, 0, -1):
        rows = math.ceil(count / 3)
        height = rows * label_h + max(0, rows - 1) * LABEL_GAP
        height += SECTION_GAP + battery_height(count)
        if product_name == "TIC12":
            height += SECTION_GAP + _manual_height(count)
        if height <= PAGE_H - top - BOTTOM:
            return count
    raise ValueError("The labels do not fit on A4.")


def _draw_primary(canvas, label, product_name, x, y, logo, qr):
    itic = _is_itic(product_name)
    base = y + (TAIL_H if itic else 0)
    ca = LABEL_W * (7 / 26.15)
    cb = LABEL_W * (9.29 / 26.15)
    cc = LABEL_W * (9.86 / 26.15)
    tx = x + ca + (cb + cc) / 2

    canvas.setFillColorRGB(0, 0, 0)
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setLineWidth(0.5)
    canvas.rect(x, base, LABEL_W, BODY_H, stroke=1, fill=0)
    canvas.line(x + ca, base, x + ca, base + BODY_H)
    canvas.line(x, base + 12, x + LABEL_W, base + 12)
    canvas.line(x + ca + cb, base, x + ca + cb, base + 12)
    if logo:
        canvas.drawImage(logo, x, base + 12, ca, 36,
                         mask="auto", preserveAspectRatio=True, anchor="c")

    def text(value, center, bottom, row_h, size, bold=False):
        canvas.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        canvas.drawCentredString(center, bottom + (row_h - size) / 2, value)

    if product_name == "ISTANTANEO":
        for value, font, size, baseline in (
            ("Misuratore di Portata", "Helvetica-Bold", 9, 39.8),
            ("Istantaneo", "Helvetica-Bold", 9, 30.5),
            ("TECNIDRO srl - GENOVA", "Helvetica-Bold", 7.3, 21.7),
            ("w w w . t e c n i d r o . c o m", "Helvetica", 7, 14.2),
        ):
            canvas.setFont(font, size)
            canvas.drawCentredString(tx, base + baseline, value)
    else:
        text(product_name, tx, base + 34.5, 13.5, 10, True)
        text("TECNIDRO srl - GENOVA", tx, base + 22.5, 12, 8, True)
        text("w w w . t e c n i d r o . c o m", tx, base + 12, 10.5, 8)
    text("SERIAL N.", x + ca / 2, base, 12, 6)
    text(label["serial"], x + ca + cb / 2, base, 12, 6, True)
    prefix = "Versione: " if product_name == "ISTANTANEO" else "FW: "
    text(prefix + label["fw"], x + ca + cb + cc / 2, base, 12, 6, True)
    if itic:
        canvas.rect(x + (LABEL_W - 12 * MM) / 2, y, 12 * MM, TAIL_H, stroke=1, fill=0)
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawCentredString(x + LABEL_W / 2, y + 12.4 * MM, "Manual")
        canvas.drawImage(qr, x + (LABEL_W - 10 * MM) / 2, y + 1.2 * MM,
                         width=10 * MM, height=10 * MM, mask="auto")


def _draw_tic12_manuals(canvas, qr, count, top):
    width, height = 18 * MM, 20 * MM
    for index in range(count):
        row, column = divmod(index, 10)
        cells = min(10, count - row * 10)
        row_w = cells * width + (cells - 1) * MM
        x = (PAGE_W - row_w) / 2 + column * (width + MM)
        y = top - height - row * (height + MM)
        canvas.saveState()
        canvas.setStrokeColorRGB(0.890196, 0.890196, 0.890196)
        canvas.setLineWidth(0.13 * MM)
        canvas.rect(x, y, width, height, stroke=1, fill=0)
        canvas.setFillColorRGB(0, 0, 0)
        canvas.setFont("Helvetica-Bold", 5.5)
        canvas.drawCentredString(x + width / 2, y + 17.2 * MM, "Manual ITA-ENG")
        canvas.drawImage(qr, x + 1.5 * MM, y + MM, width=15 * MM, height=15 * MM)
        canvas.restoreState()
    return top - _manual_height(count)


def make_tic_pdf(labels, output_path, product_name, resource, logo=None):
    from reportlab.pdfgen import canvas as pdf_canvas

    if not labels:
        raise ValueError("There are no equipment labels to print.")
    itic = _is_itic(product_name)
    assets = StickerAssets(resource)
    qr = assets.manual_qr(product_name) if product_name != "ISTANTANEO" else None
    capacity = tic_page_capacity(product_name)
    label_h = BODY_H + (TAIL_H if itic else 0)
    top = PAGE_H - (10 if product_name == "TIC12" else 12) * MM
    grid_w = 3 * LABEL_W + MM
    left = 18 * MM + (PAGE_W - 18 * MM - 14 * MM - grid_w) / 2
    canvas = pdf_canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))

    for offset in range(0, len(labels), capacity):
        if offset:
            canvas.showPage()
        page_labels = labels[offset:offset + capacity]
        for index, label in enumerate(page_labels):
            row, column = divmod(index, 3)
            x = left + column * (LABEL_W + 0.5 * MM)
            y = top - row * (label_h + LABEL_GAP) - label_h
            _draw_primary(canvas, label, product_name, x, y, logo, qr)
        rows = math.ceil(len(page_labels) / 3)
        grid_bottom = top - rows * label_h - (rows - 1) * LABEL_GAP
        footer_top = grid_bottom - SECTION_GAP
        if product_name == "TIC12":
            footer_top = _draw_tic12_manuals(canvas, qr, len(page_labels), footer_top) - SECTION_GAP
        assets.draw_batteries(canvas, len(page_labels), footer_top)
    canvas.save()


def centered_text(canvas, text, font, size, center, baseline):
    canvas.setFont(font, size)
    canvas.drawCentredString(center, baseline, text)


def draw_gateway_header(canvas, left, bottom, top, tecnidro, lorawan, regular, bold, resource):
    from reportlab.pdfbase.pdfmetrics import stringWidth

    battery = StickerAssets(resource).battery
    glyph_commands = battery["commands"][battery["commands"].index("\nq\n") + 1:]
    height = top - bottom
    cuts = [left, left + 80, left + 272.25, left + 393, left + 453]
    canvas.saveState()
    canvas.setStrokeColorRGB(0, 0, 0)
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setLineWidth(0.45)
    for x in cuts[1:-1]:
        canvas.line(x, bottom, x, top)

    if tecnidro:
        size = 54
        canvas.drawImage(tecnidro, (cuts[0] + cuts[1] - size) / 2,
                         bottom + (height - size) / 2, size, size,
                         mask="auto", preserveAspectRatio=True, anchor="c")

    inner_left = cuts[1] + 8
    logo_w, logo_h = 78, 78 * 22.8 / 118
    brand_center_y = bottom + 44
    if lorawan:
        canvas.drawImage(lorawan, inner_left, brand_center_y - logo_h / 2,
                         logo_w, logo_h, mask="auto", preserveAspectRatio=True, anchor="c")
    hydronet_x = inner_left + logo_w + 10
    available = cuts[2] - 8 - hydronet_x
    size = 17.5
    while stringWidth("HYDRONET", bold, size) > available:
        size -= 0.25
    canvas.setFont(bold, size)
    canvas.drawString(hydronet_x, brand_center_y - size * 0.34, "HYDRONET")
    company_center = (cuts[1] + cuts[2]) / 2
    centered_text(canvas, "TECNIDRO srl - GENOVA", bold, 8.5, company_center, bottom + 21)
    centered_text(canvas, "w w w . t e c n i d r o . c o m", regular, 8.0, company_center, bottom + 8.5)

    gateway_center = (cuts[2] + cuts[3]) / 2
    centered_text(canvas, "GATEWAY", bold, 17, gateway_center, bottom + 35)
    centered_text(canvas, "LTE", regular, 12, gateway_center, bottom + 18)

    x = (cuts[3] + cuts[4] - battery["width"]) / 2
    y = bottom + (height - battery["height"]) / 2
    canvas.saveState()
    canvas.translate(x - battery["source_x"], y - battery["source_y"])
    canvas._code.append(glyph_commands)
    canvas.restoreState()
    canvas.restoreState()

