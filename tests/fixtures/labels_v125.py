import os
from PIL import Image

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
