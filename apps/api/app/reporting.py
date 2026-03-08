"""Generate a polished, multi-page business-intelligence PDF.

Design principles
-----------------
* Dark-theme that matches the web dashboard.
* Fixed page margins with a flowing cursor — content is **never** placed at
  hard-coded y-offsets so nothing can overlap.
* Every visual block (stat row, chart, text card, table) is self-contained:
  it measures its own height, checks whether it fits on the current page,
  and triggers a page-break when needed.
* ReportLab canvas only — no Platypus frames, no HTML/CSS conversion.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen.canvas import Canvas

# ── Constants ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(letter)
MARGIN = 36
CONTENT_W = PAGE_W - MARGIN * 2
GUTTER = 14  # gap between side-by-side cards
CARD_RADIUS = 14
CARD_PAD = 16

# Palette (mirrors CSS variables)
BG = "#07111C"
PANEL = "#0B1522"
CARD_BG = "#102033"
CARD_STROKE = "#22364E"
TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#CBD5E1"
TEXT_MUTED = "#94A3B8"
ACCENT = "#F97316"
ACCENT2 = "#38BDF8"
DANGER = "#F43F5E"
OK = "#22C55E"
GRID_COLOR = "#203046"
AXIS_COLOR = "#4B617A"

FONT = "Helvetica"
FONT_B = "Helvetica-Bold"


# ── Helpers ────────────────────────────────────────────────────────────────

def _hex_rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    if len(h) != 6:
        return (148, 163, 184)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _pil_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _kickoff_str(iso: str) -> str:
    dt = datetime.fromisoformat(iso)
    h = dt.hour % 12 or 12
    ap = "AM" if dt.hour < 12 else "PM"
    return f"{dt.strftime('%b')} {dt.day}, {dt.year} at {h}:{dt.minute:02d} {ap} local"


def _fmt_money(v: float | int) -> str:
    return f"${v:,.0f}"


def _fmt_number(v: float | int) -> str:
    return f"{int(v):,}"


def _fmt_pct(v: float | int) -> str:
    return f"{float(v):.0f}%"


# ── Canvas primitives ─────────────────────────────────────────────────────

def _draw_bg(c: Canvas) -> None:
    """Full-page dark background."""
    c.setFillColor(HexColor(BG))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    c.setFillColor(HexColor(PANEL))
    c.roundRect(MARGIN - 6, MARGIN - 6, PAGE_W - (MARGIN - 6) * 2, PAGE_H - (MARGIN - 6) * 2, 20, fill=1, stroke=0)


def _card(c: Canvas, x: float, y: float, w: float, h: float, *, fill: str = CARD_BG, stroke: str = CARD_STROKE) -> None:
    c.setFillColor(HexColor(fill))
    c.setStrokeColor(HexColor(stroke))
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, CARD_RADIUS, stroke=1, fill=1)


def _text(c: Canvas, x: float, y: float, txt: str, *, font: str = FONT, size: int = 10, color: str = TEXT_SECONDARY) -> None:
    c.setFillColor(HexColor(color))
    c.setFont(font, size)
    c.drawString(x, y, txt)


def _text_right(c: Canvas, x: float, y: float, txt: str, *, font: str = FONT, size: int = 10, color: str = TEXT_SECONDARY) -> None:
    c.setFillColor(HexColor(color))
    c.setFont(font, size)
    c.drawRightString(x, y, txt)


def _multiline(c: Canvas, txt: str, x: float, y: float, max_w: float, *, font: str = FONT, size: int = 10, color: str = TEXT_SECONDARY, leading: float = 0) -> float:
    """Draw wrapped text. Returns the y position *below* the last line."""
    lead = leading or (size + 3)
    lines = simpleSplit(txt, font, size, max_w)
    c.setFillColor(HexColor(color))
    c.setFont(font, size)
    cur = y
    for ln in lines:
        c.drawString(x, cur, ln)
        cur -= lead
    return cur


def _chip(c: Canvas, x: float, y: float, txt: str, *, bg: str, fg: str) -> float:
    w = max(50, 12 + len(txt) * 5.4)
    c.setFillColor(HexColor(bg))
    c.roundRect(x, y, w, 17, 8, fill=1, stroke=0)
    c.setFillColor(HexColor(fg))
    c.setFont(FONT_B, 7.5)
    c.drawString(x + 7, y + 5, txt.upper())
    return w + 6


def _bar_h(c: Canvas, x: float, y: float, w: float, h: float, pct: float, color: str) -> None:
    """Horizontal progress bar."""
    c.setFillColor(HexColor("#12263B"))
    c.roundRect(x, y, w, h, h / 2, fill=1, stroke=0)
    fill_w = max(0, min(w, w * pct))
    if fill_w > 0:
        c.setFillColor(HexColor(color))
        c.roundRect(x, y, fill_w, h, h / 2, fill=1, stroke=0)


# ── PIL chart builders ─────────────────────────────────────────────────────

def _build_demand_chart(
    series: list[dict[str, Any]],
    *,
    home_color: str,
    away_color: str,
    width: int = 1060,
    height: int = 360,
) -> BytesIO:
    """Active-visitors bar chart with match-phase coloring and markers."""
    img = Image.new("RGB", (width, height), "#0B1522")
    draw = ImageDraw.Draw(img)
    tfont = _pil_font(18, bold=True)
    sfont = _pil_font(12)
    xfont = _pil_font(11)

    # Card outline
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=20, fill="#0E1B2A", outline="#1E3149", width=1)
    draw.text((24, 16), "Active visitors over time", fill="#F8FAFC", font=tfont)

    left, top, right, bottom = 64, 56, width - 20, height - 44

    # Y-axis grid
    max_val = max((p.get("value", 0) for p in series), default=1) or 1
    for i in range(5):
        y = bottom - (bottom - top) * i / 4
        draw.line((left, int(y), right, int(y)), fill="#1A2C42", width=1)
        lbl = f"{int(max_val * i / 4):,}"
        bb = draw.textbbox((0, 0), lbl, font=xfont)
        draw.text((left - 8 - (bb[2] - bb[0]), int(y) - 7), lbl, fill="#6B839E", font=xfont)

    span = max(1, len(series) - 1)
    ko_step = next((p["step"] for p in series if p.get("marker") == "kickoff"), None)
    fw_step = next((p["step"] for p in series if p.get("marker") == "final_whistle"), None)
    has_match = ko_step is not None and fw_step is not None

    # Bars
    bar_w = max(3, int((right - left) / max(len(series), 1)) - 2)
    for i, pt in enumerate(series):
        x = int(left + (right - left) * i / span)
        val = pt.get("value", 0)
        bar_h_px = int((bottom - top) * val / max_val)
        y0 = bottom - bar_h_px

        step = pt.get("step", 0)
        if has_match and ko_step <= step <= fw_step:
            fill = "#F97316"
        elif has_match and step > fw_step:
            fill = "#F59E0B"
        else:
            fill = "#38BDF8"

        draw.rounded_rectangle((x - bar_w // 2, y0, x + bar_w // 2, bottom), radius=2, fill=fill)

    # X-axis labels (every 2 hours)
    seen: set[str] = set()
    for pt in series:
        if pt.get("step", 0) % 8 != 0:
            continue
        lbl = pt["label"]
        if lbl in seen:
            continue
        seen.add(lbl)
        i = series.index(pt)
        x = int(left + (right - left) * i / span)
        bb = draw.textbbox((0, 0), lbl, font=xfont)
        draw.text((x - (bb[2] - bb[0]) // 2, bottom + 8), lbl, fill="#8FA3BD", font=xfont)

    # Marker lines
    marker_pts = [p for p in series if p.get("marker")]
    for pt in marker_pts:
        i = series.index(pt)
        x = int(left + (right - left) * i / span)
        mname = str(pt["marker"]).replace("_", " ").upper()
        col = "#F43F5E" if "PEAK" in mname else "#F97316"
        draw.line((x, top, x, bottom), fill=col, width=1)
        draw.text((x + 4, top + 2), mname, fill="#FDBA74", font=xfont)

    # Peak dot
    peak_pt = max(series, key=lambda p: p.get("value", 0), default=None)
    if peak_pt:
        pi = series.index(peak_pt)
        px = int(left + (right - left) * pi / span)
        py = int(bottom - (bottom - top) * peak_pt["value"] / max_val)
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), fill="#F43F5E", outline="#FFE4E6", width=2)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _build_comparison_chart(
    rows: list[dict[str, Any]],
    *,
    width: int = 520,
    height: int = 200,
) -> BytesIO:
    """Horizontal bar chart comparing revenue across matches."""
    img = Image.new("RGB", (width, height), "#0B1522")
    draw = ImageDraw.Draw(img)
    tfont = _pil_font(15, bold=True)
    lfont = _pil_font(11)
    vfont = _pil_font(11, bold=True)

    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=16, fill="#0E1B2A", outline="#1E3149", width=1)
    draw.text((16, 12), "Revenue by match", fill="#F8FAFC", font=tfont)

    top, bottom = 42, height - 12
    left, right = 140, width - 16
    max_val = max((r.get("revenue_estimate", 0) for r in rows), default=1) or 1
    count = min(len(rows), 5)
    if count == 0:
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    bar_h = max(14, int((bottom - top - (count - 1) * 6) / count))
    for i, row in enumerate(rows[:count]):
        y = top + i * (bar_h + 6)
        val = row.get("revenue_estimate", 0)
        bar_w = int((right - left) * val / max_val)

        # Label
        title = str(row.get("title", ""))[:20]
        draw.text((12, y + 1), title, fill="#CBD5E1", font=lfont)

        # Bar
        draw.rounded_rectangle((left, y, left + max(bar_w, 4), y + bar_h), radius=6, fill="#F97316")

        # Value
        vlbl = f"${val:,.0f}"
        draw.text((left + bar_w + 6, y + 1), vlbl, fill="#E2E8F0", font=vfont)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ── Page manager ───────────────────────────────────────────────────────────

class _PageCursor:
    """Tracks vertical position on the current page and handles page breaks."""

    def __init__(self, canvas: Canvas) -> None:
        self.c = canvas
        self.y = PAGE_H - MARGIN - 10  # start just inside the top margin
        self.floor = MARGIN + 16  # minimum y before forcing a new page

    def new_page(self) -> None:
        self.c.showPage()
        _draw_bg(self.c)
        self.y = PAGE_H - MARGIN - 10

    def ensure(self, needed: float) -> None:
        """If *needed* vertical space won't fit, start a new page."""
        if self.y - needed < self.floor:
            self.new_page()

    def skip(self, h: float) -> None:
        self.y -= h


