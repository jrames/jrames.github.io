"""Generate the free Box Tracker printable PDFs in box-tracker/printables/.

Usage (from the repo root):
    python3 -m venv /tmp/printables-venv
    /tmp/printables-venv/bin/pip install reportlab qrcode pillow
    /tmp/printables-venv/bin/python _tools/box_tracker_printables.py

Avery geometry comes from the gLabels Avery US template database and matches the
in-app label layouts (BoxTracker LabelPageLayout.Template), so app-printed and
hand-written labels fit the same sticker sheets.
"""

from pathlib import Path

import qrcode
from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "box-tracker" / "printables"
ICON = ROOT / "box-tracker" / "assets" / "app" / "app-icon.png"

# Add the App Store Connect provider token (App Analytics > Campaigns > Generate link)
# so `ct` installs are attributed in App Analytics. Apple ignores `ct` without `pt`.
PROVIDER_TOKEN = ""
APP_STORE_URL = "https://apps.apple.com/app/apple-store/id6762944912"
SITE_URL = "movingboxtracker.com"

INK = HexColor("#161718")
MUTED = HexColor("#696b70")
RULE = HexColor("#d9d4cc")
OUTLINE = HexColor("#cfc8bf")
WARM_DEEP = HexColor("#9a5d20")
WARM_SOFT = HexColor("#f4e8d8")

INCH = 72


def app_store_link(campaign):
    params = f"?ct={campaign}&mt=8"
    if PROVIDER_TOKEN:
        params = f"?pt={PROVIDER_TOKEN}&ct={campaign}&mt=8"
    return APP_STORE_URL + params


def qr_image(url):
    img = qrcode.make(url, border=0, box_size=12)
    return ImageReader(img.get_image())


class Sheet:
    def __init__(self, page_size, label_w, label_h, origin_x, origin_y, col_gap, row_gap, cols, rows, radius):
        self.page_size = page_size
        self.label_w, self.label_h = label_w, label_h
        self.origin_x, self.origin_y = origin_x, origin_y
        self.col_gap, self.row_gap = col_gap, row_gap
        self.cols, self.rows = cols, rows
        self.radius = radius

    def frames(self):
        page_h = self.page_size[1]
        for row in range(self.rows):
            for col in range(self.cols):
                x = self.origin_x + col * (self.label_w + self.col_gap)
                top = self.origin_y + row * (self.label_h + self.row_gap)
                yield x, page_h - top - self.label_h  # reportlab's origin is bottom-left


AVERY_5164 = Sheet(letter, 4 * INCH, 240, 11.25, 36, 13.5, 0, 2, 3, 9)
AVERY_5168 = Sheet(letter, 3.5 * INCH, 5 * INCH, 36, 36, 36, 0, 2, 2, 4.5)
PLAIN_LETTER = Sheet(letter, 3.75 * INCH, 4.875 * INCH, 0.4 * INCH, 0.5 * INCH, 0.2 * INCH, 0.25 * INCH, 2, 2, 6)
_a4_w, _a4_h = A4
_a4_margin, _a4_gap = 0.4 * INCH, 0.2 * INCH
PLAIN_A4 = Sheet(
    A4,
    (_a4_w - 2 * _a4_margin - _a4_gap) / 2,
    (_a4_h - 2 * 0.5 * INCH - 0.25 * INCH) / 2,
    _a4_margin, 0.5 * INCH, _a4_gap, 0.25 * INCH, 2, 2, 6,
)


def small_caps(c, text, x, y, size=6.5, color=MUTED):
    c.setFillColor(color)
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, text.upper())


def text_field(c, name, x, y, w, h, size=11, tooltip=""):
    c.acroForm.textfield(
        name=name, tooltip=tooltip or name, x=x, y=y, width=w, height=h,
        borderWidth=0, borderColor=None, fillColor=None, textColor=INK,
        fontName="Helvetica", fontSize=size, forceBorder=False,
    )


def checkbox(c, name, label, x, y, size=9):
    c.acroForm.checkbox(
        name=name, tooltip=label, x=x, y=y, size=size, buttonStyle="check",
        borderWidth=0.75, borderColor=INK, fillColor=white, textColor=INK, forceBorder=True,
    )
    small_caps(c, label, x + size + 3.5, y + 1.6, size=6.8, color=INK)
    return x + size + 3.5 + c.stringWidth(label.upper(), "Helvetica-Bold", 6.8) + 11


