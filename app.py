import os
import re
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from io import BytesIO

# ── PDF ──────────────────────────────────────────────────────────────
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.units import mm

# ── Flask ────────────────────────────────────────────────────────────
from flask import Flask, render_template, request, jsonify, send_file

# ── Gemini ───────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    genai = None
    GENAI_AVAILABLE = False

app = Flask(__name__, template_folder="templates",
            static_folder="static", static_url_path="/static")

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# ═══════════════════════════════════════════════════════════════════════
# LOAD EXAM PATTERN DATA
# ═══════════════════════════════════════════════════════════════════════
_DATA_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "data"

def _load_json(name):
    p = _DATA_DIR / name
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}

_PATTERN_AP_TS    = _load_json("exam_patterns/ap_ts.json")
_PATTERN_COMP     = _load_json("exam_patterns/competitive.json")
_CURRICULUM       = _load_json("curriculum.json")

# ═══════════════════════════════════════════════════════════════════════
# FONT REGISTRATION
# ═══════════════════════════════════════════════════════════════════════
_fonts_registered = False

def register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    _base = os.path.dirname(os.path.abspath(__file__))
    fdir  = os.path.join(_base, "static", "fonts")
    sys_d = "/usr/share/fonts/truetype/dejavu"

    def reg(name, filename):
        for d in [fdir, sys_d]:
            p = os.path.join(d, filename)
            if os.path.exists(p):
                try:
                    pdfmetrics.registerFont(TTFont(name, p))
                    return True
                except Exception:
                    pass
        return False

    reg("Reg",  "DejaVuSans.ttf")
    reg("Bold", "DejaVuSans-Bold.ttf")
    reg("Ital", "DejaVuSans-Oblique.ttf")
    _fonts_registered = True

def _f(variant="Reg"):
    register_fonts()
    fallback = {"Reg": "Helvetica", "Bold": "Helvetica-Bold", "Ital": "Helvetica-Oblique"}
    try:
        pdfmetrics.getFont(variant)
        return variant
    except Exception:
        return fallback.get(variant, "Helvetica")


# ═══════════════════════════════════════════════════════════════════════
# LATEX → REPORTLAB XML
# CRITICAL: NEVER use Unicode sub/superscript chars — use <sub>/<super>
# ═══════════════════════════════════════════════════════════════════════
_MATH_RE = re.compile(r'(\$\$[^$]+\$\$|\$[^$\n]+\$)')

_GREEK = {
    r'\alpha':'α', r'\beta':'β', r'\gamma':'γ', r'\delta':'δ',
    r'\epsilon':'ε', r'\varepsilon':'ε', r'\zeta':'ζ', r'\eta':'η',
    r'\theta':'θ', r'\iota':'ι', r'\kappa':'κ', r'\lambda':'λ',
    r'\mu':'μ', r'\nu':'ν', r'\xi':'ξ', r'\pi':'π', r'\rho':'ρ',
    r'\sigma':'σ', r'\tau':'τ', r'\upsilon':'υ', r'\phi':'φ',
    r'\varphi':'φ', r'\chi':'χ', r'\psi':'ψ', r'\omega':'ω',
    r'\Gamma':'Γ', r'\Delta':'Δ', r'\Theta':'Θ', r'\Lambda':'Λ',
    r'\Xi':'Ξ', r'\Pi':'Π', r'\Sigma':'Σ', r'\Upsilon':'Υ',
    r'\Phi':'Φ', r'\Psi':'Ψ', r'\Omega':'Ω',
}
_SYM = {
    r'\times':'×', r'\div':'÷', r'\pm':'±', r'\mp':'∓',
    r'\cdot':'·', r'\ldots':'…', r'\cdots':'⋯',
    r'\infty':'∞', r'\partial':'∂', r'\nabla':'∇',
    r'\in':'∈', r'\notin':'∉', r'\subset':'⊂', r'\supset':'⊃',
    r'\cup':'∪', r'\cap':'∩',
    r'\leq':'≤', r'\geq':'≥', r'\neq':'≠', r'\approx':'≈',
    r'\equiv':'≡', r'\sim':'~', r'\propto':'∝',
    r'\rightarrow':'→', r'\leftarrow':'←', r'\Rightarrow':'⇒',
    r'\Leftarrow':'⇐', r'\leftrightarrow':'↔',
    r'\uparrow':'↑', r'\downarrow':'↓',
    r'\forall':'∀', r'\exists':'∃', r'\neg':'¬',
    r'\angle':'∠', r'\perp':'⊥', r'\parallel':'∥',
    r'\triangle':'△', r'\degree':'°', r'\circ':'°',
    r'\therefore':'∴', r'\because':'∵',
    r'\int':'∫', r'\oint':'∮',
    r'\to':'→', r'\gets':'←',
    r'\%':'%', r'\$':'$',
}


def _extract_braced(s, pos):
    if pos >= len(s) or s[pos] != '{':
        return (s[pos], pos + 1) if pos < len(s) else ('', pos)
    depth, i = 0, pos
    while i < len(s):
        if   s[i] == '{': depth += 1
        elif s[i] == '}': depth -= 1
        if depth == 0:
            return s[pos+1:i], i+1
        i += 1
    return s[pos+1:], len(s)


def _latex_to_rl(expr: str) -> str:
    s = expr.strip().lstrip('$').rstrip('$').strip()
    s = re.sub(r'\\(?:text|mathrm|mathbf|mathit|boldsymbol)\{([^}]*)\}', r'\1', s)
    s = re.sub(r'\\(?:left|right)(?=[|(\[\]{}.])', '', s)
    for k in sorted(_GREEK, key=len, reverse=True):
        s = s.replace(k, _GREEK[k])
    for k in sorted(_SYM, key=len, reverse=True):
        s = s.replace(k, _SYM[k])

    result, i = '', 0
    while i < len(s):
        if s[i:i+5] == '\\frac':
            i += 5
            num, i = _extract_braced(s, i)
            den, i = _extract_braced(s, i)
            result += f'({_latex_to_rl(num)}/{_latex_to_rl(den)})'
            continue
        if s[i:i+5] == '\\sqrt':
            i += 5
            n_root = ''
            if i < len(s) and s[i] == '[':
                j = s.find(']', i); j = j if j != -1 else i
                n_root = s[i+1:j];  i = j + 1
            inner, i = _extract_braced(s, i)
            result += f'{n_root}√({_latex_to_rl(inner)})'
            continue
        if s[i] == '^':
            i += 1
            raw, i = _extract_braced(s, i)
            inner = _latex_to_rl(raw).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            result += f'<super>{inner}</super>'
            continue
        if s[i] == '_':
            i += 1
            raw, i = _extract_braced(s, i)
            inner = _latex_to_rl(raw).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            result += f'<sub>{inner}</sub>'
            continue
        decorated = False
        for cmd in (r'\overline', r'\widehat', r'\widetilde', r'\vec', r'\hat', r'\bar', r'\tilde'):
            if s[i:].startswith(cmd):
                i += len(cmd)
                inner, i = _extract_braced(s, i)
                result += _latex_to_rl(inner)
                decorated = True
                break
        if decorated:
            continue
        if s[i] == '\\':
            j = i + 1
            while j < len(s) and (s[j].isalpha() or s[j] == '*'):
                j += 1
            if j == i + 1 and j < len(s):
                j += 1
            i = j
            result += ' '
            continue
        c = s[i]
        if   c == '&': result += '&amp;'
        elif c == '<': result += '&lt;'
        elif c == '>': result += '&gt;'
        else:          result += c
        i += 1
    return re.sub(r'  +', ' ', result).strip()


def _process(text: str) -> str:
    text = re.sub(r'\\_', '_', text)
    text = re.sub(r'\\-',  '-', text)
    text = re.sub(r'\\%',  '%', text)

    def _repl(m):
        return _latex_to_rl(m.group(0))
    converted = _MATH_RE.sub(_repl, text)

    tag_re = re.compile(r'(</?(?:super|sub|b|i|font)[^>]*>)')
    parts  = tag_re.split(converted)
    safe   = []
    for p in parts:
        if tag_re.match(p):
            safe.append(p)
        else:
            p = p.replace('&', '&amp;')
            p = re.sub(r'&amp;(amp|lt|gt|quot|#\d+);', r'&\1;', p)
            p = re.sub(r'<', '&lt;', p)
            safe.append(p)

    out = ''.join(safe)
    out = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', out)
    out = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', out)
    return out


# ═══════════════════════════════════════════════════════════════════════
# COLOURS
# ═══════════════════════════════════════════════════════════════════════
# Monochrome palette — exam papers should look like exam papers, not websites
C_NAVY  = HexColor("#111111")   # was indigo — now near-black for headers
C_STEEL = HexColor("#111111")   # was blue   — question numbers, plain black
C_BODY  = HexColor("#1a1a1a")   # body text, unchanged
C_GREY  = HexColor("#444444")   # marks label, dark grey
C_LIGHT = HexColor("#f0f0f0")   # section banner background, light grey
C_RULE  = HexColor("#888888")   # rules/borders, medium grey
C_MARK  = HexColor("#111111")   # mark labels, plain black
C_KRED  = HexColor("#111111")   # answer key headings, black
C_KFILL = HexColor("#f7f7f7")   # answer key background, very light grey
C_STEP  = HexColor("#1a1a1a")   # key steps, body colour


# ═══════════════════════════════════════════════════════════════════════
# STYLES
# ═══════════════════════════════════════════════════════════════════════
def _styles():
    register_fonts()
    R, B, I = _f("Reg"), _f("Bold"), _f("Ital")
    base = getSampleStyleSheet()

    def S(name, **kw):
        if name not in base:
            base.add(ParagraphStyle(name=name, **kw))
        else:
            for k, v in kw.items():
                setattr(base[name], k, v)

    S("PTitle",    fontName=B, fontSize=15, textColor=black,
      alignment=TA_CENTER, leading=22, spaceAfter=0, spaceBefore=0)
    S("PMeta",     fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_LEFT, leading=13, spaceAfter=0)
    S("PMetaR",    fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_RIGHT, leading=13, spaceAfter=0)
    S("PMetaC",    fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_CENTER, leading=13, spaceAfter=0)
    S("SecBanner", fontName=B, fontSize=10.5, textColor=black,
      leading=15, spaceAfter=0, spaceBefore=0)
    S("InstrHead", fontName=B, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, spaceBefore=4)
    S("Instr",     fontName=R, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, leftIndent=18, firstLineIndent=-18)
    S("Q",         fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=15, spaceBefore=5, spaceAfter=1,
      leftIndent=22, firstLineIndent=-22)
    S("QCont",     fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=15, spaceBefore=1, spaceAfter=1, leftIndent=22)
    S("QSub",      fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=15, spaceBefore=2, spaceAfter=1,
      leftIndent=36, firstLineIndent=-14)
    S("Opt",       fontName=R, fontSize=10, textColor=C_BODY,
      leading=14, spaceAfter=0, leftIndent=0)
    S("KTitle",    fontName=B, fontSize=13, textColor=black,
      alignment=TA_CENTER, leading=18, spaceAfter=6, spaceBefore=0)
    S("KSec",      fontName=B, fontSize=10.5, textColor=black,
      leading=14, spaceAfter=2, spaceBefore=6)
    S("KQ",        fontName=B, fontSize=10.5, textColor=black,
      leading=14, spaceAfter=2, spaceBefore=4, leftIndent=24, firstLineIndent=-24)
    S("KStep",     fontName=R, fontSize=10, textColor=C_STEP,
      leading=15, spaceAfter=1, leftIndent=24)
    S("KSub",      fontName=R, fontSize=10, textColor=C_BODY,
      leading=15, spaceAfter=1, leftIndent=36, firstLineIndent=-12)
    S("KMath",     fontName=I, fontSize=10, textColor=C_BODY,
      leading=15, spaceAfter=1, leftIndent=32)
    S("DiagLabel", fontName=I, fontSize=9, textColor=C_GREY,
      leading=12, spaceAfter=2, spaceBefore=2)
    return base