# ── Section renderers ──────────────────────────────────────────────────────

def _section_hero(cur: _PageCursor, match: dict, detail: dict) -> None:
    h = 82
    cur.ensure(h + 8)
    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h)

    # Business name
    _text(cur.c, x + CARD_PAD, y + h - 28, detail["business"]["name"], font=FONT_B, size=22, color=TEXT_PRIMARY)
    # Subtitle
    btype = detail["business"]["type"].replace("_", " ").title()
    zone = detail["zone_context"]["zone_name"]
    rating = detail.get("google_rating", {}).get("value", 0)
    _text(cur.c, x + CARD_PAD, y + h - 46, f"{btype}  |  {zone}  |  {rating:.1f} stars", size=10, color=TEXT_SECONDARY)
    # Match + kickoff
    _text(cur.c, x + CARD_PAD, y + h - 62, f"{match['title']}  |  Kickoff {_kickoff_str(match['kickoff_local'])}  |  {match['venue']}", size=9, color=TEXT_MUTED)

    # Team pills (right side)
    home = match["home_team"]
    away = match["away_team"]
    rx = x + w - CARD_PAD
    pw = max(70, 10 + len(home["name"]) * 7)
    cur.c.setFillColor(HexColor(home["color"]))
    cur.c.roundRect(rx - pw * 2 - 8, y + 10, pw, 20, 10, fill=1, stroke=0)
    _text(cur.c, rx - pw * 2 - 8 + 10, y + 16, home["name"], font=FONT_B, size=9, color="#08111D")

    aw = max(70, 10 + len(away["name"]) * 7)
    cur.c.setFillColor(HexColor(away["color"]))
    cur.c.roundRect(rx - aw, y + 10, aw, 20, 10, fill=1, stroke=0)
    _text(cur.c, rx - aw + 10, y + 16, away["name"], font=FONT_B, size=9, color="#08111D")

    # Stage + pressure chips
    stage_chip_x = rx - pw * 2 - 8
    _chip(cur.c, stage_chip_x - 130, y + 50, match["stage"], bg="#2B1709", fg="#FDBA74")
    _chip(cur.c, stage_chip_x - 60, y + 50, detail["playbook"]["pressure_level"], bg="#172554", fg="#93C5FD")

    cur.y = y - 8