def draw_label(c, index, x, y, w, h, radius, cut_lines):
    # Outline: a cut guide on plain paper; a faint die-cut match on sticker sheets.
    c.saveState()
    if cut_lines:
        c.setDash(4, 3)
        c.setStrokeColor(MUTED)
        c.setLineWidth(0.6)
    else:
        c.setStrokeColor(OUTLINE)
        c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, radius)
    c.restoreState()

    pad = 15
    left, right, top = x + pad, x + w - pad, y + h - pad

    # Header band: room on the left, a big box number on the right.
    band_h = 46
    band_y = top - band_h
    c.setFillColor(WARM_SOFT)
    c.roundRect(left, band_y, right - left, band_h, 6, stroke=0, fill=1)

    swatch = 16
    c.setStrokeColor(WARM_DEEP)
    c.setFillColor(white)
    c.setLineWidth(0.75)
    c.roundRect(left + 8, band_y + band_h - 8 - swatch, swatch, swatch, 3, stroke=1, fill=1)
    small_caps(c, "Color", left + 7, band_y + 7, size=5, color=WARM_DEEP)

    box_w = 74
    room_left = left + 8 + swatch + 10
    room_right = right - box_w - 10
    small_caps(c, "Room", room_left, band_y + band_h - 12, color=WARM_DEEP)
    c.setStrokeColor(WARM_DEEP)
    c.line(room_left, band_y + 9, room_right, band_y + 9)
    text_field(c, f"room_{index}", room_left, band_y + 10, room_right - room_left, 20, size=14, tooltip="Room")

    box_x = right - box_w - 6
    c.setFillColor(white)
    c.roundRect(box_x, band_y + 6, box_w, band_h - 12, 5, stroke=1, fill=1)
    small_caps(c, "Box #", box_x + 6, band_y + band_h - 16, size=5.5, color=WARM_DEEP)
    text_field(c, f"box_{index}", box_x + 20, band_y + 8, box_w - 24, band_h - 16, size=20, tooltip="Box number")

    # Footer: checkboxes, then the small credit line.
    footer_y = y + pad
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.6)
    c.drawString(left, footer_y, f"Want scannable QR labels? Moving Box Tracker for iPhone · {SITE_URL}")

    checks_y = footer_y + 13
    cx = left
    for key, label in (("fragile", "Fragile"), ("up", "This side up"), ("first", "Open first")):
        cx = checkbox(c, f"{key}_{index}", label, cx, checks_y)

    # Contents: ruled lines, each a single-line field so typed text sits on its rule.
    small_caps(c, "Contents", left, band_y - 14)
    line_gap = 17
    first_rule = band_y - 18 - line_gap + 4
    rule_y = first_rule
    line = 0
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    while rule_y > checks_y + 16:
        c.line(left, rule_y, right, rule_y)
        text_field(c, f"contents_{index}_{line}", left, rule_y + 1, right - left, line_gap - 3, size=9.5, tooltip="Contents")
        rule_y -= line_gap
        line += 1


def label_sheet(path, sheet, title, cut_lines):
    c = canvas.Canvas(str(path), pagesize=sheet.page_size)
    c.setTitle(title)
    c.setAuthor("Moving Box Tracker")
    c.setSubject("Free printable moving box labels")
    for index, (x, y) in enumerate(sheet.frames()):
        draw_label(c, index, x, y, sheet.label_w, sheet.label_h, sheet.radius, cut_lines)
    c.showPage()
    c.save()