# ═══════════════════════════════════════════════════════════════════════
# PAGE CANVAS
# ═══════════════════════════════════════════════════════════════════════
class ExamCanvas:
    def __call__(self, canvas, doc):
        W = A4[0]
        LM, RM = doc.leftMargin, W - doc.rightMargin
        canvas.saveState()
        canvas.setStrokeColor(HexColor("#111111"))
        canvas.setLineWidth(0.6)
        canvas.line(LM, A4[1] - 12*mm, RM, A4[1] - 12*mm)
        canvas.setStrokeColor(HexColor("#888888"))
        canvas.setLineWidth(0.4)
        canvas.line(LM, 20, RM, 20)
        canvas.setFont(_f("Ital"), 7.5)
        canvas.setFillColor(C_GREY)
        if doc.page == 1:
            canvas.drawString(LM, 10,
                "ExamCraft  ·  Created by Laxman Nimmagadda"
                "  (if the paper is hard, I am not guilty)")
        canvas.drawRightString(RM, 10, f"Page {doc.page}")
        canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════
def _sec_banner(text, st, pw):
    p = Paragraph(f'<b>{text}</b>', st["SecBanner"])
    t = Table([[p]], colWidths=[pw])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), HexColor("#f0f0f0")),
        ("LINEBELOW",     (0,0),(-1,-1), 0.8, HexColor("#111111")),
        ("LINETOP",       (0,0),(-1,-1), 0.8, HexColor("#111111")),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
    ]))
    return t


def _opts_table(opts, st, pw):
    rows = []
    for k in range(0, len(opts), 2):
        L = opts[k]
        R = opts[k+1] if k+1 < len(opts) else ('', '')
        lp = Paragraph(f'<b>({L[0]})</b>  {L[1]}', st["Opt"])
        rp = Paragraph(f'<b>({R[0]})</b>  {R[1]}' if R[0] else '', st["Opt"])
        rows.append([lp, rp])
    col = pw / 2
    t = Table(rows, colWidths=[col, col])
    t.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 1),
        ("BOTTOMPADDING", (0,0),(-1,-1), 1),
        ("LEFTPADDING",   (0,0),(-1,-1), 20),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
    ]))
    return t


def _pipe_table(rows, st, pw):
    if not rows:
        return None
    mc = max(len(r) for r in rows)
    norm = [r + ['']*(mc-len(r)) for r in rows]
    R, B = _f("Reg"), _f("Bold")

    para_rows = []
    for ri, row in enumerate(norm):
        sty = st["KQ"] if ri == 0 else st["KStep"]
        para_rows.append([Paragraph(_process(c), sty) for c in row])

    cw = pw / mc
    t = Table(para_rows, colWidths=[cw]*mc, repeatRows=1)
    t.setStyle(TableStyle([
        ("FONTNAME",       (0,0),(-1,-1), R),
        ("FONTSIZE",       (0,0),(-1,-1), 9.5),
        ("BACKGROUND",     (0,0),(-1,0),  HexColor("#e8e8e8")),
        ("TEXTCOLOR",      (0,0),(-1,0),  black),
        ("FONTNAME",       (0,0),(-1,0),  B),
        ("GRID",           (0,0),(-1,-1), 0.5, HexColor("#aaaaaa")),
        ("ROWBACKGROUNDS", (0,1),(-1,-1), [white, HexColor("#f8f8f8")]),
        ("TOPPADDING",     (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",  (0,0),(-1,-1), 4),
        ("LEFTPADDING",    (0,0),(-1,-1), 7),
        ("RIGHTPADDING",   (0,0),(-1,-1), 7),
        ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
    ]))
    return t


# ═══════════════════════════════════════════════════════════════════════
# LINE-TYPE DETECTORS
# ═══════════════════════════════════════════════════════════════════════
def _is_sec_hdr(s):
    s = s.strip()
    if re.match(r'^(SECTION|Section|PART|Part)\s+[A-Da-d](\s|[-:]|$)', s):
        return True
    return bool(re.match(r'^(GENERAL INSTRUCTIONS|General Instructions'
                         r'|Instructions|Note:|NOTE:)\s*$', s))

def _is_table_row(s):
    return '|' in s and s.strip().startswith('|')

def _is_divider(s):
    return bool(re.match(r'^\|[\s\-:|]+\|', s.strip()))

def _is_hrule(s):
    s = s.strip()
    return len(s) > 3 and all(c in '-=_' for c in s)

_HDR_SKIP = re.compile(
    r'^(School|Subject|Class|Board|Total\s*Marks|Time\s*Allowed|Date)\s*[:/]',
    re.I)

# ── Figure junk-line filter ───────────────────────────────────────────
# AI sometimes outputs stray figure-description lines that are NOT
# proper [DIAGRAM:…] markers. These patterns match lines that look like
# leaked figure metadata and should be silently dropped from the PDF.
_FIG_JUNK = re.compile(
    r'^('
    r'Figure\s*:'                               # "Figure: Triangle ABC with..."
    r'|Triangle\s+[A-Z]{2,4}$'                 # "Triangle ABC"
    r'|Trapezium\s+[A-Z]{2,4}$'                # "Trapezium ABCD"
    r'|Right[\s-]?angled?\s+(Triangle|Iso)'     # "Right-angled Triangle", "Right-angled Isosceles..."
    r'|Right\s+Angle\s+Triangle$'              # "Right Angle Triangle"
    r'|Altitude(\s+from\s+\w+(\s+to\s+\w+)?)?$'  # "Altitude" / "Altitude from A to BC"
    r'|Angle\s+[A-Z]\s*=?\s*\d+°?$'            # "Angle A = 60°"
    r'|Angle\s+[A-Z]\s+\d+°?$'
    r'|∠[A-Z]\s*=\s*\d+°?$'                   # "∠A = 60°"
    r'|[A-Z]+\s+is\s+(altitude|median|midpoint|perpendicular)\s+to\s+[A-Z]+'
    r'|Side\s+[A-Z]{2}$'                       # "Side AB"
    r'|Parallel\s+[A-Z]{2}$'                   # "Parallel DE"
    r'|Diagonals?\s+[A-Z]{2}\s+and\s+[A-Z]{2}' # "Diagonals AC and BD intersect at O"
    r'|[A-Z]{2}\s+Parallel\s+to\s+[A-Z]{2}$'  # "DE Parallel to BC"
    r'|[A-Z]+\s+on\s+[A-Z]{2}$'               # "D on AB"
    r'|[A-Z]+\s+Parallel\s+to\s+[A-Z]+$'
    r'|Right\s+(angles?|angle\s+at\s+vertex)'
    r'|Perpendicular$'
    r'|Distance\s+from\s+[A-Z]\s+to\s+[A-Z]+'
    r'|(?:\d+°?\s*){3,}$'                      # "60° 60° 60°" lines of angles
    r'|(?:140"|140\s*"?\s*){2,}'               # "140" 140" 140"" repeated
    r'|θ\s*=\s*\d+°?\s*$'                      # "θ = 60°"
    r'|α\s*=\s*\d+°?\s*$'
    r'|[A-Z]M\s*is\s+altitude'
    r'|(?:Angle\s+[A-Z]\s*\n?){2,}'           # multiple "Angle X" lines
    r')',
    re.IGNORECASE
)


# ═══════════════════════════════════════════════════════════════════════
# MAIN PDF BUILDER
# ═══════════════════════════════════════════════════════════════════════
def create_exam_pdf(text, subject, chapter, board="",
                   answer_key=None, include_key=False, diagrams=None) -> bytes:

    register_fonts()
    st = _styles()

    LM = BM = 20 * mm
    RM = 20 * mm
    TM = 16 * mm
    PW = A4[0] - LM - RM

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=LM, rightMargin=RM,
                            topMargin=TM, bottomMargin=BM,
                            title=f"{subject}{' – '+chapter if chapter else ''}")
    elems = []

    def _pull(pat, default=""):
        m = re.search(pat, text, re.I | re.M)
        return m.group(1).strip() if m else default

    h_marks = _pull(r'Total\s*Marks\s*[:/]\s*(\d+)', "100")
    h_time  = _pull(r'Time\s*(?:Allowed|:)\s*([^\n]+)', "3 Hours")
    h_class = _pull(r'Class\s*[:/]?\s*(\d+\w*)', "")
    h_board = board or _pull(r'Board\s*[:/]\s*([^\n]+)', "")

    disp_title   = subject or "Question Paper"
    disp_chapter = chapter or ""

    title_str = disp_title
    if disp_chapter:
        title_str += f"  —  {disp_chapter}"
    tbl_title = Table(
        [[Paragraph(title_str, st["PTitle"])]],
        colWidths=[PW])
    tbl_title.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), white),
        ("LINEBELOW",     (0,0),(-1,-1), 1.2, HexColor("#111111")),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
    ]))

    left_meta  = "  |  ".join(x for x in [h_board, f"Class {h_class}" if h_class else ""] if x)
    right_meta = f"Total Marks: {h_marks}"
    tbl_meta = Table(
        [[Paragraph(left_meta,  st["PMeta"]),
          Paragraph(right_meta, st["PMetaR"])]],
        colWidths=[PW*0.55, PW*0.45])
    tbl_meta.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), white),
        ("LINEBELOW",     (0,0),(-1,-1), 0.5, HexColor("#888888")),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))

    elems += [tbl_title, tbl_meta, Spacer(1, 6)]

    tbl_rows    = []
    in_table    = False
    pending_opts = []
    in_instr    = False

    def flush_table():
        nonlocal tbl_rows, in_table
        if tbl_rows:
            t = _pipe_table(tbl_rows, st, PW)
            if t:
                elems.append(Spacer(1, 3))
                elems.append(t)
                elems.append(Spacer(1, 5))
        tbl_rows, in_table = [], False

    def flush_opts():
        nonlocal pending_opts
        if pending_opts:
            elems.append(_opts_table(pending_opts, st, PW))
            elems.append(Spacer(1, 3))
        pending_opts = []

    lines = text.split('\n')
    i_line = 0

    def _is_general_instr(s):
        return bool(re.match(r'^(GENERAL INSTRUCTIONS|General Instructions'
                             r'|Instructions)\s*$', s.strip()))

    def _is_instr_line(s):
        return bool(re.match(r'^\d+\.\s+', s.strip())) and in_instr

    while i_line < len(lines):
        raw  = lines[i_line].rstrip()
        line = re.sub(r'\\_', '_', re.sub(r'\\-', '-', raw))
        s    = line.strip()
        i_line += 1

        if _is_table_row(line):
            if _is_divider(line):
                continue
            flush_opts()
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                tbl_rows.append(cells)
                in_table = True
            continue
        elif in_table:
            flush_table()

        if not s:
            flush_opts()
            elems.append(Spacer(1, 4))
            continue

        if _HDR_SKIP.match(s):
            continue

        # Drop stray figure-description lines that the AI emits alongside [DIAGRAM:] markers
        if _FIG_JUNK.match(s):
            continue

        # "Figure: ..." lines emitted outside [DIAGRAM:] tags — convert to italic label
        fig_m = re.match(r'^Figure\s*:\s*(.+)', s, re.I)
        if fig_m:
            flush_opts()
            desc = fig_m.group(1).strip()
            # Remove trailing angle noise like "Angle A = 60° Angle B = 60°..."
            desc = re.sub(r'(?:\.\s*)?(?:Angle\s+[A-Z]\s*=?\s*\d+°?\s*){1,}$', '', desc).strip()
            desc = re.sub(r'(?:\s*\d+°){2,}', '', desc).strip()
            if desc:
                elems.append(Paragraph(f'<i>Figure: {desc}</i>', st["DiagLabel"]))
            continue

        if _is_hrule(line):
            flush_opts()
            elems.append(HRFlowable(width="100%", thickness=0.4,
                                    color=C_RULE, spaceBefore=3, spaceAfter=3))
            continue

        if s.startswith('[DIAGRAM:') or s.lower().startswith('[draw'):
            flush_opts()
            label   = s.strip('[]')
            desc    = re.sub(r'^DIAGRAM:\s*', '', label, flags=re.I).strip()
            # Sanitise desc — drop any angle/measurement noise that crept in
            desc = re.sub(r'(?:\s*\d+°){2,}', '', desc).strip()
            elems.append(Paragraph(f'<i>Figure: {desc}</i>', st["DiagLabel"]))

            drawing = None
            if diagrams:
                # Exact match first
                if desc in diagrams and diagrams[desc]:
                    drawing = svg_to_best_image(diagrams[desc], width_pt=PW * 0.65)
                if drawing is None:
                    # Fuzzy match: find diagram key with most word overlap
                    desc_words = set(re.findall(r'\w+', desc.lower()))
                    best_key, best_score = None, 0
                    for d_key, d_svg in diagrams.items():
                        if not d_svg:
                            continue
                        key_words = set(re.findall(r'\w+', d_key.lower()))
                        overlap = len(desc_words & key_words)
                        if overlap > best_score:
                            best_score, best_key = overlap, d_key
                    if best_key and best_score >= 2:
                        drawing = svg_to_best_image(diagrams[best_key], width_pt=PW * 0.65)

            if drawing is not None:
                elems.append(Spacer(1, 3))
                # Centre the drawing
                outer_d = Table([[drawing]], colWidths=[PW])
                outer_d.setStyle(TableStyle([
                    ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
                    ('TOPPADDING',    (0,0),(-1,-1), 2),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 2),
                ]))
                elems.append(outer_d)
            else:
                # Clean placeholder box — no stray text inside, just a neat space
                blank_height_mm = 38  # ~38 mm reserved for hand-drawn diagram
                ph_label = Paragraph(
                    f'<i>[ Draw diagram here: {desc} ]</i>',
                    st["DiagLabel"])
                box = Table(
                    [[ph_label],
                     [Spacer(1, blank_height_mm * mm - 20)]],
                    colWidths=[PW * 0.72])
                box.setStyle(TableStyle([
                    ('BOX',           (0,0),(-1,-1), 0.6, C_RULE),
                    ('BACKGROUND',    (0,0),(-1,-1), HexColor('#f9f9f9')),
                    ('TOPPADDING',    (0,0),(-1,-1), 6),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 6),
                    ('LEFTPADDING',   (0,0),(-1,-1), 10),
                    ('RIGHTPADDING',  (0,0),(-1,-1), 10),
                    ('VALIGN',        (0,0),(-1,-1), 'TOP'),
                ]))
                outer = Table([[box]], colWidths=[PW])
                outer.setStyle(TableStyle([
                    ('ALIGN',         (0,0),(-1,-1), 'CENTER'),
                    ('TOPPADDING',    (0,0),(-1,-1), 2),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 4),
                ]))
                elems.append(outer)
            elems.append(Spacer(1, 5))
            continue

        if _is_general_instr(s):
            flush_opts()
            in_instr = True
            # Skip instructions header — don't render to save space
            continue

        if _is_sec_hdr(line) and not _is_general_instr(s):
            flush_opts()
            in_instr = False
            elems.append(Spacer(1, 4))
            elems.append(_sec_banner(s, st, PW))
            elems.append(Spacer(1, 3))
            continue

        if _is_instr_line(s):
            # Skip instructions to save paper space
            continue

        opt_m = re.match(r'^\s*[\(\[]\s*([a-dA-D])\s*[\)\]\.]?\s+(.+)', s)
        if opt_m and not re.match(r'^(Q\.?\s*)?\d+[\.)\]]\s', s):
            in_instr = False
            letter = opt_m.group(1).lower()
            val    = _process(opt_m.group(2))
            pending_opts.append((letter, val))
            if len(pending_opts) >= 4:
                flush_opts()
            continue

        multi = re.findall(
            r'[\(\[]([a-dA-D])[\)\]\.]?\s+([^(\[]+?)(?=\s*[\(\[][a-dA-D][\)\]\.]|$)',
            s)
        if len(multi) >= 2 and not re.match(r'^(Q\.?\s*)?\d+[\.)\]]\s', s):
            flush_opts()
            in_instr = False
            opts = [(l.lower(), _process(v.strip())) for l, v in multi]
            elems.append(_opts_table(opts, st, PW))
            elems.append(Spacer(1, 3))
            continue

        q_m = re.match(r'^(Q\.?\s*)?(\d+)[\.)\]]\s+(.+)', s)
        if q_m and not in_instr:
            flush_opts()
            in_instr = False
            qnum  = q_m.group(2)
            qbody = q_m.group(3)
            mk_m = re.search(r'\[\s*(\d+)\s*[Mm]arks?\s*\]\s*$', qbody)
            mark_tag = ''
            if mk_m:
                mark_tag = f'[{mk_m.group(1)}M]'
                qbody    = qbody[:mk_m.start()].strip()
            body_rl = _process(qbody)
            mark_rl = (f'  <font color="{C_GREY.hexval()}" size="9">'
                       f'{mark_tag}</font>') if mark_tag else ''
            xml = (f'<font color="{C_STEEL.hexval()}"><b>{qnum}.</b></font>'
                   f'  {body_rl}{mark_rl}')
            elems.append(Paragraph(xml, st["Q"]))
            continue

        sub_m = re.match(r'^\s*[\(\[]\s*([a-z])\s*[\)\]]\s+(.+)', s)
        if sub_m and not in_instr:
            flush_opts()
            sl    = sub_m.group(1)
            sbod  = sub_m.group(2)
            mk_m2 = re.search(r'(\[\s*\d+\s*[Mm]arks?\s*\])\s*$', sbod)
            mark2 = ''
            if mk_m2:
                mark2 = (f'  <font color="{C_MARK.hexval()}" size="9.5">'
                         f'<b>{mk_m2.group(1)}</b></font>')
                sbod  = sbod[:mk_m2.start()].strip()
            elems.append(Paragraph(
                f'<b>({sl})</b>  {_process(sbod)}{mark2}',
                st["QSub"]))
            continue

        flush_opts()
        elems.append(Paragraph(_process(s), st["QCont"]))

    flush_opts()
    if in_table:
        flush_table()

    # ─── Answer key ───────────────────────────────────────────────────
    if include_key and answer_key and answer_key.strip():
        elems.append(PageBreak())
        kt = Table([[Paragraph("ANSWER KEY", st["KTitle"])]], colWidths=[PW])
        kt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_KFILL),
            ("LINEBELOW",     (0,0),(-1,-1), 2.5, C_KRED),
            ("LINETOP",       (0,0),(-1,-1), 2.5, C_KRED),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ]))
        elems += [kt, Spacer(1, 10)]

        key_lines = answer_key.split('\n')
        ki = 0
        while ki < len(key_lines):
            raw_k  = key_lines[ki].rstrip()
            line_k = re.sub(r'\\_', '_', re.sub(r'\\-', '-', raw_k))
            sk     = line_k.strip()
            ki    += 1

            if not sk:
                elems.append(Spacer(1, 3))
                continue

            if re.match(r'^(Section|SECTION|Part|PART)\s+[A-Da-d]\b', sk):
                ks = Table([[Paragraph(f'<b>{sk.rstrip(":")}:</b>',
                                       st["KSec"])]], colWidths=[PW])
                ks.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0),(-1,-1), HexColor("#f0f0f0")),
                    ("LINEBELOW",     (0,0),(-1,-1), 0.8, HexColor("#111111")),
                    ("LEFTPADDING",   (0,0),(-1,-1), 10),
                    ("TOPPADDING",    (0,0),(-1,-1), 4),
                    ("BOTTOMPADDING", (0,0),(-1,-1), 4),
                ]))
                elems += [Spacer(1, 6), ks, Spacer(1, 4)]
                continue

            q_km = re.match(r'^(Q\.?\s*)?(\d+)[\.)\]]\s*(.*)', sk)
            if q_km:
                body_k = q_km.group(3).strip()
                mk_k = re.search(r'(\[\s*\d+\s*[Mm]arks?\s*\])\s*$', body_k)
                mk_str = ''
                if mk_k:
                    mk_str  = (f'  <font color="{C_MARK.hexval()}" size="9">'
                               f'<b>{mk_k.group(1)}</b></font>')
                    body_k  = body_k[:mk_k.start()].strip()
                body_rl = _process(body_k) if body_k else ''
                elems.append(Paragraph(
                    f'<b>{q_km.group(2)}.</b>  {body_rl}{mk_str}',
                    st["KQ"]))
                continue

            sub_km = re.match(r'^\(?([a-z])\)\.?\s+(.+)', sk)
            if sub_km:
                elems.append(Paragraph(
                    f'<b>({sub_km.group(1)})</b>  {_process(sub_km.group(2))}',
                    st["KSub"]))
                continue

            if raw_k.startswith('   ') or raw_k.startswith('\t'):
                elems.append(Paragraph(_process(sk), st["KStep"]))
                continue

            if (sk.startswith('$') or
                    re.match(r'^[A-Za-z]\s*[=<>≤≥]', sk) or
                    re.match(r'^\s*(∴|Therefore|Hence|Thus)\b', sk, re.I)):
                elems.append(Paragraph(_process(sk), st["KStep"]))
                continue

            elems.append(Paragraph(_process(sk), st["KStep"]))

    doc.build(elems, onFirstPage=ExamCanvas(), onLaterPages=ExamCanvas())
    pdf = buf.getvalue()
    buf.close()
    return pdf


