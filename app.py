import os
import re
import json
import time
import base64
import textwrap
from pathlib import Path
from io import BytesIO

# ── PDF ──────────────────────────────────────────────────────────────
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.units import cm, mm

# ── Math rendering ───────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.mathtext as mathtext

# ── Flask ────────────────────────────────────────────────────────────
from flask import Flask, render_template, request, jsonify, send_file

# ── Gemini ───────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    genai = None
    GENAI_AVAILABLE = False

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# ═══════════════════════════════════════════════════════════════════════
# MATH IMAGE RENDERER
# Converts LaTeX inline math ($...$) or display math ($$...$$) to PNG
# and returns a ReportLab Image flowable.
# ═══════════════════════════════════════════════════════════════════════

_MATH_CACHE = {}

def math_to_image(latex_expr: str, fontsize: float = 13, dpi: int = 220,
                  inline: bool = True) -> Image | None:
    """Render a LaTeX math expression to a ReportLab Image flowable."""
    cache_key = (latex_expr, fontsize, dpi, inline)
    if cache_key in _MATH_CACHE:
        data = _MATH_CACHE[cache_key]
        buf = BytesIO(data)
        img = Image(buf)
        img.drawWidth  = img.imageWidth  * (72 / dpi)
        img.drawHeight = img.imageHeight * (72 / dpi)
        return img

    expr = latex_expr.strip()
    if not expr.startswith("$"):
        expr = f"${expr}$"

    try:
        fig = plt.figure(figsize=(0.01, 0.01))
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        ax.patch.set_alpha(0)

        renderer = mathtext.MathTextParser("path")
        t = ax.text(
            0.0, 0.5, expr,
            fontsize=fontsize,
            color="black",
            va="center",
            ha="left",
            transform=ax.transAxes,
        )
        fig.canvas.draw()
        bbox = t.get_window_extent(renderer=fig.canvas.get_renderer())
        w_in = max(bbox.width  / fig.dpi + 0.05, 0.3)
        h_in = max(bbox.height / fig.dpi + 0.05, 0.2)
        fig.set_size_inches(w_in, h_in)
        fig.canvas.draw()

        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                    transparent=True, pad_inches=0.01)
        plt.close(fig)

        raw = buf.getvalue()
        _MATH_CACHE[cache_key] = raw
        buf.seek(0)
        img = Image(buf)
        img.drawWidth  = img.imageWidth  * (72 / dpi)
        img.drawHeight = img.imageHeight * (72 / dpi)
        return img

    except Exception:
        plt.close("all")
        return None


# ═══════════════════════════════════════════════════════════════════════
# FONT REGISTRATION
# ═══════════════════════════════════════════════════════════════════════

_fonts_registered = False

def register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    _base = os.path.dirname(os.path.abspath(__file__))
    font_path      = os.path.join(_base, "static", "fonts", "DejaVuSans.ttf")
    font_bold_path = os.path.join(_base, "static", "fonts", "DejaVuSans-Bold.ttf")
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    except Exception:
        pass
    try:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
    except Exception:
        pass
    _fonts_registered = True


def bold_font():
    register_fonts()
    try:
        pdfmetrics.getFont("DejaVu-Bold")
        return "DejaVu-Bold"
    except Exception:
        return "DejaVu"


def body_font():
    register_fonts()
    try:
        pdfmetrics.getFont("DejaVu")
        return "DejaVu"
    except Exception:
        return "Helvetica"


# ═══════════════════════════════════════════════════════════════════════
# LINE PARSER
# Splits a line into text segments and math segments.
# Returns a list of ReportLab elements (Paragraphs + Images).
# ═══════════════════════════════════════════════════════════════════════

# Matches $$...$$  or  $...$
_MATH_PATTERN = re.compile(r'(\$\$[^$]+\$\$|\$[^$\n]+\$)')