def inventory_sheet(path, page_size, campaign):
    page_w, page_h = page_size
    margin = 0.55 * INCH
    c = canvas.Canvas(str(path), pagesize=page_size)
    c.setTitle("Moving Box Inventory Checklist")
    c.setAuthor("Moving Box Tracker")

    top = page_h - margin
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, top - 20, "Moving Box Inventory")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    c.drawString(margin, top - 36, "Number every box, note its room and contents, and tick it off as it's packed and as it arrives.")

    fields_y = top - 76
    for label, x, w in (("Move", margin, 260), ("Moving day", margin + 280, 150), ("Page", margin + 450, 40)):
        small_caps(c, label, x, fields_y + 14)
        c.setStrokeColor(RULE)
        c.line(x, fields_y, x + w, fields_y)
        text_field(c, label.lower().replace(" ", "_"), x, fields_y + 1, w, 12, size=10, tooltip=label)

    columns = (("Box #", 48), ("Room", 110), ("Contents", None), ("Packed", 46), ("Arrived", 48))
    table_left, table_right = margin, page_w - margin
    fixed = sum(w for _, w in columns if w)
    widths = [w if w else (table_right - table_left - fixed) for _, w in columns]

    promo_h = 92
    header_y = fields_y - 34
    row_h = 21
    rows = int((header_y - (margin + promo_h + 14)) // row_h)

    c.setFillColor(WARM_SOFT)
    c.rect(table_left, header_y - 4, table_right - table_left, 18, stroke=0, fill=1)
    x = table_left
    for (name, _), w in zip(columns, widths):
        small_caps(c, name, x + 6, header_y + 2, size=7, color=WARM_DEEP)
        x += w

    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    for r in range(rows):
        y = header_y - 4 - (r + 1) * row_h
        c.line(table_left, y, table_right, y)
        x = table_left
        for col, ((name, _), w) in enumerate(zip(columns, widths)):
            if name in ("Packed", "Arrived"):
                c.acroForm.checkbox(
                    name=f"{name.lower()}_{r}", tooltip=name, x=x + (w - 10) / 2, y=y + 5.5, size=10,
                    buttonStyle="check", borderWidth=0.75, borderColor=INK, fillColor=white, textColor=INK, forceBorder=True,
                )
            else:
                text_field(c, f"{name.lower().replace(' #', '')}_{r}", x + 4, y + 3, w - 8, row_h - 6, size=9.5, tooltip=name)
            x += w
    bottom = header_y - 4 - rows * row_h
    x = table_left
    for w in widths[:-1]:
        x += w
        c.line(x, header_y - 4, x, bottom)

    # Promo panel with a QR code straight to the App Store.
    panel_y = margin
    c.setFillColor(HexColor("#f7f6f3"))
    c.setStrokeColor(OUTLINE)
    c.roundRect(table_left, panel_y, table_right - table_left, promo_h, 10, stroke=1, fill=1)
    qr = promo_h - 22
    c.drawImage(qr_image(app_store_link(campaign)), table_right - qr - 11, panel_y + 11, qr, qr)
    if ICON.exists():
        # Downscale before embedding; the full-size icon alone adds ~600 KB to the PDF.
        icon = Image.open(ICON).convert("RGB")
        icon.thumbnail((144, 144))
        ix, iy = table_left + 14, panel_y + promo_h - 50
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(ix, iy, 36, 36, 8)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(ImageReader(icon), ix, iy, 36, 36)
        c.restoreState()
    tx = table_left + 62
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(tx, panel_y + promo_h - 28, "Rather search than scroll through a list?")
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    for i, line in enumerate((
        "Moving Box Tracker for iPhone prints a scannable QR label for every box",
        "and finds any packed item in seconds. Free to use, no subscription.",
        f"Scan the code or visit {SITE_URL}",
    )):
        c.drawString(tx, panel_y + promo_h - 45 - i * 13, line)

    c.showPage()
    c.save()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    label_sheet(OUT / "moving-box-labels-avery-5164.pdf", AVERY_5164, "Moving Box Labels – Avery 5164 / 8164", cut_lines=False)
    label_sheet(OUT / "moving-box-labels-avery-5168.pdf", AVERY_5168, "Moving Box Labels – Avery 5168 / 8168", cut_lines=False)
    label_sheet(OUT / "moving-box-labels-letter.pdf", PLAIN_LETTER, "Moving Box Labels – Letter paper", cut_lines=True)
    label_sheet(OUT / "moving-box-labels-a4.pdf", PLAIN_A4, "Moving Box Labels – A4 paper", cut_lines=True)
    inventory_sheet(OUT / "moving-box-inventory-checklist-letter.pdf", letter, "printable-checklist")
    inventory_sheet(OUT / "moving-box-inventory-checklist-a4.pdf", A4, "printable-checklist")
    print(f"Wrote printables to {OUT}")


if __name__ == "__main__":
    main()