# ═══════════════════════════════════════════════════════════════════════
# GEMINI
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
                models.append(m.name.replace("models/", ""))
        preferred = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro", "gemini-2.0-flash-exp"]
        ordered   = [p for p in preferred if any(p in n for n in models)]
        rest      = [n for n in models if not any(p in n for p in preferred)]
        _discovered_models = ordered + rest
        return _discovered_models
    except Exception:
        return ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro", "gemini-2.0-flash-exp"]


def call_gemini(prompt):
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
                    generation_config={"temperature": 0.7, "max_output_tokens": 8192, "top_p": 0.9})
                response = model.generate_content(prompt)
                if response and hasattr(response, "text") and response.text.strip():
                    return response.text.strip(), None
                last_error = f"{model_name}: empty response"
                break
            except Exception as e:
                err = str(e)
                last_error = f"{model_name} ({attempt+1}): {err}"
                if "429" in err or "404" in err or "quota" in err.lower():
                    time.sleep(0.3); break
                if attempt == 0:
                    time.sleep(1.5); continue
                break
    return None, last_error


# ═══════════════════════════════════════════════════════════════════════
# FALLBACK PAPER (used when Gemini is unavailable)
# ═══════════════════════════════════════════════════════════════════════
def build_local_paper(cls, subject, chapter, marks, difficulty):
    return f"""{subject or "Science"} — Model Question Paper
Subject: {subject or "Science"}   Class: {cls}
Total Marks: {marks}   Time Allowed: 3 Hours 15 Minutes

GENERAL INSTRUCTIONS
1. Answer all the questions under Part-A on the question paper itself and attach it to the answer booklet at the end.
2. Read the instructions carefully and answer only the required number of questions in each section.
3. Figures to the right indicate marks allotted.
4. Draw neat, labelled diagrams wherever necessary.

PART A — OBJECTIVE (20 Marks)
(Answer in the question paper itself. Submit after 30 minutes.)

Section-I — Multiple Choice Questions [1 Mark each]
1. Which of the following best describes Newton's First Law of Motion? [1 Mark]
   (A) Force equals mass times acceleration
   (B) An object at rest stays at rest unless acted upon by an external force
   (C) Every action has an equal and opposite reaction
   (D) Acceleration is inversely proportional to mass  (   )

2. The SI unit of electric charge is __________. [1 Mark]
   (A) Ampere   (B) Coulomb   (C) Volt   (D) Ohm  (   )

Section-II — Fill in the Blanks [1 Mark each]
11. The chemical formula of water is __________.
12. The process by which plants make food using sunlight is called __________.

Section-III — Match the Following [1 Mark each]
| Group A | Group B |
|---|---|
| Newton | Laws of Motion |
| Ohm | Resistance |
| Faraday | Electromagnetic Induction |
| Darwin | Theory of Evolution |
| Mendel | Laws of Heredity |

PART B — WRITTEN (80 Marks)

Section-IV — Very Short Answer Questions [2 Marks each]
(Answer ALL questions in not more than 5 lines each.)

1. State Newton's Second Law of Motion. [2 Marks]
2. What is an electric circuit? Name its two essential components. [2 Marks]

Section-V — Short Answer Questions [4 Marks each]
(Answer any FOUR of the following six questions.)

11. Explain the process of photosynthesis with a labelled diagram. [4 Marks]
12. State and explain Ohm's Law. Give one example. [4 Marks]

Section-VI — Long Answer / Essay Questions [6 Marks each]
(Answer any FOUR of the following six questions.)

21. (i) Derive the equations of motion $v = u + at$ and $s = ut + \\frac{{1}}{{2}}at^2$. [6 Marks]
OR
    (ii) A car starts from rest and accelerates uniformly at $2\\ m/s^2$. Find the velocity after 5 seconds and the distance covered. [6 Marks]

Section-VII — Application / Problem Solving [10 Marks each]
(Answer any TWO of the following three questions.)

31. A wire of resistance $R = 6\\ \\Omega$ is connected to a $12\\ V$ battery.
    (a) Find the current flowing through the circuit. [3 Marks]
    (b) If three such resistors are connected in parallel, find the equivalent resistance and total current. [4 Marks]
    (c) State two differences between series and parallel circuits. [3 Marks]

ANSWER KEY

Section-I:
1. (B)   2. (B)

Section-II:
11. H₂O   12. Photosynthesis

Section-III:
Newton → Laws of Motion, Ohm → Resistance, Faraday → Electromagnetic Induction, Darwin → Theory of Evolution, Mendel → Laws of Heredity

Section-IV:
1. Newton's Second Law: The rate of change of momentum of a body is directly proportional to the applied force and takes place in the direction of the force. F = ma.
2. An electric circuit is a closed path through which electric current flows. Essential components: (1) a source of EMF (battery/cell), (2) conducting wires.

Section-V:
11. Photosynthesis: 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂. Occurs in chloroplasts. Requires sunlight, chlorophyll, CO₂, and water. [DIAGRAM: Chloroplast showing grana and stroma]

Section-VI:
21. (i) Starting from F = ma → a = (v-u)/t → v = u + at. Substituting: s = ut + ½at². 
(ii) Given: u=0, a=2 m/s², t=5s. v = 0 + 2×5 = 10 m/s. s = 0 + ½×2×25 = 25 m.

Section-VII:
31. (a) I = V/R = 12/6 = 2 A.
    (b) 1/R_eq = 1/6 + 1/6 + 1/6 = 3/6, R_eq = 2 Ω. I_total = 12/2 = 6 A.
    (c) Series: same current, voltages add. Parallel: same voltage, currents add.
"""