def _section_stats(cur: _PageCursor, detail: dict) -> None:
    """Four KPI stat cards in a row."""
    card_h = 80
    cur.ensure(card_h + 8)

    cards_data = detail.get("insight_cards", [])[:4]
    if not cards_data:
        return

    gap = 10
    count = len(cards_data)
    card_w = (CONTENT_W - gap * (count - 1)) / count

    tone_colors = {"danger": DANGER, "warning": ACCENT, "ok": OK, "accent": ACCENT2, "muted": TEXT_MUTED}
    y = cur.y - card_h

    for i, card in enumerate(cards_data):
        x = MARGIN + i * (card_w + gap)
        accent = tone_colors.get(card.get("tone", "ok"), ACCENT2)
        _card(cur.c, x, y, card_w, card_h)

        # Accent bar at top of card
        cur.c.setFillColor(HexColor(accent))
        cur.c.rect(x + 12, y + card_h - 14, card_w - 24, 3, fill=1, stroke=0)

        # Label
        _text(cur.c, x + CARD_PAD, y + card_h - 30, card["label"].upper(), font=FONT_B, size=8, color=TEXT_MUTED)
        # Value
        val_size = 18 if len(card["value"]) <= 10 else 15
        _text(cur.c, x + CARD_PAD, y + card_h - 50, card["value"], font=FONT_B, size=val_size, color=TEXT_PRIMARY)
        # Detail
        _text(cur.c, x + CARD_PAD, y + 10, card["detail"][:60], size=8, color="#8FA3BD")

    cur.y = y - 10


