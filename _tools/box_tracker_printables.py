"""Generate the free Box Tracker printable PDFs in box-tracker/printables/.

Usage (from the repo root):
    python3 -m venv /tmp/printables-venv
    /tmp/printables-venv/bin/pip install reportlab qrcode pillow
    /tmp/printables-venv/bin/python _tools/box_tracker_printables.py

Preview images (box-tracker/assets/printables/*.jpg, 900 px tall) come from page 1 of each
PDF; `--previews` renders them too (needs `pip install pypdfium2`).

Avery geometry comes from the gLabels Avery US template database and matches the
in-app label layouts (BoxTracker LabelPageLayout.Template), so app-printed and
hand-written labels fit the same sticker sheets.
"""

import sys
from pathlib import Path

import qrcode
from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "box-tracker" / "printables"
PREVIEWS = ROOT / "box-tracker" / "assets" / "printables"
ICON = ROOT / "box-tracker" / "assets" / "app" / "app-icon.png"

# Add the App Store Connect provider token (App Analytics > Campaigns > Generate link)
# so `ct` installs are attributed in App Analytics. Apple ignores `ct` without `pt`.
PROVIDER_TOKEN = "119038783"
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


def link_area(c, url, x, y, w, h):
    """Make a region tappable. A QR code can't be scanned from the screen it's displayed on,
    and these PDFs are often read on the phone they were emailed or downloaded to."""
    c.linkURL(url, (x, y, x + w, y + h), relative=0, thickness=0)


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
    credit = f"Want scannable QR labels? Moving Box Tracker for iPhone · {SITE_URL}"
    c.drawString(left, footer_y, credit)
    link_area(c, f"https://{SITE_URL}/", left, footer_y - 2, c.stringWidth(credit, "Helvetica", 5.6), 8)

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




def page_header(c, page_size, margin, title, subtitle, fields):
    page_w, page_h = page_size
    top = page_h - margin
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin, top - 20, title)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    c.drawString(margin, top - 36, subtitle)

    fields_y = top - 76
    x = margin
    usable = page_w - 2 * margin
    gap = 20
    total = sum(share for _, share in fields)
    for label, share in fields:
        w = (usable - gap * (len(fields) - 1)) * share / total
        small_caps(c, label, x, fields_y + 14)
        c.setStrokeColor(RULE)
        c.line(x, fields_y, x + w, fields_y)
        text_field(c, label.lower().replace(" ", "_").replace("#", "no"), x, fields_y + 1, w, 12, size=10, tooltip=label)
        x += w + gap
    return fields_y


def promo_panel(c, x, y, w, h, campaign, headline, lines):
    """App promo with a QR code straight to the App Store."""
    c.setFillColor(HexColor("#f7f6f3"))
    c.setStrokeColor(OUTLINE)
    c.roundRect(x, y, w, h, 10, stroke=1, fill=1)
    qr = h - 22
    link = app_store_link(campaign)
    c.drawImage(qr_image(link), x + w - qr - 11, y + 11, qr, qr)
    link_area(c, link, x, y, w, h)
    if ICON.exists():
        # Downscale before embedding; the full-size icon alone adds ~600 KB to the PDF.
        icon = Image.open(ICON).convert("RGB")
        icon.thumbnail((144, 144))
        ix, iy = x + 14, y + h - 50
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(ix, iy, 36, 36, 8)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(ImageReader(icon), ix, iy, 36, 36)
        c.restoreState()
    tx = x + 62
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12.5)
    c.drawString(tx, y + h - 28, headline)
    c.setFont("Helvetica", 9.5)
    c.setFillColor(MUTED)
    for i, line in enumerate(lines + (f"Scan or tap the code, or visit {SITE_URL}",)):
        c.drawString(tx, y + h - 45 - i * 13, line)