# ═══════════════════════════════════════════════════════════════════════
# MATH NOTATION RULES (injected into every STEM prompt)
# ═══════════════════════════════════════════════════════════════════════

def _math_rules():
    return (
        "\nMATH NOTATION — every mathematical expression MUST be in $...$:\n"
        "  Powers     : $x^{2}$  $a^{3}$  $10^{-3}$    ← never x2\n"
        "  Subscripts : $H_{2}O$  $v_{0}$  $CO_{2}$     ← never H2O\n"
        "  Fractions  : $\\frac{a}{b}$  $\\frac{mv^{2}}{r}$\n"
        "  Roots      : $\\sqrt{2}$  $\\sqrt{b^{2}-4ac}$\n"
        "  Greek      : $\\theta$  $\\alpha$  $\\pi$  $\\lambda$  $\\omega$\n"
        "  Trig       : $\\sin\\theta$  $\\cos 60^{\\circ}$  $\\tan\\alpha$\n"
        "  Units      : write cm, kg, m/s, N, Ω as plain text outside $\n"
        "  Blanks     : use __________ (underscores, NOT LaTeX)\n"
    )


# ─── helpers ──────────────────────────────────────────────────────────
def _class_int(cls_str):
    m = re.search(r'\d+', str(cls_str or "10"))
    return int(m.group()) if m else 10


# ═══════════════════════════════════════════════════════════════════════
# MASTER ROUTER
# ═══════════════════════════════════════════════════════════════════════
def build_prompt(class_name, subject, chapter, board, exam_type,
                 difficulty, marks, suggestions):
    m       = max(10, int(marks) if str(marks).isdigit() else 100)
    cls_str = class_name or "10"
    cls_n   = _class_int(cls_str)
    chap    = chapter or "as per syllabus"
    extra   = f"TEACHER NOTES: {suggestions.strip()}\n" if (suggestions or "").strip() else ""
    board_l = (board or "").lower()
    subj_l  = (subject or "").lower()
    is_stem = any(k in subj_l for k in [
        "math","maths","science","physics","chemistry","biology",
        "algebra","geometry","trigonometry","statistics"
    ])
    math_note = _math_rules() if is_stem else ""

    comp_map = {"ntse":"NTSE","nso":"NSO","imo":"IMO","ijso":"IJSO"}
    for key, val in comp_map.items():
        if key in board_l:
            return _prompt_competitive(val, subject, chap, cls_str,
                                       m, difficulty, extra, math_note)
    return _prompt_ap_ts(subject, chap, board, cls_str, cls_n,
                         m, difficulty, extra, math_note)


# ═══════════════════════════════════════════════════════════════════════
# AP / TS STATE BOARD ROUTER
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ap_ts(subject, chap, board, cls_str, cls_n,
                  m, difficulty, extra, math_note):
    pat = _PATTERN_AP_TS
    if cls_n <= 8:
        return _prompt_ap_ts_6_8(subject, chap, board, cls_str,
                                  m, difficulty, extra, math_note, pat)
    return _prompt_ap_ts_9_10(subject, chap, board, cls_str,
                               m, difficulty, extra, math_note, pat)


# ═══════════════════════════════════════════════════════════════════════
# AP/TS CLASS 9–10  SSC  (100-mark official pattern)
# Technique: Role + CoT self-verification + few-shot anchors + strict counts
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ap_ts_9_10(subject, chap, board, cls_str,
                        m, difficulty, extra, math_note, pat):
    subj_l = (subject or "").lower()

    if "math" in subj_l:
        subject_guidance = """\
SUBJECT — MATHEMATICS:
• Every numerical: write formula first, substitute values with units, show EACH arithmetic step, box the final answer.
• Theorems/proofs: state what is Given, what To Prove, then write numbered Steps each with a Reason.
• Constructions (Section VII): list steps one by one — "Step 1: Draw AB = 5 cm", "Step 2: ..."
• Wrong options in MCQ must correspond to common student errors (sign slip, formula confusion, wrong formula chosen)."""

    elif any(k in subj_l for k in ["physics","chemistry","science","biology"]):
        subject_guidance = """\
SUBJECT — SCIENCE:
• Physics/Chemistry numericals: Given → Formula → Substitution → Working → Answer with unit.
• Chemical equations must be balanced with state symbols: (s) (l) (g) (aq).
• Biology questions needing diagrams: write [DIAGRAM: description with every label] on its own line.
• Section VII: application/experiment questions. Show full working. Don't skip steps."""

    elif any(k in subj_l for k in ["social","history","geography","civics","economics"]):
        subject_guidance = """\
SUBJECT — SOCIAL STUDIES:
• VSQ: one crisp factual sentence per mark. No waffle.
• SA: 4–5 distinct points with sub-headings where helpful.
• LA: structured essay — intro, 5–6 points, conclusion.
• Section VII must include one map question: ask students to mark exactly 5 items on an outline map of India."""

    elif "english" in subj_l:
        subject_guidance = """\
SUBJECT — ENGLISH (no Part A objective section):
Section A — Reading (20 marks): unseen passage ~250 words + 5 comprehension questions.
Section B — Writing (20 marks): formal letter OR essay (150-200 words) OR notice.
Section C — Grammar (20 marks): gap-fill, sentence transformation, editing.
Section D — Literature (40 marks): questions from prescribed Class texts (prose + poetry).
Do NOT generate any Part A objective section for English."""

    else:
        subject_guidance = f"""\
SUBJECT — {subject.upper()}:
• Questions must follow the official board textbook for Class {cls_str}.
• Progress from simple recall (Part A) to deep application (Section VII)."""

    diff_mix = {
        "Easy":   "Bloom's: 50% Remember/Understand, 30% Apply, 20% Analyse",
        "Medium": "Bloom's: 25% Remember/Understand, 40% Apply, 25% Analyse, 10% Evaluate",
        "Hard":   "Bloom's: 10% Remember, 20% Understand, 35% Apply, 25% Analyse, 10% Evaluate",
    }.get(difficulty, "Bloom's: 25% Remember/Understand, 40% Apply, 25% Analyse, 10% Evaluate")

    return f"""You are a senior question-paper setter for {board}, Class {cls_str}, with 15 years of experience.
Your papers are used as official model papers by the board. Quality, accuracy, and correct marks are non-negotiable.
{extra}
━━━ PAPER SPECIFICATION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Subject : {subject}
Topic   : {chap}
Class   : {cls_str}   Board: {board}
Marks   : 100 total   Difficulty: {difficulty}
{diff_mix}
━━━ MANDATORY SECTION STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━
Before writing any question, think through the section counts:

PART A — OBJECTIVE (20 marks, given separately, collected after 30 min)
  Section I   — 10 MCQ       × 1 mark  = 10 marks
  Section II  — 5  Fill-blank × 1 mark =  5 marks
  Section III — 1  Match (5 pairs) × 1 = 5 marks
                                Subtotal = 20 marks ✓

PART B — WRITTEN (80 marks, continued in answer booklet)
  Section IV  — 10 VSQ        ALL compulsory  × 2 marks =  20 marks
  Section V   — 6 SA given,   attempt any 4   × 4 marks =  16 marks
  Section VI  — 6 LA given,   attempt any 4   × 6 marks =  24 marks
                (each LA must have an OR alternative of equal marks)
  Section VII — 3 Application, attempt any 2  × 10 marks = 20 marks
                                        TOTAL = 100 marks ✓

{subject_guidance}
{math_note}
━━━ FEW-SHOT FORMAT EXAMPLES ━━━━━━━━━━━━━━━━━━━━━━━━━━
Study these EXACT formats. Your paper must match them precisely.

--- MCQ (Section I) ---
1. The tangent to a circle is always __________ to the radius at the point of contact. [1 Mark]
   (A) parallel   (B) perpendicular   (C) equal   (D) bisected   (   )

--- Fill-in-blank (Section II) ---
11. The sum of the first n natural numbers is given by the formula __________. [1 Mark]

--- Match (Section III) ---
16. Match the following: [5 Marks]
   Group A                        |  Group B
   --------------------------------|------------------
   Tangent from external point     |  $\\sqrt{{d^{{2}}-r^{{2}}}}$
   Area of sector                  |  $\\frac{{\\theta}}{{360}}\\pi r^{{2}}$
   Pythagoras theorem              |  $AB^{{2}}+BC^{{2}}=AC^{{2}}$
   Volume of cylinder              |  $\\pi r^{{2}}h$
   Curved surface area of cone     |  $\\pi r l$

--- VSQ (Section IV) ---
1. Find the length of the tangent drawn from a point 13 cm away from the centre of a circle of radius 5 cm. [2 Marks]

--- SA (Section V) ---
11. Prove that the tangents drawn from an external point to a circle are equal in length. [4 Marks]

--- LA with OR (Section VI) ---
17. (i) Prove Pythagoras theorem: In a right triangle, the square on the hypotenuse equals the sum of squares on the other two sides. Draw a neat diagram. [6 Marks]
    OR
   (ii) In a right triangle ABC with $\\angle B = 90^{{\\circ}}$, D is the midpoint of BC. Prove that $4AD^{{2}} = 4AB^{{2}} + BC^{{2}}$. [6 Marks]

--- Application (Section VII) ---
23. A solid is formed by placing a cone of radius 3.5 cm and slant height 7 cm on top of a cylinder of the same radius and height 10 cm. [10 Marks]
   (a) Find the curved surface area of the cone. [2 Marks]
   (b) Find the curved surface area of the cylinder. [3 Marks]
   (c) Find the total surface area of the solid. [2 Marks]
   (d) Find the volume of the solid. (Use $\\pi = \\frac{{22}}{{7}}$) [3 Marks]

━━━ STRICT RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. MARKS LABEL: Every question MUST end with its exact marks in square brackets — [1 Mark], [2 Marks], [4 Marks], [6 Marks], [10 Marks]. The number must match the section it belongs to. This is non-negotiable.
2. QUESTION NUMBERS: Section I: Q1–Q10. Section II: Q11–Q15. Section III: Q16 (single match question). Section IV: renumber Q1–Q10. Section V: Q11–Q16. Section VI: Q17–Q22. Section VII: Q23–Q25.
3. MCQ ANSWER BRACKET: Every MCQ must end with (   ) on the same line after option D.
4. SECTION HEADERS: Write exactly as shown — "Section I — Multiple Choice Questions [1 Mark each]" etc.
5. DIAGRAMS: When a question requires a diagram (geometry proof, biology structure, physics setup), put [DIAGRAM: full description with all required labels] on its own line immediately after the question. Do NOT write any additional figure description lines such as "Figure: ...", "Triangle ABC", angle labels, or other diagram metadata — these cause formatting errors. The [DIAGRAM:] tag is sufficient.
6. DO NOT write instructions, do not add a preamble, do not explain your choices. Output the paper directly.
7. SELF-CHECK: After writing all sections, mentally count: 10 MCQ ✓, 5 fill-blank ✓, 1 match ✓, 10 VSQ ✓, 6 SA ✓, 6 LA ✓, 3 App ✓. Then write the answer key.

━━━ ANSWER KEY FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
After all questions, write exactly: ANSWER KEY

Section I:   1.(  )  2.(  )  ... 10.(  )   — fill in the letter
Section II:  11. answer   12. answer  ... 15. answer
Section III: Match: 1→ , 2→ , 3→ , 4→ , 5→
Section IV:  For each VSQ, write the key answer in 2–4 lines.
Section V–VII: Show FULL WORKING — every step, not just the final answer.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEGIN THE PAPER. Write the header line first, then start Section I.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subject: {subject}   Class: {cls_str}   Total Marks: 100
Board: {board}

PART A — OBJECTIVE  (20 Marks)

Section I — Multiple Choice Questions  [1 Mark each]

"""