def _section_demand_chart(cur: _PageCursor, detail: dict, match: dict) -> None:
    """Full-width active-visitors chart rendered as a PNG image."""
    series = detail.get("active_visitors_series_15m", [])
    if not series:
        return

    img_h = 240
    cur.ensure(img_h + 8)

    buf = _build_demand_chart(
        series,
        home_color=match["home_team"]["color"],
        away_color=match["away_team"]["color"],
    )
    reader = ImageReader(buf)
    y = cur.y - img_h
    cur.c.drawImage(reader, MARGIN, y, width=CONTENT_W, height=img_h, preserveAspectRatio=True, mask="auto")
    cur.y = y - 10


def _section_capacity_gauge(cur: _PageCursor, detail: dict) -> None:
    h = 60
    cur.ensure(h + 8)
    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h)

    pct = detail.get("peak_capacity_pct_capped", 0)
    color = DANGER if pct >= 120 else ACCENT if pct >= 85 else OK
    label = "Over capacity" if pct >= 120 else "Busy window" if pct >= 85 else "Healthy headroom"

    _text(cur.c, x + CARD_PAD, y + h - 20, "PEAK CAPACITY", font=FONT_B, size=8, color=TEXT_MUTED)
    # Bar
    bar_x, bar_y, bar_w, bar_h_px = x + CARD_PAD, y + 14, w - CARD_PAD * 2 - 140, 10
    _bar_h(cur.c, bar_x, bar_y, bar_w, bar_h_px, min(pct / 150.0, 1.0), color)
    # Percent label
    _text(cur.c, bar_x + bar_w + 10, bar_y, f"{pct}%", font=FONT_B, size=11, color=color)
    _text(cur.c, bar_x + bar_w + 60, bar_y, label, size=9, color=TEXT_MUTED)

    cur.y = y - 8


def _section_revenue(cur: _PageCursor, detail: dict) -> None:
    rev = detail.get("served_revenue", {})
    if not rev:
        return
    h = 56
    cur.ensure(h + 8)
    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h, fill="#0F2818", stroke="#1B4332")

    _text(cur.c, x + CARD_PAD, y + h - 20, "ESTIMATED REVENUE", font=FONT_B, size=8, color="#6EE7B7")
    _text(cur.c, x + CARD_PAD, y + 12, _fmt_money(rev["total"]), font=FONT_B, size=22, color="#A7F3D0")

    desc = f'{_fmt_number(rev["served_visits_today"])} served visits  x  ${rev["avg_spend"]:.0f} avg spend  x  {round(rev.get("service_capture_rate", 1) * 100)}% capture'
    _text(cur.c, x + 200, y + 16, desc, size=9, color="#6EE7B7")

    cur.y = y - 8