def table_sheet(path, page_size, title, subtitle, fields, columns, campaign, promo, pages=1):
    """A fillable table. `columns` is (name, width or None, is_checkbox); one None column
    takes the leftover width."""
    page_w, page_h = page_size
    margin = 0.55 * INCH
    c = canvas.Canvas(str(path), pagesize=page_size)
    c.setTitle(title)
    c.setAuthor("Moving Box Tracker")

    table_left, table_right = margin, page_w - margin
    fixed = sum(w for _, w, _ in columns if w)
    widths = [w if w else (table_right - table_left - fixed) for _, w, _ in columns]
    promo_h = 92
    row_h = 21

    for page in range(pages):
        fields_y = page_header(c, page_size, margin, title, subtitle, fields)
        header_y = fields_y - 34
        # Only the last page carries the promo; earlier pages use the space for rows.
        floor = margin + (promo_h + 14 if page == pages - 1 else 0)
        rows = int((header_y - floor) // row_h)

        c.setFillColor(WARM_SOFT)
        c.rect(table_left, header_y - 4, table_right - table_left, 18, stroke=0, fill=1)
        x = table_left
        for (name, _, _), w in zip(columns, widths):
            small_caps(c, name, x + 6, header_y + 2, size=7, color=WARM_DEEP)
            x += w

        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        for r in range(rows):
            y = header_y - 4 - (r + 1) * row_h
            c.line(table_left, y, table_right, y)
            x = table_left
            for (name, _, is_check), w in zip(columns, widths):
                key = f"{name.lower().replace(' ', '_').replace('#', 'no').replace('.', '')}_{page}_{r}"
                if is_check:
                    c.acroForm.checkbox(
                        name=key, tooltip=name, x=x + (w - 10) / 2, y=y + 5.5, size=10,
                        buttonStyle="check", borderWidth=0.75, borderColor=INK, fillColor=white, textColor=INK, forceBorder=True,
                    )
                else:
                    text_field(c, key, x + 4, y + 3, w - 8, row_h - 6, size=9.5, tooltip=name)
                x += w
        bottom = header_y - 4 - rows * row_h
        x = table_left
        for w in widths[:-1]:
            x += w
            c.line(x, header_y - 4, x, bottom)

        if page == pages - 1:
            promo_panel(c, table_left, margin, table_right - table_left, promo_h, campaign, *promo)
        c.showPage()
    c.save()


MOVING_CHECKLIST = (
    ("8 weeks before", (
        "Decide on movers or a DIY truck, and get at least three written quotes",
        "Start a moving folder for quotes, contracts, receipts, and the inventory",
        "Declutter room by room: sell, donate, or toss what you won't move",
        "Measure big furniture and the doorways at the new place",
        "Request school and medical records, and book time off for moving day",
    )),
    ("6 weeks before", (
        "Book the movers or truck and confirm the date in writing",
        "Order boxes, tape, markers, and labels (about 10 boxes per room is a start)",
        "Pack the things you rarely use: seasonal items, books, guest-room decor",
        "Number every box as you pack it and add a line to your inventory",
        "Check what your mover's valuation coverage or your insurance pays for damage",
    )),
    ("4 weeks before", (
        "File a change of address with the post office",
        "Schedule utilities to stop at the old place and start at the new one",
        "Update your address with your bank, employer, insurance, and subscriptions",
        "Refill prescriptions and arrange pet or childcare for moving day",
        "Reserve elevators or parking at both homes if the building needs it",
    )),
    ("2 weeks before", (
        "Pack room by room, labeling each box with its room at the new home",
        "Reconfirm the movers' arrival time and the new address",
        "Eat down the freezer and pantry, and return anything you've borrowed",
        "Take apart furniture and bag and label the screws and hardware",
    )),
    ("Moving week", (
        "Pack an Open First box: sheets, towels, toilet paper, tools, chargers, snacks",
        "Pack a suitcase with clothes and toiletries for the first few days",
        "Defrost and clean the fridge and freezer a day before",
        "Set aside documents, valuables, and medicine to carry with you",
    )),
    ("Moving day", (
        "Walk the movers through and point out anything fragile",
        "Count the boxes onto the truck against your inventory",
        "Check closets, cabinets, the attic, and the garage before you leave",
        "Photograph meter readings and the empty rooms",
    )),
    ("After the move", (
        "Count boxes off the truck and note damage on the paperwork before signing",
        "Unpack the Open First box, then the kitchen and bedrooms",
        "Update your driver's license and car registration (deadlines vary by state)",
        "Report any loss or damage to the mover quickly and keep the photos",
    )),
)


def checklist_doc(path, page_size, title, subtitle, sections, campaign, promo):
    page_w, page_h = page_size
    margin = 0.6 * INCH
    c = canvas.Canvas(str(path), pagesize=page_size)
    c.setTitle(title)
    c.setAuthor("Moving Box Tracker")
    col_gap = 22
    col_w = (page_w - 2 * margin - col_gap) / 2
    text_w = col_w - 18
    line_h = 11.5
    promo_h = 92

    def new_page(first):
        if not first:
            c.showPage()
        page_header(c, page_size, margin, title, subtitle, (("Moving day", 1), ("New address", 2)))
        return page_h - margin - 110

    # Lay sections into two columns, top to bottom, left then right. Only the last page
    # reserves room for the promo, so the first page fills to the margin.
    top = new_page(True)
    y, col = top, 0
    floor = margin

    def advance():
        nonlocal top, y, col, floor
        if col == 0:
            y, col = top, 1
        else:
            top = new_page(False)
            y, col = top, 0
            floor = margin + promo_h + 16

    def section_heading(x, heading):
        nonlocal y
        c.setFillColor(WARM_SOFT)
        c.roundRect(x, y - 16, col_w, 18, 4, stroke=0, fill=1)
        small_caps(c, heading, x + 7, y - 11, size=7.5, color=WARM_DEEP)
        y -= 30

    def box(name, tooltip, x):
        c.acroForm.checkbox(
            name=name, tooltip=tooltip, x=x + 2, y=y - 1, size=9, buttonStyle="check",
            borderWidth=0.75, borderColor=INK, fillColor=white, textColor=INK, forceBorder=True,
        )

    index = 0
    for heading, tasks in sections:
        heights = [len(simpleSplit(t, "Helvetica", 9, text_w)) * line_h + 6 for t in tasks]
        if y - (26 + sum(heights)) < floor:
            advance()
        x = margin + col * (col_w + col_gap)
        section_heading(x, heading)
        for task, h in zip(tasks, heights):
            box(f"task_{index}", task, x)
            c.setFillColor(INK)
            c.setFont("Helvetica", 9)
            for i, line in enumerate(simpleSplit(task, "Helvetica", 9, text_w)):
                c.drawString(x + 18, y + 1 - i * line_h, line)
            y -= h
            index += 1
        y -= 10

    # Blank, fillable rows for the reader's own tasks, down to the promo on the last page.
    own_h = 20
    if col == 0 or y - (30 + 5 * own_h) < margin + promo_h + 16:
        advance()
    floor = margin + promo_h + 16
    c.setStrokeColor(RULE)
    c.setLineWidth(0.6)
    own = 0
    # Fill the rest of this column, and the right column too when starting on the left.
    for heading, last_col in (("Your own tasks", col), ("Notes and phone numbers", 1)):
        if last_col != col:
            y, col = top, last_col
        x = margin + col * (col_w + col_gap)
        section_heading(x, heading)
        c.setStrokeColor(RULE)
        while y - own_h + 8 > floor:
            if heading.startswith("Your"):
                box(f"own_check_{own}", "Done", x)
            indent = 18 if heading.startswith("Your") else 0
            c.line(x + indent, y - 3, x + col_w, y - 3)
            text_field(c, f"own_{own}", x + indent, y - 2, col_w - indent, 13, size=9, tooltip=heading)
            y -= own_h
            own += 1
        if col == 1:
            break

    promo_panel(c, margin, margin, page_w - 2 * margin, promo_h, campaign, *promo)
    c.showPage()
    c.save()


BOX_PROMO = (
    "Rather search than scroll through a list?",
    (
        "Moving Box Tracker for iPhone prints a scannable QR label for every box",
        "and finds any packed item in seconds. Free to use, no subscription.",
    ),
)
ITEM_PROMO = (
    "Keep this list on your phone instead",
    (
        "Moving Box Tracker for iPhone lists what's in every box, with photos,",
        "and finds any item by search or by scanning the box's QR label.",
    ),
)
CHECKLIST_PROMO = (
    "Know what's in every box when you get there",
    (
        "Moving Box Tracker for iPhone prints a QR label for every box. Scan it to",
        "see what's inside, or search to find which box the coffee maker is in.",
    ),
)


def wrapped_text(c, text, x, y, width, font="Helvetica", size=9.5, leading=12, color=INK):
    """Draw wrapped text and return the next baseline below it."""
    c.setFillColor(color)
    c.setFont(font, size)
    lines = simpleSplit(text, font, size, width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def guide_bullet(c, number, title, body, x, y, width):
    c.setFillColor(WARM_SOFT)
    c.roundRect(x, y - 18, 24, 24, 7, stroke=0, fill=1)
    c.setFillColor(WARM_DEEP)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + 12, y - 10, str(number))
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(x + 34, y, title)
    return wrapped_text(c, body, x + 34, y - 14, width - 34, size=8.8, leading=10.5, color=MUTED) - 9


def organization_guide(path):
    """Two-page partner handout: useful by itself, with a restrained app CTA."""
    page_w, page_h = letter
    margin = 40
    c = canvas.Canvas(str(path), pagesize=letter)
    c.setTitle("The Calm Moving Box System")
    c.setAuthor("Moving Box Tracker")
    c.setSubject("A free guide to labeling, inventorying, moving, and unpacking boxes")

    def footer(page):
        c.setStrokeColor(RULE)
        c.line(margin, 28, page_w - margin, 28)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 6.5)
        c.drawString(margin, 17, "Free guide from Moving Box Tracker - movingboxtracker.com")
        c.drawRightString(page_w - margin, 17, f"{page} / 2")

    # Page 1: the repeatable packing and labeling system.
    small_caps(c, "Free moving guide", margin, page_h - 46, size=7.2, color=WARM_DEEP)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(margin, page_h - 75, "The Calm Moving Box System")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10.5)
    c.drawString(margin, page_h - 94, "Label, track, and unpack without opening every box.")
    c.setStrokeColor(RULE)
    c.line(page_w - 175, page_h - 88, page_w - margin, page_h - 88)
    small_caps(c, "Shared by", page_w - 175, page_h - 73, size=6.2)

    # Four rules summary.
    box_y, box_h = page_h - 210, 86
    c.setFillColor(WARM_SOFT)
    c.roundRect(margin, box_y, page_w - 2 * margin, box_h, 14, stroke=0, fill=1)
    small_caps(c, "The whole system", margin + 16, box_y + box_h - 18, size=6.8, color=WARM_DEEP)
    rules = (
        ("1", "One number", "Number boxes in one sequence."),
        ("2", "One destination", "Use the room in the new home."),
        ("3", "Useful contents", "List what you may need to find."),
        ("4", "Visible labels", "Mark the top and at least one side."),
    )
    rule_w = (page_w - 2 * margin - 32) / 4
    for i, (num, title, body) in enumerate(rules):
        x = margin + 16 + i * rule_w
        c.setFillColor(WARM_DEEP)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(x, box_y + 42, num)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(x + 16, box_y + 43, title)
        wrapped_text(c, body, x, box_y + 26, rule_w - 8, size=7.6, leading=9, color=MUTED)

    # Preparation row.
    section_y = box_y - 36
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, section_y, "Before the first box")
    cards_y, card_h, gap = section_y - 82, 64, 10
    card_w = (page_w - 2 * margin - 2 * gap) / 3
    prep = (
        ("Name destinations", "Use clear names for the rooms in the new home, such as Bedroom: Sam or Office."),
        ("Pick room colors", "A color helps helpers sort quickly. Still write the room name so color is never the only clue."),
        ("Keep tools together", "Put labels, thick markers, tape, and your inventory in one portable packing station."),
    )
    for i, (title, body) in enumerate(prep):
        x = margin + i * (card_w + gap)
        c.setFillColor(HexColor("#f7f6f3"))
        c.setStrokeColor(RULE)
        c.roundRect(x, cards_y, card_w, card_h, 10, stroke=1, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x + 12, cards_y + card_h - 18, title)
        wrapped_text(c, body, x + 12, cards_y + card_h - 33, card_w - 24, size=7.4, leading=9, color=MUTED)

    # Box example plus workflow.
    section_y = cards_y - 34
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, section_y, "For every box")
    example_x, example_y, example_w, example_h = margin, 205, 225, 218
    c.setStrokeColor(OUTLINE)
    c.setFillColor(white)
    c.roundRect(example_x, example_y, example_w, example_h, 14, stroke=1, fill=1)
    c.setFillColor(WARM_SOFT)
    c.roundRect(example_x + 12, example_y + example_h - 68, example_w - 24, 52, 8, stroke=0, fill=1)
    small_caps(c, "Destination room", example_x + 22, example_y + example_h - 33, size=5.8, color=WARM_DEEP)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(example_x + 22, example_y + example_h - 54, "KITCHEN")
    small_caps(c, "Box", example_x + example_w - 72, example_y + example_h - 33, size=5.8, color=WARM_DEEP)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(example_x + example_w - 22, example_y + example_h - 55, "014")
    small_caps(c, "Key contents", example_x + 22, example_y + example_h - 90)
    c.setFillColor(INK)
    c.setFont("Helvetica", 10)
    for i, line in enumerate(("Coffee maker", "Mugs and filters", "Tea kettle")):
        c.drawString(example_x + 22, example_y + example_h - 110 - i * 19, line)
        c.setStrokeColor(RULE)
        c.line(example_x + 22, example_y + example_h - 114 - i * 19, example_x + example_w - 22, example_y + example_h - 114 - i * 19)
    check_y = example_y + 28
    for i, label in enumerate(("FRAGILE", "THIS SIDE UP", "OPEN FIRST")):
        x = example_x + 22 + i * 64
        c.setStrokeColor(INK)
        c.rect(x, check_y, 8, 8, stroke=1, fill=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 5.3)
        c.drawString(x + 11, check_y + 1.2, label)

    x = example_x + example_w + 24
    y = example_y + example_h - 4
    steps = (
        (1, "Pack one room at a time", "Mixed-room boxes are harder to unload and harder to find later."),
        (2, "Record before you seal", "Write the box number, destination, and three to six useful contents while the box is open."),
        (3, "Flag only what matters", "Mark Fragile, This Side Up, or Open First only when the instruction is true."),
        (4, "Label top and side", "A top label helps while carrying. A side label stays visible in a stack."),
        (5, "Add it to the master list", "The number connects the physical box to your paper list or searchable inventory."),
    )
    for num, title, body in steps:
        y = guide_bullet(c, num, title, body, x, y, page_w - margin - x)

    # Safety strip.
    c.setFillColor(HexColor("#f7f6f3"))
    c.setStrokeColor(RULE)
    c.roundRect(margin, 64, page_w - 2 * margin, 112, 14, stroke=1, fill=1)
    small_caps(c, "Pack safely", margin + 16, 156, size=6.8, color=WARM_DEEP)
    safety = (
        ("Heavy goes small", "Books, canned goods, and tools belong in small boxes. Put pillows and linens in large ones."),
        ("Nothing should rattle", "Fill gaps and cushion breakables. The lid should close without force or bowing."),
        ("Lift before sealing", "If you cannot lift the box comfortably, make it lighter. Keep boxes around 50 lb or less."),
    )
    col_w = (page_w - 2 * margin - 32) / 3
    for i, (title, body) in enumerate(safety):
        x = margin + 16 + i * col_w
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(x, 135, title)
        wrapped_text(c, body, x, 120, col_w - 10, size=7.5, leading=9, color=MUTED)
    footer(1)
    c.showPage()

    # Page 2: moving day, arrival, and the optional app workflow.
    small_caps(c, "Moving day and arrival", margin, page_h - 46, size=7.2, color=WARM_DEEP)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(margin, page_h - 75, "Move it. Find it. Unpack it.")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 10.5)
    c.drawString(margin, page_h - 94, "A few decisions now prevent the first night from becoming a box hunt.")

    # Essentials + carry-yourself cards.
    top_y, panel_h, gap = page_h - 260, 128, 14
    panel_w = (page_w - 2 * margin - gap) / 2
    panels = (
        ("Make one Open First box", ("Bedding and towels", "Toilet paper and soap", "Chargers and basic tools", "Coffee, snacks, and pet supplies")),
        ("Carry these with you", ("Medication and keys", "IDs and important documents", "Jewelry and irreplaceable items", "A change of clothes and toiletries")),
    )
    for i, (title, items) in enumerate(panels):
        x = margin + i * (panel_w + gap)
        c.setFillColor(WARM_SOFT if i == 0 else HexColor("#f7f6f3"))
        c.setStrokeColor(RULE)
        c.roundRect(x, top_y, panel_w, panel_h, 14, stroke=1 if i else 0, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(x + 16, top_y + panel_h - 24, title)
        c.setFont("Helvetica", 8.7)
        for j, item in enumerate(items):
            iy = top_y + panel_h - 48 - j * 18
            c.setStrokeColor(WARM_DEEP)
            c.rect(x + 17, iy - 1, 7, 7, stroke=1, fill=0)
            c.setFillColor(INK)
            c.drawString(x + 30, iy, item)

    # Mini moving-day inventory table.
    table_top = top_y - 52
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, table_top + 20, "Count boxes onto the truck and off again")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, table_top + 6, "A missing number is easiest to investigate while the movers are still present.")
    cols = (("BOX", 48), ("DESTINATION", 118), ("KEY CONTENTS", 210), ("LOADED", 48), ("RECEIVED", 50))
    x = margin
    c.setFillColor(WARM_SOFT)
    c.rect(margin, table_top - 18, page_w - 2 * margin, 22, stroke=0, fill=1)
    for name, w in cols:
        small_caps(c, name, x + 5, table_top - 10, size=5.8, color=WARM_DEEP)
        x += w
    row_h = 24
    for r in range(6):
        y = table_top - 18 - (r + 1) * row_h
        c.setStrokeColor(RULE)
        c.line(margin, y, page_w - margin, y)
        x = margin
        for name, w in cols:
            key = f"guide_{name.lower()}_{r}"
            if name in ("LOADED", "RECEIVED"):
                c.acroForm.checkbox(
                    name=key, tooltip=name.title(), x=x + (w - 9) / 2, y=y + 7.5, size=9,
                    buttonStyle="check", borderWidth=0.75, borderColor=INK,
                    fillColor=white, textColor=INK, forceBorder=True,
                )
            else:
                text_field(c, key, x + 4, y + 4, w - 8, row_h - 7, size=8.5, tooltip=name.title())
            x += w
    table_bottom = table_top - 18 - 6 * row_h
    x = margin
    for _, w in cols[:-1]:
        x += w
        c.line(x, table_top - 18, x, table_bottom)

    # Arrival steps.
    arrival_y = table_bottom - 35
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, arrival_y, "At the new home")
    arrival = (
        ("Mark the doors", "Put the matching room name or color on each doorway so helpers can unload without asking."),
        ("Check as boxes arrive", "Tick each number off and photograph damage before signing the delivery paperwork."),
        ("Unpack in order", "Start with Open First, then bedrooms and the kitchen. Leave low-priority boxes for later."),
    )
    y = arrival_y - 22
    card_w = (page_w - 2 * margin - 20) / 3
    for i, (title, body) in enumerate(arrival):
        x = margin + i * (card_w + 10)
        c.setFillColor(HexColor("#f7f6f3"))
        c.setStrokeColor(RULE)
        c.roundRect(x, y - 72, card_w, 72, 10, stroke=1, fill=1)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.8)
        c.drawString(x + 12, y - 19, title)
        wrapped_text(c, body, x + 12, y - 34, card_w - 24, size=7.4, leading=9, color=MUTED)

    # Restrained app panel.
    promo_y, promo_h = 54, 112
    c.setFillColor(HexColor("#17191c"))
    c.roundRect(margin, promo_y, page_w - 2 * margin, promo_h, 15, stroke=0, fill=1)
    qr_size = 86
    guide_link = app_store_link("pdf-organizing-guide")
    c.drawImage(qr_image(guide_link), page_w - margin - qr_size - 13, promo_y + 13, qr_size, qr_size)
    link_area(c, guide_link, margin, promo_y, page_w - 2 * margin, promo_h)
    if ICON.exists():
        icon = Image.open(ICON).convert("RGB")
        icon.thumbnail((144, 144))
        c.drawImage(ImageReader(icon), margin + 16, promo_y + promo_h - 50, 34, 34, mask="auto")
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin + 62, promo_y + promo_h - 30, "Prefer a searchable inventory?")
    c.setFillColor(HexColor("#c6c8cc"))
    c.setFont("Helvetica", 8.8)
    wrapped_text(c, "Moving Box Tracker for iPhone keeps every box, photo, and item searchable. Print a QR label, scan a box to see its contents, and share the move privately with your household.", margin + 16, promo_y + 45, page_w - 2 * margin - qr_size - 45, size=8.8, leading=11, color=HexColor("#c6c8cc"))
    c.setFillColor(HexColor("#e4aa68"))
    c.setFont("Helvetica-Bold", 8)
    c.drawString(margin + 16, promo_y + 16, "Scan or tap to view on the App Store - free for unlimited boxes")

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.6)
    c.drawString(margin, 38, "Common guidance reviewed from U-Haul, Lowe's, Move.org, Allied Van Lines, and Mayflower.")
    footer(2)
    c.showPage()
    c.save()