# ═══════════════════════════════════════════════════════════════════════
# AP/TS CLASSES 6–8  Summative Assessment (50 marks)
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ap_ts_6_8(subject, chap, board, cls_str,
                       m, difficulty, extra, math_note, pat):
    subj_l = (subject or "").lower()
    diff_mix = {
        "Easy":   "Simple recall and recognition. Age-appropriate language for Class {cls_str}.",
        "Medium": "Mix of recall, understanding, and short application.",
        "Hard":   "Conceptual questions requiring explanation, comparison, and analysis.",
    }.get(difficulty, "Mix of recall, understanding and short application.")

    if "math" in subj_l:
        subject_guidance = "Maths: Objective items test formulas/definitions. VSQ: short computation with working. SA: multi-step word problem — show formula → substitution → steps → answer with unit. LA: longer proof or complex word problem."
    elif "science" in subj_l:
        subject_guidance = "Science: Objective tests definitions. VSQ: label/define/name. SA: explain with diagram or short experiment. LA: detailed explanation with fully labelled diagram."
    else:
        subject_guidance = f"{subject}: Questions follow the board textbook. Simple to complex progression."

    return f"""You are a {board} Class {cls_str} examiner setting a Summative Assessment paper.
{extra}
Subject: {subject}  |  Topic: {chap}  |  Class: {cls_str}  |  Total Marks: 50
Difficulty: {difficulty} — {diff_mix}

━━━ MANDATORY STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Section A — Objective  (10 marks):  5 MCQ (Q1–5) + 3 Fill-blank (Q6–8) + 1 Match 2-pair (Q9) = 10 marks
Section B — VSQ        (20 marks): 10 questions (Q1–10) × 2 marks = 20 marks  [ALL compulsory]
Section C — SA         (10 marks):  4 questions (Q11–14) given, attempt any 2 × 5 marks = 10 marks
Section D — LA         (10 marks):  2 questions (Q15–16) given, attempt any 1 × 10 marks = 10 marks
TOTAL = 50 marks ✓

{subject_guidance}
{math_note}
━━━ FORMAT (follow exactly) ━━━━━━━━━━━━━━━━━━━━━━━━━━━
MCQ: 1. [question] [1 Mark]
     (A) opt   (B) opt   (C) opt   (D) opt   (   )
Fill-blank: 6. [complete sentence with __________ for the blank] [1 Mark]
Match: 9. Match Group A with Group B: [2 Marks]  (pipe table, 2 data rows)
VSQ: 1. [question] [2 Marks]
SA:  11. [question] [5 Marks]
LA:  15. [question] [10 Marks]

MARKS LABEL: Every question must end with [X Mark] or [X Marks] — matching section values.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BEGIN — write header then Section A directly:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subject: {subject}   Class: {cls_str}   Total Marks: 50
Board: {board}

Section A — Objective  (10 Marks)

"""


# ═══════════════════════════════════════════════════════════════════════
# COMPETITIVE EXAM ROUTER
# ═══════════════════════════════════════════════════════════════════════
def _prompt_competitive(exam, subject, chap, cls_str,
                        m, difficulty, extra, math_note):
    comp = _PATTERN_COMP.get("exams", {}).get(exam, {})
    exam_full = comp.get("full_name", exam)
    dispatch = {"NTSE": _prompt_ntse, "NSO": _prompt_nso,
                "IMO": _prompt_imo, "IJSO": _prompt_ijso}
    fn = dispatch.get(exam, _prompt_generic_comp)
    return fn(comp, exam_full, subject, chap, cls_str,
              m, difficulty, extra, math_note)


# ═══════════════════════════════════════════════════════════════════════
# NTSE — 100-mark MAT or SAT
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ntse(comp, exam_full, subject, chap, cls_str,
                 m, difficulty, extra, math_note):
    subj_l = (subject or "").lower()
    is_mat = any(k in subj_l for k in ["mat","mental","reasoning","ability"])

    if is_mat:
        return f"""You are an experienced NTSE MAT question setter. Generate a complete, ready-to-use practice paper.

EXAM: {exam_full} — Mental Ability Test (MAT)
Class: {cls_str}   Total: 100 Questions × 1 mark = 100 marks   Time: 2 Hours   No negative marking
Difficulty: {difficulty}
{extra}
━━━ QUESTION TYPE DISTRIBUTION (total must equal 100) ━━━
Q1–12    Verbal Analogy                    12 questions
Q13–22   Series (Number / Letter)          10 questions
Q23–32   Non-Verbal Analogy (describe)     10 questions
Q33–40   Coding–Decoding                    8 questions
Q41–46   Blood Relations                    6 questions
Q47–52   Direction & Distance               6 questions
Q53–58   Ranking & Ordering                 6 questions
Q59–64   Clock & Calendar                   6 questions
Q65–70   Venn Diagrams                      6 questions
Q71–76   Mirror / Water Image (text only)   6 questions
Q77–82   Classification / Odd-One-Out       6 questions
Q83–88   Pattern Completion (text only)     6 questions
Q89–94   Mathematical Operations            6 questions
Q95–100  Mixed Reasoning                    6 questions
TOTAL = 100 ✓

━━━ QUALITY RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Every question is 100% self-contained — no reference to figures not described in text.
• All 4 options are plausible. Wrong options must represent specific reasoning errors.
• Increase difficulty within each type (Q1 easier than Q12 within Verbal Analogy, etc.).
• For visual-based types (mirror image, pattern): describe the figure and relationships clearly in words.

FORMAT (every question):
Q[n]. [full question text] [1 Mark]
(A) option   (B) option   (C) option   (D) option

ANSWER KEY after all 100 questions:
Q1.(B)  Q2.(A)  Q3.(D)  ... (10 per line)
Then for Q1–Q20: one-line explanation of the reasoning rule used.

BEGIN the paper now. Write the header then Q1 directly:

Exam: {exam_full} — MAT
Class: {cls_str}   Marks: 100   Time: 2 Hours   No Negative Marking

INSTRUCTIONS: Each question carries 1 mark. No negative marking.

Q1–Q12 — Verbal Analogy  [1 Mark each]

"""

    # SAT paper
    topic = chap if chap and chap != "as per syllabus" else "Class 10 full syllabus"
    return f"""You are an experienced NTSE SAT question setter. Generate a complete, ready-to-use practice paper.

EXAM: {exam_full} — Scholastic Aptitude Test (SAT)
Class: {cls_str}   Topic: {topic}   Total: 100 Q × 1 mark = 100 marks   Time: 2 Hours
Difficulty: {difficulty}   No negative marking at Stage 1
{extra}
━━━ MANDATORY SECTION DISTRIBUTION ━━━━━━━━━━━━━━━━━━━━━
SCIENCE    Q1–Q40   (40 questions)
  Physics     Q1–Q13   13 questions — Motion, Force, Light, Electricity, Magnetism, Sound
  Chemistry   Q14–Q26  13 questions — Matter, Atoms, Molecules, Reactions, Acids/Bases, Periodic Table
  Biology     Q27–Q40  14 questions — Cell, Life Processes, Reproduction, Heredity, Environment
SOCIAL SCI  Q41–Q80  (40 questions)
  History     Q41–Q53  13 questions — Revolution, Nationalism, Industrialisation, World Wars
  Geography   Q54–Q66  13 questions — Resources, Agriculture, Physical features, Climate
  Civics      Q67–Q73   7 questions — Constitution, Parliament, Rights, Federalism
  Economics   Q74–Q80   7 questions — Development, Poverty, Food Security, Globalisation
MATHEMATICS Q81–Q100 (20 questions)
  All Class 10 topics: Number, Algebra, Geometry, Trig, Mensuration, Stats, Probability
TOTAL = 100 ✓
{math_note}
━━━ QUALITY RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Use NCERT Class 10 terminology and facts exactly.
• 30% recall, 50% understanding/application, 20% multi-step analysis.
• Wrong options represent specific misconceptions or calculation errors.

FORMAT: Q[n]. [question] [1 Mark]
(A) option   (B) option   (C) option   (D) option

ANSWER KEY: List Q1.(B) Q2.(C) ... (10 per line). Then explain all Maths answers (Q81–Q100) step by step.

BEGIN the paper now:

Exam: {exam_full} — SAT
Class: {cls_str}   Topic: {topic}   Marks: 100   Time: 2 Hours   No Negative Marking

SCIENCE — Physics  (Q1–Q13)  [1 Mark each]

"""


# ═══════════════════════════════════════════════════════════════════════
# NSO — 50 questions, 60 marks, 1 hour
# ═══════════════════════════════════════════════════════════════════════
def _prompt_nso(comp, exam_full, subject, chap, cls_str,
                m, difficulty, extra, math_note):
    topic = chap if chap and chap != "as per syllabus" else f"Class {cls_str} Science"
    return f"""You are an expert NSO (Science Olympiad Foundation) question setter. Generate a complete practice paper.

EXAM: {exam_full}   Class: {cls_str}   Topic: {topic}   Difficulty: {difficulty}
Total: 50 questions | 60 marks | 1 hour | No negative marking
{extra}
━━━ MANDATORY STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Section 1 — Logical Reasoning   Q1–Q10   10 × 1 mark = 10 marks
Section 2 — Science             Q11–Q45  35 × 1 mark = 35 marks
Section 3 — Achiever's Section  Q46–Q50   5 × 3 marks = 15 marks
TOTAL = 60 marks ✓
{math_note}
━━━ SECTION RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 (Q1–10): Pure reasoning — analogy, series, coding, odd-one-out, direction. NO science content.
SECTION 2 (Q11–45): Strictly Class {cls_str} science syllabus on "{topic}".
  • 30% easy (definition/fact), 50% conceptual application, 20% slightly challenging.
  • Wrong options = plausible misconceptions, not obviously wrong distractors.
SECTION 3 (Q46–50): HOT questions — significantly harder, 3 marks each.
  • Multi-step inference, experimental scenarios, data interpretation.
  • A student who only knows the topic cannot solve these by recall alone.

FORMAT:
Q[n]. [question] [marks]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY: Q1.(B) Q2.(A) ... (10 per line). For Q46–50: explain why correct AND why the best wrong option is wrong.

BEGIN:

Exam: {exam_full}
Class: {cls_str}   Topic: {topic}   Total Marks: 60   Time: 1 Hour

Section 1 — Logical Reasoning  [Q1–Q10 | 1 Mark each]

"""