def _section_audience(cur: _PageCursor, detail: dict, match: dict) -> None:
    mix = detail.get("nationality_mix", {})
    if not mix:
        return

    row_h = 22
    h = 30 + len(mix) * row_h + 30  # title + bars + insight
    cur.ensure(h + 8)

    x, y, w = MARGIN, cur.y - h, CONTENT_W / 2 - GUTTER / 2
    _card(cur.c, x, y, w, h)

    _text(cur.c, x + CARD_PAD, y + h - 22, "Audience mix", font=FONT_B, size=13, color=TEXT_PRIMARY)

    labels = {"team_a": match["home_team"]["name"], "team_b": match["away_team"]["name"], "neutral": "Neutral", "locals": "Locals"}
    colors = {"team_a": match["home_team"]["color"], "team_b": match["away_team"]["color"], "neutral": ACCENT2, "locals": TEXT_MUTED}

    row_y = y + h - 42
    bar_left = x + CARD_PAD + 80
    bar_w = w - CARD_PAD * 2 - 120
    for key, val in mix.items():
        _text(cur.c, x + CARD_PAD, row_y, labels.get(key, key), size=9, color=TEXT_SECONDARY)
        _bar_h(cur.c, bar_left, row_y, bar_w, 8, float(val) / 100.0, colors.get(key, TEXT_MUTED))
        _text_right(cur.c, x + w - CARD_PAD, row_y, _fmt_pct(val), font=FONT_B, size=9, color=TEXT_PRIMARY)
        row_y -= row_h

    dom = detail.get("audience_profile", {})
    if dom.get("dominant_label"):
        _multiline(cur.c, f'Primary: {dom["dominant_label"]} ({dom["dominant_share"]}%). Shape menu & signage.', x + CARD_PAD, row_y - 2, w - CARD_PAD * 2, size=8, color=TEXT_MUTED)

    return x, y, w, h  # pass geometry for side-by-side layout


def _section_recommendation(cur: _PageCursor, detail: dict, *, x: float, y: float, w: float, h: float) -> None:
    """Owner recommendation — drawn at specified position (beside audience card)."""
    _card(cur.c, x, y, w, h, fill="#1E1220", stroke="#4A253A")

    src = detail.get("recommendation", {}).get("source", "heuristic")
    _text(cur.c, x + CARD_PAD, y + h - 22, f"OWNER RECOMMENDATION  |  {src.upper()}", font=FONT_B, size=8, color="#FDBA74")

    text = detail.get("recommendation", {}).get("text", "")
    max_lines = max(3, int((h - 44) / 13))
    lines = simpleSplit(text, FONT_B, 10, w - CARD_PAD * 2)[:max_lines]
    if len(simpleSplit(text, FONT_B, 10, w - CARD_PAD * 2)) > max_lines and lines:
        lines[-1] = lines[-1].rstrip(". ") + "..."

    cursor = y + h - 40
    cur.c.setFillColor(HexColor(TEXT_PRIMARY))
    cur.c.setFont(FONT_B, 10)
    for ln in lines:
        cur.c.drawString(x + CARD_PAD, cursor, ln)
        cursor -= 13