def _escape_xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def parse_math_line(line: str, style, math_fontsize: float = 12) -> list:
    """
    Parse a line that may contain $math$ or $$math$$.
    Returns a list of flowables: Paragraphs and Images, to be wrapped
    in a KeepTogether so they sit on the same visual line.
    """
    parts = _MATH_PATTERN.split(line)
    if len(parts) == 1:
        # No math — just a paragraph
        safe = _escape_xml(line)
        safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
        safe = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', safe)
        return [Paragraph(safe, style)]

    flowables = []
    text_buf  = ""

    def flush_text():
        nonlocal text_buf
        if text_buf.strip():
            safe = _escape_xml(text_buf)
            safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
            safe = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', safe)
            flowables.append(Paragraph(safe, style))
        text_buf = ""

    for part in parts:
        if _MATH_PATTERN.match(part):
            flush_text()
            # Strip delimiters
            expr = part.strip("$").strip()
            is_display = part.startswith("$$")
            fs = math_fontsize + 3 if is_display else math_fontsize
            img = math_to_image(expr, fontsize=fs, dpi=220)
            if img:
                flowables.append(img)
            else:
                # Fallback: monospace text
                safe = _escape_xml(part)
                flowables.append(Paragraph(f"<font name='Courier'>{safe}</font>", style))
        else:
            text_buf += part

    flush_text()
    return flowables


# ═══════════════════════════════════════════════════════════════════════
# SECTION / TABLE DETECTORS
# ═══════════════════════════════════════════════════════════════════════

def is_section_header(line: str) -> bool:
    s = line.strip()
    if re.match(r'^(SECTION|Section|PART|Part)\s+[A-Da-d](\s|[-:]|$)', s):
        return True
    return bool(re.match(
        r'^(General Instructions|Instructions|ANSWER KEY|Answer Key|'
        r'GENERAL INSTRUCTIONS|Note:|NOTE:)', s
    ))

def is_table_row(line: str) -> bool:
    return "|" in line and line.strip().startswith("|")

def is_divider_row(line: str) -> bool:
    return bool(re.match(r'^\|[\s\-:|]+\|', line.strip()))

def is_separator_line(line: str) -> bool:
    s = line.strip()
    return len(s) > 4 and all(c in "-=_" for c in s)


# ═══════════════════════════════════════════════════════════════════════
# PAGE CANVAS CALLBACKS (header/footer on every page)
# ═══════════════════════════════════════════════════════════════════════