# ═══════════════════════════════════════════════════════════════════════
# IMO — 50 questions, 60 marks, 1 hour
# ═══════════════════════════════════════════════════════════════════════
def _prompt_imo(comp, exam_full, subject, chap, cls_str,
                m, difficulty, extra, math_note):
    topic = chap if chap and chap != "as per syllabus" else f"Class {cls_str} Mathematics"
    return f"""You are an expert IMO (Science Olympiad Foundation) question setter. Generate a complete practice paper.

EXAM: {exam_full}   Class: {cls_str}   Topic: {topic}   Difficulty: {difficulty}
Total: 50 questions | 60 marks | 1 hour | No negative marking
{extra}
━━━ MANDATORY STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Section 1 — Logical Reasoning      Q1–Q10   10 × 1 mark = 10 marks
Section 2 — Mathematical Reasoning Q11–Q35  25 × 1 mark = 25 marks
Section 3 — Everyday Mathematics   Q36–Q45  10 × 1 mark = 10 marks
Section 4 — Achiever's Section     Q46–Q50   5 × 3 marks = 15 marks
TOTAL = 60 marks ✓
{math_note}
━━━ SECTION RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SEC 1 (Q1–10): Number analogies, letter series, Venn diagrams, ranking. NO direct maths computation.
SEC 2 (Q11–35): Class {cls_str} maths on "{topic}". 30% formula application, 50% two-step, 20% multi-step. Wrong options = arithmetic/sign/formula errors.
SEC 3 (Q36–45): Real-life word problems. Contexts: shopping, measurement, speed-distance-time, profit-loss, percentage, area. One numeric answer per question.
SEC 4 (Q46–50): 3 marks each. Require 3+ reasoning steps. Combinatorics, geometric deduction, number theory, or multi-concept integration.

FORMAT:
Q[n]. [question] [marks]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY: Q1.(B) Q2.(A) ... (10 per line). For Q46–50: full step-by-step working.

BEGIN:

Exam: {exam_full}
Class: {cls_str}   Topic: {topic}   Total Marks: 60   Time: 1 Hour

Section 1 — Logical Reasoning  [Q1–Q10 | 1 Mark each]

"""


# ═══════════════════════════════════════════════════════════════════════
# IJSO / NSEJS — 80 MCQ, +3/−1, 2 hours
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ijso(comp, exam_full, subject, chap, cls_str,
                 m, difficulty, extra, math_note):
    topic = chap if chap and chap != "as per syllabus" else "Integrated Physics, Chemistry, Biology — Class 9-10 level"
    return f"""You are a senior question setter at IAPT for NSEJS (National Standard Examination in Junior Science). Generate a complete Stage 1 practice paper.

EXAM: {exam_full} (NSEJS Stage 1)   Class: {cls_str}   Difficulty: {difficulty}
Topic focus: {topic}
Total: 80 questions | Marking: +3 correct / −1 wrong / 0 unattempted | Time: 2 Hours
{extra}
━━━ MANDATORY STRUCTURE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHYSICS    Q1–Q27    27 questions   [+3/−1 each]
CHEMISTRY  Q28–Q54   27 questions   [+3/−1 each]
BIOLOGY    Q55–Q80   26 questions   [+3/−1 each]
TOTAL = 80 ✓
{math_note}
━━━ QUALITY STANDARDS (prestigious national olympiad) ━━
LEVEL: Conceptual Class 9–10. Every question requires genuine understanding. Pure recall is insufficient.
PHYSICS (Q1–27): Motion equations, Newton's laws, optics (lenses/mirrors), electricity (Ohm, circuits, power), magnetism. Include 5+ numericals requiring 2+ steps. At least 3 graph/data-reading questions.
CHEMISTRY (Q28–54): Stoichiometry, mole concept, reaction types, acid-base indicators, periodic trends, carbon compounds. Include 3+ calculation questions. Balanced equations required.
BIOLOGY (Q55–80): Cell organelles, nutrition/respiration/transport/excretion mechanisms, reproductive systems, heredity ratios, ecology. Include 4+ questions based on experimental observation ("If... then what is observed?").
DISTRACTORS: Each wrong option must represent a specific, named misconception. No obviously wrong options.

FORMAT:
Q[n]. [full question] [+3/−1]
(A) option   (B) option   (C) option   (D) option

ANSWER KEY:
Q1.(B) Q2.(C) ... (10 per line, all 80)
Then for EVERY question: [correct letter] — one sentence: why correct + why best distractor is wrong.

BEGIN:

Exam: {exam_full} — NSEJS Stage 1 Practice
Class: {cls_str}   Topic: {topic}   Marking: +3/−1/0   Time: 2 Hours

PHYSICS  (Q1–Q27)  [+3/−1 each]

"""