def _section_audience_and_recommendation(cur: _PageCursor, detail: dict, match: dict) -> None:
    """Side-by-side: audience mix (left) and recommendation (right)."""
    mix = detail.get("nationality_mix", {})
    if not mix:
        return

    row_h = 22
    h = max(30 + len(mix) * row_h + 30, 120)
    cur.ensure(h + 8)

    half_w = CONTENT_W / 2 - GUTTER / 2
    y = cur.y - h

    # Left: audience
    lx = MARGIN
    _card(cur.c, lx, y, half_w, h)
    _text(cur.c, lx + CARD_PAD, y + h - 22, "Audience mix", font=FONT_B, size=13, color=TEXT_PRIMARY)

    labels = {"team_a": match["home_team"]["name"], "team_b": match["away_team"]["name"], "neutral": "Neutral", "locals": "Locals"}
    colors_map = {"team_a": match["home_team"]["color"], "team_b": match["away_team"]["color"], "neutral": ACCENT2, "locals": TEXT_MUTED}

    row_y = y + h - 44
    bar_left = lx + CARD_PAD + 80
    bar_w = half_w - CARD_PAD * 2 - 120
    for key, val in mix.items():
        _text(cur.c, lx + CARD_PAD, row_y, labels.get(key, key), size=9, color=TEXT_SECONDARY)
        _bar_h(cur.c, bar_left, row_y, bar_w, 8, float(val) / 100.0, colors_map.get(key, TEXT_MUTED))
        _text_right(cur.c, lx + half_w - CARD_PAD, row_y, _fmt_pct(val), font=FONT_B, size=9, color=TEXT_PRIMARY)
        row_y -= row_h

    dom = detail.get("audience_profile", {})
    if dom.get("dominant_label"):
        _multiline(cur.c, f'Primary: {dom["dominant_label"]} ({dom["dominant_share"]}%). Shape menu & signage.', lx + CARD_PAD, row_y - 2, half_w - CARD_PAD * 2, size=8, color=TEXT_MUTED)

    # Right: recommendation
    rx = MARGIN + half_w + GUTTER
    _section_recommendation(cur, detail, x=rx, y=y, w=half_w, h=h)

    cur.y = y - 10


def _section_playbook(cur: _PageCursor, detail: dict) -> None:
    actions = detail.get("playbook", {}).get("action_options", [])[:5]
    if not actions:
        return

    action_h = 46
    h = 32 + len(actions) * action_h
    cur.ensure(h + 8)

    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h)

    _text(cur.c, x + CARD_PAD, y + h - 22, "Operational playbook", font=FONT_B, size=13, color=TEXT_PRIMARY)

    cursor = y + h - 44
    for action in actions:
        priority = str(action.get("priority", "")).upper()
        p_bg = "#451A03" if priority == "URGENT" else "#172554" if priority == "RECOMMENDED" else "#1E293B"
        p_fg = "#FDBA74" if priority == "URGENT" else "#93C5FD" if priority == "RECOMMENDED" else TEXT_SECONDARY
        chip_end = _chip(cur.c, x + CARD_PAD, cursor - 2, priority, bg=p_bg, fg=p_fg)

        timing = str(action.get("timing", ""))
        _text(cur.c, x + CARD_PAD + chip_end + 2, cursor + 2, timing.upper(), font=FONT_B, size=7, color=TEXT_MUTED)

        _text(cur.c, x + CARD_PAD, cursor - 16, action["title"], font=FONT_B, size=10, color=TEXT_PRIMARY)
        _multiline(cur.c, action["detail"], x + CARD_PAD, cursor - 30, w - CARD_PAD * 2, size=8, color="#8FA3BD", leading=10)
        cursor -= action_h

    cur.y = y - 10


def _section_watchouts(cur: _PageCursor, detail: dict) -> None:
    watchouts = detail.get("playbook", {}).get("watchouts", [])
    if not watchouts:
        return

    line_h = 14
    h = 28 + len(watchouts) * (line_h + 6)
    cur.ensure(h + 8)

    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h, fill="#1A0F14", stroke="#4A253A")

    _text(cur.c, x + CARD_PAD, y + h - 22, "OPERATIONAL WATCHOUTS", font=FONT_B, size=8, color="#FECACA")
    cursor = y + h - 40
    for wo in watchouts[:5]:
        lines = simpleSplit(f"- {wo}", FONT, 9, w - CARD_PAD * 2)
        for ln in lines:
            _text(cur.c, x + CARD_PAD, cursor, ln, size=9, color="#FBCFE8")
            cursor -= line_h

    cur.y = y - 8