BOX_COLUMNS = (("Box #", 48, False), ("Room", 110, False), ("Contents", None, False), ("Packed", 46, True), ("Arrived", 48, True))
ITEM_COLUMNS = (("Room", 82, False), ("Item", None, False), ("Qty", 34, False), ("Box #", 44, False), ("Condition", 78, False), ("Value", 56, False))
PCS_COLUMNS = (
    ("Item", None, False), ("Box #", 42, False), ("Mover tag #", 62, False), ("Condition", 72, False),
    ("Value", 52, False), ("Pro-gear", 46, True), ("Photo", 38, True),
)


def write_previews(paths):
    import pypdfium2 as pdfium

    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for path in paths:
        pdf = pdfium.PdfDocument(str(path))
        pdf.init_forms()  # so checkbox outlines render
        page = pdf[0]
        image = page.render(scale=900 / page.get_height()).to_pil().convert("RGB")
        image.save(PREVIEWS / (path.stem + ".jpg"), quality=82, optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    written = []

    def out(name):
        written.append(OUT / name)
        return OUT / name

    label_sheet(out("moving-box-labels-avery-5164.pdf"), AVERY_5164, "Moving Box Labels – Avery 5164 / 8164", cut_lines=False)
    label_sheet(out("moving-box-labels-avery-5168.pdf"), AVERY_5168, "Moving Box Labels – Avery 5168 / 8168", cut_lines=False)
    label_sheet(out("moving-box-labels-letter.pdf"), PLAIN_LETTER, "Moving Box Labels – Letter paper", cut_lines=True)
    label_sheet(out("moving-box-labels-a4.pdf"), PLAIN_A4, "Moving Box Labels – A4 paper", cut_lines=True)

    box_subtitle = "Number every box, note its room and contents, and tick it off as it's packed and as it arrives."
    box_fields = (("Move", 260), ("Moving day", 150), ("Page", 40))
    for name, size in (("letter", letter), ("a4", A4)):
        table_sheet(out(f"moving-box-inventory-checklist-{name}.pdf"), size, "Moving Box Inventory", box_subtitle,
                    box_fields, BOX_COLUMNS, "pdf-box-checklist", BOX_PROMO)

    item_subtitle = "List what you own room by room: what it is, how many, which box it's in, its condition, and a rough value."
    for name, size in (("letter", letter), ("a4", A4)):
        table_sheet(out(f"moving-inventory-list-{name}.pdf"), size, "Moving Inventory List", item_subtitle,
                    (("Name", 3), ("Moving day", 2), ("Page", 1)), ITEM_COLUMNS, "pdf-inventory-list", ITEM_PROMO, pages=2)

    checklist_subtitle = "A week-by-week plan from eight weeks out to the first week in your new home."
    for name, size in (("letter", letter), ("a4", A4)):
        checklist_doc(out(f"moving-checklist-{name}.pdf"), size, "Moving Checklist", checklist_subtitle,
                      MOVING_CHECKLIST, "pdf-moving-checklist", CHECKLIST_PROMO)

    pcs_subtitle = "Your own record of what you own, matched to the movers' tag numbers. Keep it with your orders."
    table_sheet(out("pcs-move-inventory-letter.pdf"), letter, "PCS Move Inventory", pcs_subtitle,
                (("Name", 3), ("Pickup date", 2), ("Shipment", 2), ("Page", 1)), PCS_COLUMNS, "pdf-pcs-inventory", ITEM_PROMO, pages=2)

    organization_guide(out("moving-box-organization-guide.pdf"))

    print(f"Wrote {len(written)} printables to {OUT}")
    if "--previews" in sys.argv:
        write_previews(written)
        print(f"Wrote previews to {PREVIEWS}")


if __name__ == "__main__":
    main()