class ExamPageCanvas:
    """Adds page number and branding footer to every page."""
    def __init__(self, canvas, doc):
        self.canvas = canvas
        self.doc    = doc

    def __call__(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(body_font(), 8)
        canvas.setFillColor(HexColor("#aaaaaa"))
        # Left: ExamCraft branding
        canvas.drawString(28, 16, "ExamCraft — AI Exam Paper Generator")
        # Right: page number
        canvas.drawRightString(A4[0] - 28, 16, f"Page {doc.page}")
        # Thin line above footer
        canvas.setStrokeColor(HexColor("#dddddd"))
        canvas.setLineWidth(0.5)
        canvas.line(28, 24, A4[0] - 28, 24)
        canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════
# STYLES BUILDER
# ═══════════════════════════════════════════════════════════════════════

ACCENT  = HexColor("#1a237e")
KEY_RED = HexColor("#b71c1c")

def build_styles():
    register_fonts()
    bf  = bold_font()
    bdf = body_font()

    styles = getSampleStyleSheet()

    def add(name, **kw):
        if name not in styles:
            styles.add(ParagraphStyle(name=name, **kw))

    add("ExamTitle",
        fontName=bf, fontSize=16, alignment=TA_CENTER,
        textColor=ACCENT, spaceAfter=3, leading=20)
    add("ExamSubtitle",
        fontName=bdf, fontSize=10.5, alignment=TA_CENTER,
        textColor=HexColor("#444444"), spaceAfter=4, leading=14)
    add("ExamMeta",
        fontName=bdf, fontSize=9.5, alignment=TA_CENTER,
        textColor=HexColor("#666666"), spaceAfter=10, leading=13)
    add("SectionHeader",
        fontName=bf, fontSize=11.5, textColor=ACCENT,
        spaceBefore=10, spaceAfter=5, leading=15,
        borderPad=4, backColor=HexColor("#e8eaf6"),
        borderColor=ACCENT, borderWidth=0)
    add("Instructions",
        fontName=bdf, fontSize=9.5, textColor=HexColor("#333333"),
        leading=14, spaceAfter=2, leftIndent=10)
    add("QNumber",
        fontName=bf, fontSize=10.5, textColor=HexColor("#000000"),
        leading=15, spaceAfter=1)
    add("QBody",
        fontName=bdf, fontSize=10.5, alignment=TA_JUSTIFY,
        leading=15, spaceAfter=3, leftIndent=18)
    add("QOption",
        fontName=bdf, fontSize=10, leading=14,
        spaceAfter=1, leftIndent=30)
    add("Marks",
        fontName=bf, fontSize=9.5, alignment=TA_RIGHT,
        textColor=HexColor("#555555"), leading=14)
    add("DiagramBox",
        fontName=bdf, fontSize=9.5, leading=13, spaceAfter=6,
        textColor=HexColor("#555555"),
        borderColor=HexColor("#aaaaaa"), borderWidth=1,
        borderPad=6, backColor=HexColor("#f5f5f5"))
    add("KeyTitle",
        fontName=bf, fontSize=14, alignment=TA_CENTER,
        textColor=KEY_RED, spaceAfter=8, leading=18)
    add("KeySectionHeader",
        fontName=bf, fontSize=11, textColor=KEY_RED,
        spaceBefore=8, spaceAfter=3, leading=15,
        backColor=HexColor("#fff8f8"), borderPad=3)
    add("KeyQNum",
        fontName=bf, fontSize=10, textColor=HexColor("#333333"),
        leading=14, spaceAfter=1)
    add("KeyBody",
        fontName=bdf, fontSize=10, leading=14, spaceAfter=2)
    add("KeyBodyIndent",
        fontName=bdf, fontSize=10, leading=14, spaceAfter=2,
        leftIndent=18, textColor=HexColor("#222222"))

    return styles


# ═══════════════════════════════════════════════════════════════════════
# MAIN PDF BUILDER
# ═══════════════════════════════════════════════════════════════════════

def create_exam_pdf(
    text: str,
    subject: str,
    chapter: str,
    board: str = "",
    answer_key: str = None,
    include_key: bool = False,
) -> bytes:

    buffer  = BytesIO()
    styles  = build_styles()
    bf      = bold_font()
    bdf     = body_font()
    PAGE_W  = A4[0] - 56  # usable width (28mm margins each side — wider)

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=28, leftMargin=28,
        topMargin=30, bottomMargin=28,
        title=f"{subject} - {chapter}" if chapter else subject,
    )

    elements = []

    # ── Header box ───────────────────────────────────────────────────
    # Two-column header: left = title/chapter, right = board/meta
    left_content  = [Paragraph(f"<b>{subject or 'Question Paper'}</b>", styles["ExamTitle"])]
    right_content = []
    if chapter:
        left_content.append(Paragraph(f"Chapter: {chapter}", styles["ExamSubtitle"]))
    if board:
        right_content.append(Paragraph(f"<b>{board}</b>", styles["ExamMeta"]))
    right_content.append(Paragraph("ExamCraft — AI Generated", styles["ExamMeta"]))

    left_cell  = [item for item in left_content]
    right_cell = [item for item in right_content]

    header_tbl = Table(
        [[left_cell, right_cell]],
        colWidths=[PAGE_W * 0.65, PAGE_W * 0.35]
    )
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#e8eaf6")),
        ("BOX",           (0, 0), (-1, -1), 1.5, ACCENT),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (1, 0), (1, -1),  "RIGHT"),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 12))

    # ── Parse body ───────────────────────────────────────────────────
    table_data: list = []
    in_table: bool   = False

    def flush_table():
        nonlocal table_data, in_table
        if not table_data:
            return
        max_cols = max(len(r) for r in table_data)
        rows     = [r + [""] * (max_cols - len(r)) for r in table_data]

        # First row = header
        col_w = PAGE_W / max(max_cols, 1)
        tbl   = Table(rows, colWidths=[col_w] * max_cols, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME",       (0, 0), (-1, -1), bdf),
            ("FONTSIZE",       (0, 0), (-1, -1), 9.5),
            ("BACKGROUND",     (0, 0), (-1,  0), HexColor("#e8eaf6")),
            ("TEXTCOLOR",      (0, 0), (-1,  0), ACCENT),
            ("FONTNAME",       (0, 0), (-1,  0), bf),
            ("FONTSIZE",       (0, 0), (-1,  0), 10),
            ("GRID",           (0, 0), (-1, -1), 0.5, HexColor("#9e9e9e")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor("#ffffff"), HexColor("#f3f3f3")]),
            ("TOPPADDING",     (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",  (0, 0), (-1, -1), 5),
            ("LEFTPADDING",    (0, 0), (-1, -1), 7),
            ("RIGHTPADDING",   (0, 0), (-1, -1), 7),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(Spacer(1, 4))
        elements.append(tbl)
        elements.append(Spacer(1, 8))
        table_data.clear()
        in_table = False

    for raw_line in text.split("\n"):
        raw = raw_line.rstrip()

        # Table row
        if is_table_row(raw):
            if is_divider_row(raw):
                continue
            cells = [c.strip() for c in raw.split("|") if c.strip()]
            if cells:
                # Parse math inside table cells
                parsed_cells = []
                for cell in cells:
                    if "$" in cell:
                        img = math_to_image(cell.strip("$").strip(), fontsize=10, dpi=200)
                        parsed_cells.append(img if img else cell)
                    else:
                        parsed_cells.append(Paragraph(_escape_xml(cell), styles["QBody"]))
                table_data.append(parsed_cells)
                in_table = True
            continue
        else:
            if in_table:
                flush_table()

        # Blank
        if not raw.strip():
            elements.append(Spacer(1, 4))
            continue

        # HR separator
        if is_separator_line(raw):
            elements.append(HRFlowable(
                width="100%", thickness=0.5,
                color=HexColor("#cccccc"), spaceBefore=3, spaceAfter=3))
            continue

        # Diagram placeholder
        if raw.strip().startswith("[DIAGRAM:") or raw.strip().lower().startswith("[draw"):
            label = raw.strip()
            elements.append(Paragraph(f"<i>{_escape_xml(label)}</i>", styles["DiagramBox"]))
            # Draw an empty box for student to draw in
            box = Table([["  " * 40]], colWidths=[PAGE_W])
            box.setStyle(TableStyle([
                ("BOX",           (0, 0), (-1, -1), 1, HexColor("#aaaaaa")),
                ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#fafafa")),
                ("TOPPADDING",    (0, 0), (-1, -1), 40),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 40),
            ]))
            elements.append(box)
            elements.append(Spacer(1, 6))
            continue

        # Section header
        if is_section_header(raw):
            s = raw.strip()
            elements.append(Spacer(1, 6))
            # Coloured section banner
            sec_tbl = Table(
                [[Paragraph(f"<b>{_escape_xml(s)}</b>", styles["SectionHeader"])]],
                colWidths=[PAGE_W]
            )
            sec_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#e8eaf6")),
                ("BOX",           (0, 0), (-1, -1), 1,   ACCENT),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            elements.append(sec_tbl)
            elements.append(Spacer(1, 5))
            continue

        # Math-aware line rendering
        line_elements = parse_math_line(raw, styles["QBody"], math_fontsize=12)
        if line_elements:
            if len(line_elements) == 1:
                elements.append(line_elements[0])
            else:
                elements.append(KeepTogether(line_elements))

    if in_table:
        flush_table()

    # ── Answer Key ───────────────────────────────────────────────────
    if include_key and answer_key and answer_key.strip():
        elements.append(PageBreak())

        # Key header banner
        key_hdr = Table(
            [[Paragraph("ANSWER KEY", styles["KeyTitle"])]],
            colWidths=[PAGE_W]
        )
        key_hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#fff0f0")),
            ("BOX",           (0, 0), (-1, -1), 2, KEY_RED),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(key_hdr)
        elements.append(Spacer(1, 10))

        for raw_line in answer_key.split("\n"):
            raw    = raw_line.rstrip()
            stripped = raw.strip()

            if not stripped:
                elements.append(Spacer(1, 3))
                continue

            # Section header in key
            if re.match(r'^(Section|SECTION|Part|PART)\s+[A-D]:?', stripped):
                sec = Table(
                    [[Paragraph(f"<b>{_escape_xml(stripped)}</b>", styles["KeySectionHeader"])]],
                    colWidths=[PAGE_W]
                )
                sec.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), HexColor("#fff8f8")),
                    ("BOX",           (0, 0), (-1, -1), 0.8, KEY_RED),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
                    ("TOPPADDING",    (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                elements.append(Spacer(1, 4))
                elements.append(sec)
                elements.append(Spacer(1, 4))
                continue

            # Detect question number line
            is_qline = bool(re.match(r'^Q?\d+[\.\)]', stripped))
            is_indent = stripped.startswith(("Ans", "Answer", "Sol", "a)", "b)", "c)", "d)", "->", "="))

            style = (styles["KeyBodyIndent"] if is_indent
                     else styles["KeyQNum"] if is_qline
                     else styles["KeyBody"])

            line_els = parse_math_line(raw, style, math_fontsize=11)
            for el in line_els:
                elements.append(el)

    # ── Build ─────────────────────────────────────────────────────────
    page_cb = ExamPageCanvas(None, None)
    doc.build(elements, onFirstPage=page_cb, onLaterPages=page_cb)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════
# GEMINI — model discovery + call
# ═══════════════════════════════════════════════════════════════════════

_discovered_models = []

def discover_models():
    global _discovered_models
    if _discovered_models:
        return _discovered_models
    if not (GEMINI_KEY and GENAI_AVAILABLE):
        return []
    try:
        genai.configure(api_key=GEMINI_KEY)
        models = []
        for m in genai.list_models():
            if "generateContent" in (m.supported_generation_methods or []):
                name = m.name.replace("models/", "")
                models.append(name)
        preferred = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        ordered   = [p for p in preferred if any(p in n for n in models)]
        rest      = [n for n in models if not any(p in n for p in preferred)]
        _discovered_models = ordered + rest
        return _discovered_models
    except Exception:
        return ["gemini-1.5-flash", "gemini-pro"]


def call_gemini(prompt: str) -> tuple:
    if not (GEMINI_KEY and GENAI_AVAILABLE):
        return None, "Gemini not configured."
    models_to_try = discover_models()
    if not models_to_try:
        return None, "No Gemini models discovered."
    last_error = ""
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                model = genai.GenerativeModel(
                    model_name,
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 8192,
                        "top_p": 0.9,
                    },
                )
                response = model.generate_content(prompt)
                if response and hasattr(response, "text") and response.text.strip():
                    return response.text.strip(), None
                last_error = f"{model_name}: empty response"
                break
            except Exception as e:
                err_str = str(e)
                last_error = f"{model_name} (attempt {attempt+1}): {err_str}"
                if "429" in err_str or "404" in err_str or "quota" in err_str.lower():
                    time.sleep(0.3)
                    break
                if attempt == 0:
                    time.sleep(1.5)
                    continue
                break
    return None, last_error


# ═══════════════════════════════════════════════════════════════════════
# FALLBACK LOCAL PAPER
# ═══════════════════════════════════════════════════════════════════════

def build_local_paper(cls, subject, chapter, marks, difficulty):
    half = int(int(marks) * 0.5)
    return f"""{subject or "General"} - Model Question Paper
School: ________________________    Date: __________
Class: {cls}    Subject: {subject or "N/A"}    Board: Standard
Total Marks: {marks}               Time Allowed: 3 Hours

Chapter / Topic: {chapter or "Full Syllabus"}
Difficulty: {difficulty}

General Instructions:
1. All questions are compulsory.
2. Read each question carefully before answering.
3. Marks for each question are shown in brackets.
4. Write answers neatly and in order.
5. Calculators are not permitted unless specified.
6. Draw diagrams wherever necessary.

SECTION A - Objective Questions [20 Marks]

1. Choose the correct answer:                              [1 Mark]
   (A) Option A   (B) Option B   (C) Option C   (D) Option D

2. Fill in the blank: The value of ________ is fundamental.  [1 Mark]

3. True or False: Statement about {chapter or "this topic"}.   [1 Mark]

SECTION B - Short Answer Questions [30 Marks]

4. Explain the main concept of {chapter or "this chapter"}.   [3 Marks]

5. State and explain an important theorem or principle.      [3 Marks]

SECTION C - Long Answer Questions [30 Marks]

6. Describe the important principles of {chapter or "this topic"}
   with proofs or derivations where applicable.             [5 Marks]

SECTION D - Case Study [20 Marks]

7. Read the following scenario and answer:
   (a) Identify the key concept demonstrated.               [5 Marks]
   (b) Explain the underlying principle involved.           [5 Marks]

ANSWER KEY

Section A:
1. (B)
2. [Expected answer]
3. True / False — [brief justification]

Section B:
4. Three key points with brief explanation each.
5. Statement + explanation of the principle.

Section C:
6. Introduction → Principle → Proof/Derivation → Conclusion.

Section D:
7. (a) Key concept identified and explained.
   (b) Principle stated with reasoning.
"""


# ═══════════════════════════════════════════════════════════════════════
# PROMPT BUILDER — asks AI to use LaTeX math notation
# ═══════════════════════════════════════════════════════════════════════

def build_prompt(class_name, subject, chapter, board, exam_type, difficulty, marks, suggestions):
    subj_lower = (subject or "").lower()
    is_stem = any(k in subj_lower for k in [
        "math", "maths", "physics", "chemistry",
        "science", "biology", "computer"
    ])

    math_block = ""
    if is_stem:
        math_block = """
==================================================
MATH & SCIENCE NOTATION — MANDATORY
==================================================
Use LaTeX math notation wrapped in $ signs for ALL mathematical/scientific expressions.
This is critical — the PDF renderer supports LaTeX math perfectly.

Inline math  : $F = ma$,  $E = mc^2$,  $H_2O$,  $CO_2$
Display math : $$\\int_0^\\infty e^{-x^2}dx = \\frac{\\sqrt{\\pi}}{2}$$
Powers       : $x^2$, $a^{n+1}$, $10^{-19}$
Subscripts   : $H_2O$, $v_{max}$, $a_n$
Fractions    : $\\frac{a}{b}$, $\\frac{x+1}{x-1}$
Square root  : $\\sqrt{x}$, $\\sqrt[3]{8}$
Greek letters: $\\theta$, $\\alpha$, $\\beta$, $\\pi$, $\\lambda$, $\\mu$
Integrals    : $\\int_a^b f(x)dx$
Summation    : $\\sum_{i=1}^n i^2$
Vectors      : $\\vec{F}$, $|\\vec{v}|$
Chemical eq  : $2H_2 + O_2 \\rightarrow 2H_2O$
Degree symbol: $90^\\circ$
Approximately: $\\approx$
==================================================
DO NOT use plain text for ANY mathematical expression.
Every number with a unit, every equation, every formula MUST be in $...$.
==================================================
"""

    extra = (
        f"\nSPECIAL INSTRUCTIONS:\n{suggestions}\n"
        if suggestions and suggestions.strip()
        else ""
    )

    return f"""You are a senior board examination authority creating an official exam paper.

==================================================
CRITICAL OUTPUT RULES
==================================================
1. Use LaTeX math notation ($...$) for all math/science expressions.
2. Output the exam body first, then "ANSWER KEY" on its own line, then the key.
3. Every question must show its mark value in brackets: [2 Marks]
4. Start directly with the Exam Header — no preamble.
5. For tables, use Markdown pipe table format: | Col1 | Col2 |
6. For diagram spots write: [DIAGRAM: brief description]
{extra}
==================================================
EXAM DETAILS
==================================================
Class        : {class_name or "Not specified"}
Subject      : {subject or "Not specified"}
Chapter/Topic: {chapter or "Full Syllabus"}
Board / Exam : {board}
Difficulty   : {difficulty}
Total Marks  : {marks}
==================================================
REQUIRED STRUCTURE
==================================================

[EXAM HEADER]
  School / Institution: ______________________________
  Subject: {subject}   Class: {class_name}   Board: {board}
  Total Marks: {marks}       Time Allowed: 3 Hours
  Date: ______________

[GENERAL INSTRUCTIONS]
  (6 numbered instructions)

SECTION A - Objective Questions  (~20% = {int(int(marks)*0.2)} marks)
  MCQ, fill-in-blank, true/false — 1 mark each, min 10 questions

SECTION B - Short Answer  (~30% = {int(int(marks)*0.3)} marks)
  2–3 marks each, min 6 questions

SECTION C - Long Answer  (~30% = {int(int(marks)*0.3)} marks)
  5 marks each with sub-parts, min 4 questions

SECTION D - Case Study  (~20% = {int(int(marks)*0.2)} marks)
  One real-world scenario + 4 sub-questions

ANSWER KEY
  Section A: all MCQ answers
  Section B: key points per question
  Section C: step-by-step solutions
  Section D: detailed answers
{math_block}
Begin the paper now.
"""


# ═══════════════════════════════════════════════════════════════════════
# SPLIT PAPER / KEY
# ═══════════════════════════════════════════════════════════════════════

def split_key(text: str) -> tuple:
    patterns = [
        r'\nANSWER KEY\n',
        r'\n---\s*ANSWER KEY\s*---\n',
        r'(?i)\nANSWER KEY:?\s*\n',
    ]
    for pat in patterns:
        parts = re.split(pat, text, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


# ═══════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json(force=True) or {}

        class_name       = (data.get("class") or "").strip()
        subject          = (data.get("subject") or "").strip()
        chapter          = (data.get("chapter") or "").strip()
        marks            = (data.get("marks") or "100").strip()
        difficulty       = (data.get("difficulty") or "Medium").strip()
        state            = (data.get("state") or "").strip()
        competitive_exam = (data.get("competitiveExam") or "").strip()
        exam_type        = (data.get("examType") or "").strip()
        suggestions      = (data.get("suggestions") or "").strip()

        if exam_type == "state-board" and state:
            board = f"{state} State Board"
        elif exam_type == "competitive" and competitive_exam:
            board = competitive_exam
        else:
            board = (data.get("board") or "Standard Curriculum").strip()

        if not subject and (data.get("scope") == "all" or data.get("all_chapters")):
            subject = "Mixed Subjects"

        use_fallback = str(data.get("use_fallback", "false")).lower() in ("true", "1", "yes")

        prompt = data.get("prompt") or build_prompt(
            class_name, subject, chapter, board,
            exam_type, difficulty, marks, suggestions
        )

        generated_text = None
        api_error      = None

        if not use_fallback:
            generated_text, api_error = call_gemini(prompt)

        if not generated_text:
            if use_fallback or not GEMINI_KEY:
                generated_text = build_local_paper(
                    class_name, subject, chapter, marks, difficulty
                )
                use_fallback = True
            else:
                return jsonify({
                    "success":   False,
                    "error":     "AI generation failed.",
                    "api_error": api_error,
                    "suggestion": "Send use_fallback=true to get a template paper.",
                }), 502

        paper, key = split_key(generated_text)

        return jsonify({
            "success":       True,
            "paper":         paper,
            "answer_key":    key,
            "api_error":     api_error,
            "used_fallback": use_fallback,
            "board":         board,
            "subject":       subject,
            "chapter":       chapter,
        })

    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    try:
        data        = request.get_json(force=True) or {}
        paper_text  = data.get("paper", "")
        answer_key  = data.get("answer_key", "")
        subject     = (data.get("subject") or "Question Paper").strip()
        chapter     = (data.get("chapter") or "").strip()
        board       = (data.get("board") or "").strip()
        include_key = str(data.get("includeKey", "false")).lower() == "true"

        if not paper_text.strip():
            return jsonify({"success": False, "error": "No paper text provided"}), 400

        pdf_bytes = create_exam_pdf(
            paper_text, subject, chapter,
            board=board,
            answer_key=answer_key,
            include_key=include_key,
        )
        parts    = [p for p in [board, subject, chapter] if p]
        filename = ("_".join(parts) + ".pdf").replace(" ", "_").replace("/", "-")
        return send_file(
            BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()}), 500


@app.route("/health")
def health():
    configured = bool(GEMINI_KEY and GENAI_AVAILABLE)
    models     = discover_models() if configured else []
    return jsonify({"status": "ok", "gemini": "configured" if configured else "not configured",
                    "models_available": models})


@app.route("/chapters")
def chapters():
    try:
        data_path = Path(os.path.dirname(os.path.abspath(__file__))) / "data" / "curriculum.json"
        if not data_path.exists():
            return jsonify({"success": False, "error": "curriculum.json not found"})
        with open(data_path, encoding="utf-8") as f:
            curriculum = json.load(f)
        cls = request.args.get("class") or request.args.get("cls")
        if cls and cls in curriculum:
            return jsonify({"success": True, "data": curriculum[cls]})
        return jsonify({"success": True, "data": curriculum})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)