def _section_peers(cur: _PageCursor, detail: dict) -> None:
    peers = detail.get("peer_benchmark", [])[:5]
    if not peers:
        return

    row_h = 26
    h = 30 + len(peers) * row_h
    cur.ensure(h + 8)

    x, y, w = MARGIN, cur.y - h, CONTENT_W / 2 - GUTTER / 2
    _card(cur.c, x, y, w, h)

    _text(cur.c, x + CARD_PAD, y + h - 22, "Nearby competition", font=FONT_B, size=13, color=TEXT_PRIMARY)

    cursor = y + h - 44
    for peer in peers:
        if cursor < y + 10:
            break
        # Divider
        cur.c.setStrokeColor(HexColor("#1E3149"))
        cur.c.line(x + CARD_PAD, cursor - 8, x + w - CARD_PAD, cursor - 8)

        _text(cur.c, x + CARD_PAD, cursor, peer["name"], font=FONT_B, size=9, color=TEXT_PRIMARY)
        ptype = peer.get("type", "").replace("_", " ").title()
        grating = peer.get("google_rating", 0)
        _text(cur.c, x + CARD_PAD, cursor - 11, f"{ptype}  |  {grating:.1f} stars", size=8, color=TEXT_MUTED)
        _text_right(cur.c, x + w - CARD_PAD, cursor, f'{peer.get("served_visits_today", 0):,}', font=FONT_B, size=9, color=ACCENT)
        _text_right(cur.c, x + w - CARD_PAD, cursor - 11, f'Peak {peer.get("peak_label", "")}', size=8, color=TEXT_MUTED)
        cursor -= row_h

    return x, y, w, h  # for side-by-side


def _section_comparison_chart(cur: _PageCursor, comparison: dict, *, x: float, y: float, w: float, h: float) -> None:
    """Revenue-by-match chart drawn at specified position."""
    rows = comparison.get("comparisons", [])[:5]
    if not rows:
        return
    buf = _build_comparison_chart(rows, width=int(w * 2), height=int(h * 2))
    reader = ImageReader(buf)
    cur.c.drawImage(reader, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")


def _section_peers_and_comparison(cur: _PageCursor, detail: dict, comparison: dict) -> None:
    peers = detail.get("peer_benchmark", [])[:5]
    rows = comparison.get("comparisons", [])[:5]
    if not peers and not rows:
        return

    row_h = 26
    h = max(30 + len(peers) * row_h, 160)
    cur.ensure(h + 8)

    half_w = CONTENT_W / 2 - GUTTER / 2
    y = cur.y - h

    # Left: peers
    if peers:
        x = MARGIN
        _card(cur.c, x, y, half_w, h)
        _text(cur.c, x + CARD_PAD, y + h - 22, "Nearby competition", font=FONT_B, size=13, color=TEXT_PRIMARY)
        cursor = y + h - 44
        for peer in peers:
            if cursor < y + 10:
                break
            cur.c.setStrokeColor(HexColor("#1E3149"))
            cur.c.line(x + CARD_PAD, cursor - 8, x + half_w - CARD_PAD, cursor - 8)
            _text(cur.c, x + CARD_PAD, cursor, peer["name"], font=FONT_B, size=9, color=TEXT_PRIMARY)
            ptype = peer.get("type", "").replace("_", " ").title()
            grating = peer.get("google_rating", 0)
            _text(cur.c, x + CARD_PAD, cursor - 11, f"{ptype}  |  {grating:.1f} stars", size=8, color=TEXT_MUTED)
            _text_right(cur.c, x + half_w - CARD_PAD, cursor, f'{peer.get("served_visits_today", 0):,}', font=FONT_B, size=9, color=ACCENT)
            _text_right(cur.c, x + half_w - CARD_PAD, cursor - 11, f'Peak {peer.get("peak_label", "")}', size=8, color=TEXT_MUTED)
            cursor -= row_h

    # Right: match comparison chart
    if rows:
        rx = MARGIN + half_w + GUTTER
        _section_comparison_chart(cur, comparison, x=rx, y=y, w=half_w, h=h)

    cur.y = y - 10


def _section_day_comparison(cur: _PageCursor, detail: dict) -> None:
    days = detail.get("day_comparison", [])
    if not days:
        return

    h = 50
    cur.ensure(h + 8)
    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h)

    _text(cur.c, x + CARD_PAD, y + h - 20, "3-DAY DEMAND WINDOW", font=FONT_B, size=8, color=TEXT_MUTED)

    max_val = max((d.get("served_visits_today", 0) for d in days), default=1) or 1
    bar_area_w = w - CARD_PAD * 2 - 10
    bar_unit = bar_area_w / max(len(days), 1)
    for i, d in enumerate(days):
        bx = x + CARD_PAD + i * bar_unit
        bw = bar_unit - 8
        val = d.get("served_visits_today", 0)
        pct = val / max_val
        fill = ACCENT if d.get("day") == 0 else ACCENT2
        bar_h_px = int(18 * pct)
        by = y + 8
        cur.c.setFillColor(HexColor(fill))
        cur.c.roundRect(bx, by, bw, bar_h_px, 4, fill=1, stroke=0)
        _text(cur.c, bx, by + bar_h_px + 2, d.get("label", ""), size=7, color=TEXT_MUTED)
        _text(cur.c, bx + bw + 2, by + 2, _fmt_number(val), font=FONT_B, size=7, color=TEXT_PRIMARY)

    cur.y = y - 8