# ═══════════════════════════════════════════════════════════════════════
# GENERIC COMPETITIVE FALLBACK
# ═══════════════════════════════════════════════════════════════════════
def _prompt_generic_comp(exam, subject, chap, cls_str,
                          m, difficulty, extra, math_note):
    n_q   = max(25, m // 4)
    topic = chap if chap and chap != "as per syllabus" else f"Class {cls_str} {subject}"
    return f"""Generate a {exam} practice paper — {n_q} MCQ questions on {subject}, Class {cls_str}.
Topic: {topic}   Difficulty: {difficulty}   Total marks: {n_q}
{extra}{math_note}
• 4 options per question (A)(B)(C)(D). Exactly one correct. Plausible distractors.
• Questions numbered Q1–Q{n_q}. Each ends with [1 Mark].
• Difficulty increases from Q1 to Q{n_q}.

FORMAT: Q[n]. [question] [1 Mark]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY after all questions: Q1.(B) Q2.(A) ... + one-sentence explanation per answer.

BEGIN:

Exam: {exam} Practice Paper
Subject: {subject}   Class: {cls_str}   Topic: {topic}   Marks: {n_q}

"""



# SPLIT PAPER / KEY
# ═══════════════════════════════════════════════════════════════════════
def split_key(text):
    for pat in [r'\nANSWER KEY\n', r'\n---\s*ANSWER KEY\s*---\n',
                r'(?i)\nANSWER KEY:?\s*\n']:
        parts = re.split(pat, text, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return text.strip(), ""


# ═══════════════════════════════════════════════════════════════════════
# AI DIAGRAM GENERATION (SVG via Gemini)
# ═══════════════════════════════════════════════════════════════════════

# Subject-specific diagram prompt templates
# ═══════════════════════════════════════════════════════════════════════
# HIGH-QUALITY DIAGRAM ENGINE
# Pipeline: Gemini SVG → wkhtmltoimage PNG @ 300dpi → embed in PDF
# Falls back to pure ReportLab SVG renderer if wkhtmltoimage unavailable
# ═══════════════════════════════════════════════════════════════════════
import subprocess, tempfile, os
from io import BytesIO

# ── Check wkhtmltoimage availability once at startup ──────────────────
def _has_wkhtmltoimage():
    try:
        r = subprocess.run(['which', 'wkhtmltoimage'], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False

_WKHTML_AVAILABLE = _has_wkhtmltoimage()


# ── Subject → diagram type hints ─────────────────────────────────────
_DIAG_CONTEXT = {
    # Geometry
    "tangent":      "circle geometry: external point P, two tangent lines PA and PB touching the circle at A and B, centre O, radius OA perpendicular to PA, all lengths and angles labelled",
    "secant":       "circle with a secant line intersecting at two points and a tangent from an external point, all lengths labelled",
    "circle":       "circle with centre O, radius, chord, tangent line, and relevant angles clearly labelled",
    "triangle":     "triangle with labelled vertices A B C, sides a b c, angles, altitude or median as required",
    "geometry":     "clean geometric figure with all vertices, sides, angles and relevant construction marks labelled",
    "coordinate":   "coordinate plane with clearly marked x-axis and y-axis, origin O, labelled points, plotted line or curve",
    "construction": "step-by-step geometric construction showing compass arcs (dashed), straight lines, and all labelled points",
    "pythagoras":   "right-angled triangle with the right angle marked by a small square, sides labelled a, b, and hypotenuse c",
    "similar":      "two similar triangles with corresponding sides and angles marked with tick marks and arcs",
    "mensuration":  "3D solid (cylinder/cone/sphere/frustum) drawn in perspective with all dimensions r, h, l labelled",
    # Physics
    "circuit":      "electric circuit schematic using standard symbols: battery (long/short lines), resistor (rectangle), bulb (circle-X), switch, ammeter (A in circle), voltmeter (V in circle), connecting wires",
    "ray":          "optics ray diagram: incident ray, normal (dashed), reflected or refracted ray, angles of incidence and reflection/refraction labelled with θ, lens or mirror surface",
    "lens":         "convex or concave lens diagram showing principal axis, focal points F and 2F, object arrow, image arrow, three standard rays",
    "mirror":       "concave or convex mirror diagram with principal axis, centre of curvature C, focal point F, object, image, and ray paths",
    "motion":       "velocity-time or distance-time graph with clearly labelled axes, values on axes, and the plotted line or curve",
    "force":        "free body diagram showing an object (rectangle or dot) with force arrows labelled: weight W downward, normal N upward, friction f horizontal, applied force F",
    "magnet":       "bar magnet with field lines curving from N pole to S pole, arrowheads showing direction",
    "refraction":   "glass slab or prism with incident ray, refracted ray inside the medium, emergent ray, normals (dashed) and angles i, r labelled",
    # Biology
    "cell":         "animal or plant cell (oval/rectangle outline) with organelles inside: nucleus (double circle), mitochondria, ribosomes, cell wall (plant only), vacuole, chloroplast (plant only), each labelled with leader lines",
    "heart":        "human heart cross-section showing 4 chambers: left atrium (LA), right atrium (RA), left ventricle (LV), right ventricle (RV), aorta, pulmonary artery/vein, vena cava, bicuspid and tricuspid valves, all labelled",
    "digestion":    "human digestive system: mouth → oesophagus → stomach → small intestine (duodenum, jejunum, ileum) → large intestine → rectum → anus, with liver and pancreas, all labelled",
    "neuron":       "neuron showing: dendrites (branching), cell body (circle with nucleus), axon (long line), myelin sheath (oval segments), nodes of Ranvier, synaptic knob, direction of impulse arrow",
    "eye":          "human eye cross-section: cornea, iris, pupil, lens, vitreous humour, retina, fovea, blind spot, optic nerve, ciliary muscles, all labelled",
    "reproduction": "longitudinal section of a flower showing: sepal, petal, stamen (anther + filament), carpel (stigma + style + ovary), ovules, receptacle, all labelled",
    "photosynthesis":"chloroplast structure: outer membrane, inner membrane, granum (stack of thylakoids), stroma, starch grain, labelled; with equation 6CO₂ + 6H₂O → C₆H₁₂O₆ + 6O₂ shown",
    "respiration":  "mitochondrion cross-section: outer membrane, inner membrane, cristae (folds), matrix, ATP synthase, all labelled",
    # Chemistry
    "atom":         "Bohr atomic model: nucleus (circle) labelled with protons P and neutrons N, electron shells (concentric circles) with electrons (dots) on each shell, element symbol in centre",
    "apparatus":    "laboratory glassware setup: stand with clamp holding a test tube or flask over a burner, beaker, thermometer, delivery tube, collecting jar over water trough, all labelled",
    "molecule":     "structural formula or ball-and-stick model of a simple molecule with atoms as circles and bonds as lines, atom symbols labelled",
    # Social Studies
    "map":          "outline map of India showing state boundaries, major rivers (Ganga, Yamuna, Godavari, Krishna, Brahmaputra), mountain ranges (Himalayas, Western/Eastern Ghats), and key locations as required",
}

def _get_diag_context(desc: str) -> str:
    dl = desc.lower()
    # Score by how many context keywords appear in description
    best_score, best_ctx = 0, "educational diagram for a school exam paper with all parts clearly labelled"
    for key, ctx in _DIAG_CONTEXT.items():
        if key in dl:
            score = len(key)  # longer key = more specific match
            if score > best_score:
                best_score, best_ctx = score, ctx
    return best_ctx


# ── Master SVG generation prompt ──────────────────────────────────────
def generate_diagram_svg(description: str) -> str | None:
    """
    Ask Gemini to produce a clean, accurate SVG for the given description.
    Returns the SVG string or None on failure.
    """
    ctx = _get_diag_context(description)

    prompt = f"""You are a professional technical illustrator producing diagrams for a Class 10 Indian school exam paper.

DIAGRAM TO DRAW: "{description}"
DIAGRAM TYPE: {ctx}

═══════════════════════════════════════════════════
OUTPUT RULES — follow every rule or the diagram is rejected
═══════════════════════════════════════════════════
1. Output ONLY the raw SVG code. No markdown code fences (``` or ```svg), no explanation, no comments outside SVG tags.
2. SVG must start with exactly:
   <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 320" width="500" height="320">
3. SVG must end with: </svg>
4. Background: add <rect x="0" y="0" width="500" height="320" fill="white"/> as the very first element.

VISUAL STYLE:
5. Main structural lines: stroke="#111111" stroke-width="2"
6. Secondary/dimension lines: stroke="#333333" stroke-width="1"
7. Dashed/construction lines: stroke="#555555" stroke-width="1" stroke-dasharray="5,3"
8. Arrow fill: fill="#111111"
9. Shape fills: fill="white" for closed shapes (triangles, circles, rectangles)
10. Shaded regions (if needed): fill="#e8e8e8"

LABELLING — critical for educational quality:
11. All labels: font-family="Arial, Helvetica, sans-serif" font-size="13" fill="#111111"
12. Smaller secondary labels (angle names, dimension ticks): font-size="11"
13. Place every label clearly AWAY from lines — never overlapping a line or another label
14. Use text-anchor="middle" for centred labels, "start" for left-aligned, "end" for right-aligned
15. Every important point, line, angle, and measurement MUST be labelled — this is an exam diagram
16. For angles: draw a small arc near the vertex, label it clearly (θ, α, ∠A, 60°, etc.)
17. Right angles: mark with a 6×6 square at the corner vertex

ARROWS:
18. Draw arrowheads as filled triangles: <polygon points="x1,y1 x2,y2 x3,y3" fill="#111111"/>
19. Use arrows on dimension lines (both ends) and direction-of-flow indicators

GEOMETRY ACCURACY:
20. All measurements must be geometrically consistent — if you label a length or angle, draw it accurately to scale
21. For circles: use <circle> elements. For arcs: use <path d="M... A..."/>
22. For curves and bezier paths: use smooth <path> with C or Q commands
23. Leave at least 25px padding on all four sides of the viewBox

ALLOWED ELEMENTS ONLY:
24. You may ONLY use: <svg>, <g>, <line>, <circle>, <ellipse>, <rect>, <polygon>, <polyline>, <path>, <text>, <tspan>
25. Do NOT use: <image>, <use>, <defs>, <symbol>, <clipPath>, <filter>, <foreignObject>, <marker>, <pattern>, <mask>, CSS styles, JavaScript

COMPLETENESS:
26. The diagram must be COMPLETE and SELF-CONTAINED — a student can understand it without reading anything else
27. Include all parts mentioned in the description. Do not omit any component.
28. If the description mentions specific measurements (e.g. radius 5 cm), label those measurements on the diagram

Generate the SVG now:"""

    text, _ = call_gemini(prompt)
    if not text:
        return None

    # Extract the SVG block — strip markdown fences if they crept in
    text = re.sub(r'```(?:svg|xml|html)?', '', text).strip()
    m = re.search(r'(<svg[\s\S]*?</svg>)', text, re.IGNORECASE)
    if not m:
        return None

    svg = m.group(1).strip()
    # Ensure background rect is present
    if '<rect x="0" y="0"' not in svg and "white" not in svg[:200]:
        svg = svg.replace(
            '>', '><rect x="0" y="0" width="500" height="320" fill="white"/>', 1
        )
    return svg


# ── High-quality SVG → PNG via wkhtmltoimage ──────────────────────────
def svg_to_png_bytes(svg_str: str, target_width_px: int = 900) -> bytes | None:
    """
    Render SVG to PNG at high resolution using wkhtmltoimage.
    Returns PNG bytes or None on failure.
    """
    if not _WKHTML_AVAILABLE:
        return None

    try:
        # Parse viewBox to get aspect ratio
        vb_match = re.search(r'viewBox=["\'][\d. ]+ ([\d.]+) ([\d.]+)["\']', svg_str)
        if vb_match:
            vb_w = float(vb_match.group(1))
            vb_h = float(vb_match.group(2))
        else:
            vb_w, vb_h = 500.0, 320.0

        target_height_px = int(target_width_px * vb_h / vb_w)

        # Wrap SVG in minimal HTML so wkhtmltoimage renders it cleanly
        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: white; width: {target_width_px}px; height: {target_height_px}px; overflow: hidden; }}
  svg {{ display: block; width: {target_width_px}px; height: {target_height_px}px; }}
</style>
</head><body>{svg_str}</body></html>"""

        with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
            f.write(html)
            htmlfile = f.name

        pngfile = htmlfile.replace('.html', '.png')

        result = subprocess.run([
            'wkhtmltoimage',
            '--format', 'png',
            '--width', str(target_width_px),
            '--height', str(target_height_px),
            '--disable-smart-width',
            '--quality', '100',
            '--quiet',
            htmlfile, pngfile
        ], capture_output=True, timeout=20)

        if result.returncode == 0 and os.path.exists(pngfile):
            with open(pngfile, 'rb') as f:
                png_bytes = f.read()
            os.unlink(pngfile)
            os.unlink(htmlfile)
            return png_bytes if len(png_bytes) > 500 else None

        # Cleanup on failure
        for fp in [htmlfile, pngfile]:
            if os.path.exists(fp):
                os.unlink(fp)
        return None

    except Exception:
        return None


# ── PNG bytes → ReportLab ImageFlowable ──────────────────────────────
def png_to_rl_image(png_bytes: bytes, width_pt: float):
    """Convert PNG bytes to a ReportLab flowable Image at the given width with correct height."""
    from reportlab.platypus import Image as RLImage
    from PIL import Image as PILImage

    # Get actual PNG dimensions so we can calculate the correct height
    pil_img = PILImage.open(BytesIO(png_bytes))
    px_w, px_h = pil_img.size
    aspect = px_h / px_w if px_w > 0 else 0.64
    height_pt = width_pt * aspect

    buf = BytesIO(png_bytes)
    img = RLImage(buf, width=width_pt, height=height_pt)
    img.hAlign = 'CENTER'
    return img


# ── Master function: SVG string → best available PDF flowable ─────────
def svg_to_best_image(svg_str: str, width_pt: float = 380):
    """
    Convert an SVG string to the best available ReportLab flowable.
    Priority: wkhtmltoimage PNG (high quality) → pure ReportLab renderer (fallback)
    """
    # Try high-quality PNG path first
    target_px = int(width_pt * 2.2)  # 2.2x gives crisp output at half the size
    png_bytes = svg_to_png_bytes(svg_str, target_width_px=target_px)
    if png_bytes:
        return png_to_rl_image(png_bytes, width_pt)

    # Fallback: pure ReportLab SVG renderer
    return svg_to_rl_drawing(svg_str, width_pt)


# ── Pure-Python SVG → ReportLab Drawing (fallback renderer) ───────────
def _svg_color(val, default=(0, 0, 0)):
    if not val or val in ('none', 'transparent', ''):
        return None
    val = val.strip()
    named = {
        'black': (0,0,0), 'white': (1,1,1), 'red': (1,0,0), 'blue': (0,0,1),
        'green': (0,.5,0), 'grey': (.5,.5,.5), 'gray': (.5,.5,.5),
        'lightgrey': (.83,.83,.83), 'lightgray': (.83,.83,.83),
        'darkgray': (.33,.33,.33), 'darkgrey': (.33,.33,.33),
        '#111111': (.067,.067,.067), '#333333': (.2,.2,.2),
        '#555555': (.333,.333,.333), '#888888': (.533,.533,.533),
        '#e8e8e8': (.91,.91,.91), '#f5f5f5': (.961,.961,.961),
        '#f0f0f0': (.941,.941,.941), '#ffffff': (1,1,1), '#000000': (0,0,0),
    }
    if val.lower() in named:
        return named[val.lower()]
    if val.startswith('#'):
        h = val[1:]
        if len(h) == 3: h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) == 6:
            try: return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)
            except Exception: pass
    if val.startswith('rgb('):
        nums = re.findall(r'\d+', val)
        if len(nums) >= 3: return (int(nums[0])/255, int(nums[1])/255, int(nums[2])/255)
    return default


def _parse_points(pts_str):
    nums = re.findall(r'[-+]?\d*\.?\d+', pts_str)
    return [(float(nums[i]), float(nums[i+1])) for i in range(0, len(nums)-1, 2)]


def _parse_style(style_str):
    result = {}
    for part in (style_str or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            result[k.strip()] = v.strip()
    return result


def _parse_path_d(d, scale_x, height_pt):
    import math

    def tx(x): return float(x) * scale_x
    def ty(y): return height_pt - float(y) * scale_x

    tokens = re.findall(
        r'[MmLlHhVvZzAaCcQqSsTt]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)

    paths = []
    cur_pts = []
    cur_x, cur_y = 0.0, 0.0
    start_x, start_y = 0.0, 0.0
    cmd = 'M'
    i = 0

    def consume(n):
        nonlocal i
        vals = []
        for _ in range(n):
            while i < len(tokens) and re.match(r'[A-Za-z]', tokens[i]):
                break
            if i < len(tokens):
                vals.append(float(tokens[i])); i += 1
        return vals

    while i < len(tokens):
        t = tokens[i]
        if re.match(r'[A-Za-z]', t):
            cmd = t; i += 1; continue

        if cmd in 'Mm':
            v = consume(2)
            if len(v) < 2: continue
            if cmd == 'm': cur_x += v[0]; cur_y += v[1]
            else: cur_x, cur_y = v[0], v[1]
            start_x, start_y = cur_x, cur_y
            if cur_pts: paths.append((cur_pts, False))
            cur_pts = [(tx(cur_x), ty(cur_y))]
            cmd = 'l' if cmd == 'm' else 'L'

        elif cmd in 'Ll':
            v = consume(2)
            if len(v) < 2: continue
            if cmd == 'l': cur_x += v[0]; cur_y += v[1]
            else: cur_x, cur_y = v[0], v[1]
            cur_pts.append((tx(cur_x), ty(cur_y)))

        elif cmd in 'Hh':
            v = consume(1)
            if not v: continue
            if cmd == 'h': cur_x += v[0]
            else: cur_x = v[0]
            cur_pts.append((tx(cur_x), ty(cur_y)))

        elif cmd in 'Vv':
            v = consume(1)
            if not v: continue
            if cmd == 'v': cur_y += v[0]
            else: cur_y = v[0]
            cur_pts.append((tx(cur_x), ty(cur_y)))

        elif cmd in 'Zz':
            if cur_pts: cur_pts.append((tx(start_x), ty(start_y)))
            paths.append((cur_pts, True))
            cur_pts = []
            cur_x, cur_y = start_x, start_y

        elif cmd in 'Aa':
            v = consume(7)
            if len(v) < 7: continue
            rx_a, ry_a, x_rot, laf, sf, ex, ey = v
            if cmd == 'a': ex += cur_x; ey += cur_y
            try:
                x_rot_r = math.radians(x_rot)
                cos_r, sin_r = math.cos(x_rot_r), math.sin(x_rot_r)
                dx2, dy2 = (cur_x - ex) / 2, (cur_y - ey) / 2
                x1p = cos_r*dx2 + sin_r*dy2
                y1p = -sin_r*dx2 + cos_r*dy2
                laf, sf = int(laf), int(sf)
                rx_a, ry_a = abs(rx_a), abs(ry_a)
                if rx_a > 0 and ry_a > 0:
                    sq = max(0, (rx_a*ry_a)**2 - (rx_a*y1p)**2 - (ry_a*x1p)**2)
                    dq = (rx_a*y1p)**2 + (ry_a*x1p)**2
                    c = math.sqrt(sq / dq) if dq > 0 else 0
                    if laf == sf: c = -c
                    cxp = c * rx_a * y1p / ry_a
                    cyp = -c * ry_a * x1p / rx_a
                    cxc = cos_r*cxp - sin_r*cyp + (cur_x+ex)/2
                    cyc = sin_r*cxp + cos_r*cyp + (cur_y+ey)/2
                    ang1 = math.atan2((y1p - cyp) / ry_a, (x1p - cxp) / rx_a)
                    ang2 = math.atan2((-y1p - cyp) / ry_a, (-x1p - cxp) / rx_a)
                    if sf == 0 and ang2 > ang1: ang2 -= 2*math.pi
                    if sf == 1 and ang2 < ang1: ang2 += 2*math.pi
                    steps = max(12, int(abs(ang2 - ang1) * max(rx_a, ry_a) * scale_x / 3))
                    for k in range(steps + 1):
                        a = ang1 + (ang2 - ang1) * k / steps
                        px = cxc + rx_a*math.cos(a)*cos_r - ry_a*math.sin(a)*sin_r
                        py = cyc + rx_a*math.cos(a)*sin_r + ry_a*math.sin(a)*cos_r
                        cur_pts.append((tx(px), ty(py)))
                else:
                    cur_pts.append((tx(ex), ty(ey)))
            except Exception:
                cur_pts.append((tx(ex), ty(ey)))
            cur_x, cur_y = ex, ey

        elif cmd in 'CcQqSsTt':
            # Approximate bezier curves by sampling 8 intermediate points
            import math
            n_params = {'C':6,'c':6,'Q':4,'q':4,'S':4,'s':4,'T':2,'t':2}
            n = n_params.get(cmd.upper(), 2)
            v = consume(n)
            if len(v) < 2: continue
            # For cubic bezier, sample the curve
            if cmd.upper() == 'C' and len(v) == 6:
                bx0, by0 = cur_x, cur_y
                if cmd == 'c':
                    bx1,by1 = cur_x+v[0],cur_y+v[1]
                    bx2,by2 = cur_x+v[2],cur_y+v[3]
                    bx3,by3 = cur_x+v[4],cur_y+v[5]
                else:
                    bx1,by1 = v[0],v[1]
                    bx2,by2 = v[2],v[3]
                    bx3,by3 = v[4],v[5]
                for k in range(1, 9):
                    t_ = k / 8
                    s_ = 1 - t_
                    bx = s_**3*bx0 + 3*s_**2*t_*bx1 + 3*s_*t_**2*bx2 + t_**3*bx3
                    by = s_**3*by0 + 3*s_**2*t_*by1 + 3*s_*t_**2*by2 + t_**3*by3
                    cur_pts.append((tx(bx), ty(by)))
                cur_x, cur_y = bx3, by3
            else:
                if cmd.islower(): cur_x += v[-2]; cur_y += v[-1]
                else: cur_x, cur_y = v[-2], v[-1]
                cur_pts.append((tx(cur_x), ty(cur_y)))
        else:
            i += 1

    if cur_pts:
        paths.append((cur_pts, False))
    return paths


def svg_to_rl_drawing(svg_str: str, width_pt: float = 380):
    """Pure ReportLab SVG renderer — fallback when wkhtmltoimage unavailable."""
    from reportlab.graphics.shapes import Drawing, Line, Circle, Rect, Polygon, PolyLine, String, Group
    from reportlab.lib.colors import Color
    import math

    try:
        clean = re.sub(r'<(/?)[\w]+:', r'<\1', svg_str)
        clean = re.sub(r'\s[\w]+:[\w-]+="[^"]*"', '', clean)
        clean = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[\da-fA-F]+);)', '&amp;', clean)

        root = ET.fromstring(clean)

        vb = root.get('viewBox', '0 0 500 320')
        vb_parts = [float(x) for x in re.findall(r'[-\d.]+', vb)]
        svg_w = vb_parts[2] if len(vb_parts) >= 3 else float(root.get('width', 500) or 500)
        svg_h = vb_parts[3] if len(vb_parts) >= 4 else float(root.get('height', 320) or 320)
        if svg_w <= 0: svg_w = 500
        if svg_h <= 0: svg_h = 320

        scale_x = width_pt / svg_w
        height_pt = svg_h * scale_x
        drawing = Drawing(width_pt, height_pt)

        def tx(x): return float(x) * scale_x
        def ty(y): return height_pt - float(y) * scale_x

        def make_color(val, default_rgb=(0, 0, 0)):
            if val in (None, 'none', 'transparent', ''): return None
            rgb = _svg_color(val, default_rgb)
            return Color(rgb[0], rgb[1], rgb[2]) if rgb else None

        def parse_sw(val):
            try: return max(0.3, float(re.findall(r'[\d.]+', str(val))[0]) * scale_x)
            except Exception: return 1.0

        NS = '{http://www.w3.org/2000/svg}'

        def _inh(el, attr, ps, default):
            style = _parse_style(el.get('style', ''))
            css = attr.replace('_', '-')
            if css in style: return style[css]
            v = el.get(attr)
            if v is not None: return v
            if attr in ps: return ps[attr]
            return default

        def render_el(el, group, ps=None):
            if ps is None: ps = {}
            tag = el.tag.replace(NS, '').lower()

            my_stroke = _inh(el, 'stroke', ps, '#111111')
            my_fill   = _inh(el, 'fill',   ps, 'none')
            sw_raw    = _inh(el, 'stroke-width', ps, '1.5')
            sw        = parse_sw(sw_raw)
            dash_raw  = _inh(el, 'stroke-dasharray', ps, None)

            stroke_c = make_color(my_stroke)
            fill_c   = make_color(my_fill)

            cs = dict(ps)
            cs.update({'stroke': my_stroke, 'fill': my_fill, 'stroke-width': sw_raw})
            if dash_raw: cs['stroke-dasharray'] = dash_raw

            def set_dash(shape):
                if dash_raw:
                    try:
                        dp = [float(v)*scale_x for v in re.findall(r'[\d.]+', dash_raw)]
                        shape.strokeDashArray = dp
                    except Exception: pass

            if tag == 'line':
                shape = Line(tx(el.get('x1','0')), ty(el.get('y1','0')),
                             tx(el.get('x2','0')), ty(el.get('y2','0')))
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                set_dash(shape)
                group.add(shape)

            elif tag == 'circle':
                shape = Circle(tx(el.get('cx','0')), ty(el.get('cy','0')),
                               float(el.get('r','5')) * scale_x)
                shape.fillColor   = fill_c or Color(1,1,1)
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)

            elif tag == 'ellipse':
                cx = tx(el.get('cx','0')); cy = ty(el.get('cy','0'))
                rx = float(el.get('rx','10')) * scale_x
                ry = float(el.get('ry','10')) * scale_x
                pts = []
                for k in range(37):
                    a = 2 * math.pi * k / 36
                    pts += [cx + rx*math.cos(a), cy + ry*math.sin(a)]
                shape = Polygon(pts)
                shape.fillColor   = fill_c or Color(1,1,1)
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)

            elif tag == 'rect':
                x_  = float(el.get('x','0')); y_  = float(el.get('y','0'))
                rw  = float(el.get('width','10')); rh = float(el.get('height','10'))
                shape = Rect(tx(x_), ty(y_+rh), rw*scale_x, rh*scale_x)
                shape.fillColor   = fill_c or Color(1,1,1)
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)

            elif tag in ('polygon','polyline'):
                pairs = _parse_points(el.get('points',''))
                if len(pairs) >= 2:
                    pts = []
                    for (px, py) in pairs: pts += [tx(px), ty(py)]
                    shape = Polygon(pts) if tag=='polygon' else PolyLine(pts)
                    if tag == 'polygon': shape.fillColor = fill_c or Color(1,1,1)
                    shape.strokeColor = stroke_c or Color(0,0,0)
                    shape.strokeWidth = sw
                    set_dash(shape)
                    group.add(shape)

            elif tag == 'path':
                d = el.get('d','')
                if not d.strip(): return
                for (pts, closed) in _parse_path_d(d, scale_x, height_pt):
                    if len(pts) < 2: continue
                    flat = [c for pt in pts for c in pt]
                    if closed and fill_c:
                        shape = Polygon(flat)
                        shape.fillColor   = fill_c
                        shape.strokeColor = stroke_c or Color(0,0,0)
                        shape.strokeWidth = sw
                    else:
                        shape = PolyLine(flat)
                        shape.strokeColor = stroke_c or Color(0,0,0)
                        shape.strokeWidth = sw
                        set_dash(shape)
                    group.add(shape)

            elif tag == 'text':
                raw_x = float(el.get('x','0')); raw_y = float(el.get('y','0'))
                anchor = el.get('text-anchor', _parse_style(el.get('style','')).get('text-anchor','start'))
                fs_raw = _inh(el, 'font-size', ps, '13')
                try: fs = max(6, float(re.findall(r'[\d.]+', str(fs_raw))[0]) * scale_x)
                except Exception: fs = 11 * scale_x

                parts_text = []
                if el.text and el.text.strip():
                    parts_text.append((raw_x, raw_y, el.text.strip()))
                for tspan in el:
                    if tspan.tag.replace(NS,'').lower() == 'tspan':
                        tx_ = float(tspan.get('x', raw_x))
                        ty_ = float(tspan.get('y', raw_y))
                        if tspan.text and tspan.text.strip():
                            parts_text.append((tx_, ty_, tspan.text.strip()))
                if not parts_text:
                    all_txt = ''.join(el.itertext()).strip()
                    if all_txt: parts_text.append((raw_x, raw_y, all_txt))

                fc  = make_color(_inh(el,'fill',ps,'#111111')) or Color(0,0,0)
                bold = 'bold' in (_inh(el,'font-weight',ps,'')+_parse_style(el.get('style','')).get('font-weight',''))
                font_name = 'Helvetica-Bold' if bold else 'Helvetica'

                for (px, py, txt) in parts_text:
                    x_pos = tx(px); y_pos = ty(py) - fs * 0.15
                    if anchor == 'middle': x_pos -= len(txt) * fs * 0.27
                    elif anchor == 'end':  x_pos -= len(txt) * fs * 0.53
                    s = String(x_pos, y_pos, txt)
                    s.fontSize = fs; s.fillColor = fc; s.fontName = font_name
                    group.add(s)

            elif tag == 'g':
                sub = Group()
                for child in el: render_el(child, sub, cs)
                group.add(sub)

        top = Group()
        for child in root: render_el(child, top, {})
        drawing.add(top)
        return drawing

    except Exception:
        return None


# Keep old name as alias for backward compat
def svg_to_rl_image(svg_str: str, width_pt: float = 380):
    return svg_to_best_image(svg_str, width_pt)




# ═══════════════════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data             = request.get_json(force=True) or {}
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
            board = (data.get("board") or "AP State Board").strip()

        if not subject and (data.get("scope") == "all" or data.get("all_chapters")):
            subject = "Mixed Subjects"

        use_fallback = str(data.get("use_fallback", "false")).lower() in ("true", "1", "yes")
        prompt = data.get("prompt") or build_prompt(
            class_name, subject, chapter, board, exam_type, difficulty, marks, suggestions)

        generated_text = None
        api_error      = None

        if not use_fallback:
            generated_text, api_error = call_gemini(prompt)

        if not generated_text:
            if use_fallback or not GEMINI_KEY:
                generated_text = build_local_paper(class_name, subject, chapter, marks, difficulty)
                use_fallback = True
            else:
                return jsonify({"success": False, "error": "AI generation failed.",
                                "api_error": api_error,
                                "suggestion": "Send use_fallback=true for a template paper."}), 502

        paper, key = split_key(generated_text)
        return jsonify({"success": True, "paper": paper, "answer_key": key,
                        "api_error": api_error, "used_fallback": use_fallback,
                        "board": board, "subject": subject, "chapter": chapter})
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e),
                        "trace": traceback.format_exc()}), 500


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

        diagrams = {}
        if GEMINI_KEY and GENAI_AVAILABLE:
            # Collect diagram descriptions from both paper and answer key
            full_text = paper_text + "\n" + (answer_key or "")
            diag_descs = re.findall(
                r'\[DIAGRAM:\s*([^\]]+)\]|\[draw\s+([^\]]+)\]',
                full_text, re.IGNORECASE)
            unique_descs = []
            seen = set()
            for d1, d2 in diag_descs:
                desc = (d1 or d2).strip()
                if desc and desc not in seen:
                    seen.add(desc)
                    unique_descs.append(desc)

            # Generate all diagrams in parallel for speed
            if unique_descs:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=min(4, len(unique_descs))) as ex:
                    futures = {ex.submit(generate_diagram_svg, d): d for d in unique_descs}
                    for future in as_completed(futures):
                        desc = futures[future]
                        try:
                            svg = future.result(timeout=30)
                            if svg:
                                diagrams[desc] = svg
                        except Exception:
                            pass

        pdf_bytes = create_exam_pdf(
            paper_text, subject, chapter,
            board=board, answer_key=answer_key,
            include_key=include_key, diagrams=diagrams)

        parts    = [p for p in [board, subject, chapter] if p]
        filename = ("_".join(parts) + ".pdf").replace(" ", "_").replace("/", "-")
        return send_file(BytesIO(pdf_bytes), as_attachment=True,
                         download_name=filename, mimetype="application/pdf")
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e),
                        "trace": traceback.format_exc()}), 500


@app.route("/health")
def health():
    configured = bool(GEMINI_KEY and GENAI_AVAILABLE)
    models     = discover_models() if configured else []
    return jsonify({"status": "ok",
                    "gemini": "configured" if configured else "not configured",
                    "models_available": models})


@app.route("/chapters")
def chapters():
    try:
        data_path = _DATA_DIR / "curriculum.json"
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