def _section_methodology(cur: _PageCursor, detail: dict) -> None:
    explanations = detail.get("metric_explanations", {})
    rev_formula = explanations.get("served_revenue", {}).get("formula", "")
    cap_formula = explanations.get("peak_capacity", {}).get("formula", "")
    if not rev_formula and not cap_formula:
        return

    h = 70
    cur.ensure(h + 8)
    x, y, w = MARGIN, cur.y - h, CONTENT_W
    _card(cur.c, x, y, w, h, fill="#0F1A29", stroke="#1E3149")

    _text(cur.c, x + CARD_PAD, y + h - 20, "METHODOLOGY", font=FONT_B, size=8, color=TEXT_MUTED)
    cursor = y + h - 36
    if rev_formula:
        cursor = _multiline(cur.c, f"Revenue: {rev_formula}", x + CARD_PAD, cursor, w - CARD_PAD * 2, size=8, color=TEXT_SECONDARY, leading=10)
        cursor -= 4
    if cap_formula:
        cursor = _multiline(cur.c, f"Capacity: {cap_formula}", x + CARD_PAD, cursor, w - CARD_PAD * 2, size=8, color=TEXT_SECONDARY, leading=10)

    cur.y = y - 8


def _section_footer(cur: _PageCursor, match: dict, detail: dict) -> None:
    h = 22
    cur.ensure(h)
    y = cur.y - h
    _text(cur.c, MARGIN, y + 4, f"MatchFlow World Cup  |  {match['title']}  |  {detail['business']['name']}  |  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}", size=7, color="#4B617A")
    cur.y = y


# ── Main entry point ──────────────────────────────────────────────────────

def build_business_report_pdf(
    *,
    match: dict[str, Any],
    detail: dict[str, Any],
    comparison: dict[str, Any],
    visible_sections: dict[str, bool],
    output_path: Path,
) -> None:
    """Build a multi-page landscape PDF with all business-drawer content.

    Every section checks ``visible_sections`` so the user can toggle blocks
    on/off from the dashboard's metric-filter chips.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = Canvas(str(output_path), pagesize=landscape(letter))
    _draw_bg(c)
    cur = _PageCursor(c)

    vs = visible_sections or {}

    # Page 1: Hero + KPIs + demand chart
    _section_hero(cur, match, detail)
    _section_stats(cur, detail)

    if vs.get("capacity", True):
        _section_capacity_gauge(cur, detail)

    if vs.get("revenue", True):
        _section_revenue(cur, detail)

    if vs.get("demand", True):
        _section_demand_chart(cur, detail, match)

    # Page 2: Audience + Recommendation + Peers + Comparison
    if vs.get("audience", True) or vs.get("recommendations", True):
        cur.new_page()
        _section_audience_and_recommendation(cur, detail, match)

    if vs.get("competition", True):
        _section_peers_and_comparison(cur, detail, comparison)

    if vs.get("demand", True):
        _section_day_comparison(cur, detail)

    # Page 3: Playbook + Watchouts + Methodology
    if vs.get("recommendations", True):
        cur.new_page()
        _section_playbook(cur, detail)

    _section_watchouts(cur, detail)

    if vs.get("report_sections", True):
        _section_methodology(cur, detail)

    _section_footer(cur, match, detail)

    c.save()
