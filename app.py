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
# Professional exam paper palette
C_NAVY  = HexColor("#1a237e")   # Deep navy for header
C_STEEL = HexColor("#1a1a1a")   # Near-black for question numbers
C_BODY  = HexColor("#1a1a1a")   # Body text
C_GREY  = HexColor("#444444")   # Marks label, dark grey
C_LIGHT = HexColor("#e8eaf6")   # Section banner background, light indigo tint
C_RULE  = HexColor("#3949ab")   # Rules/borders, indigo
C_MARK  = HexColor("#c62828")   # Mark labels, deep red for visibility
C_KRED  = HexColor("#1a237e")   # Answer key headings, navy
C_KFILL = HexColor("#f3f4ff")   # Answer key background, very light blue
C_STEP  = HexColor("#1a1a1a")   # Key steps, body colour
C_HDR   = HexColor("#1a237e")   # Header band fill


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

    S("PTitle",    fontName=B, fontSize=16, textColor=white,
      alignment=TA_CENTER, leading=24, spaceAfter=0, spaceBefore=0)
    S("PMeta",     fontName=R, fontSize=9, textColor=white,
      alignment=TA_LEFT, leading=13, spaceAfter=0)
    S("PMetaR",    fontName=R, fontSize=9, textColor=white,
      alignment=TA_RIGHT, leading=13, spaceAfter=0)
    S("PMetaC",    fontName=R, fontSize=9, textColor=white,
      alignment=TA_CENTER, leading=13, spaceAfter=0)
    S("SecBanner", fontName=B, fontSize=10.5, textColor=C_NAVY,
      leading=15, spaceAfter=0, spaceBefore=0)
    S("InstrHead", fontName=B, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, spaceBefore=4)
    S("Instr",     fontName=R, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, leftIndent=18, firstLineIndent=-18)
    S("Q",         fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=16, spaceBefore=5, spaceAfter=1,
      leftIndent=22, firstLineIndent=-22)
    S("QCont",     fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=16, spaceBefore=1, spaceAfter=1, leftIndent=22)
    S("QSub",      fontName=R, fontSize=10.5, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=16, spaceBefore=2, spaceAfter=1,
      leftIndent=36, firstLineIndent=-14)
    S("Opt",       fontName=R, fontSize=10, textColor=C_BODY,
      leading=14, spaceAfter=0, leftIndent=0)
    S("KTitle",    fontName=B, fontSize=14, textColor=white,
      alignment=TA_CENTER, leading=20, spaceAfter=6, spaceBefore=0)
    S("KSec",      fontName=B, fontSize=10.5, textColor=C_NAVY,
      leading=14, spaceAfter=2, spaceBefore=6)
    S("KQ",        fontName=B, fontSize=10.5, textColor=C_BODY,
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
        canvas.setStrokeColor(HexColor("#1a237e"))
        canvas.setLineWidth(1.0)
        canvas.line(LM, A4[1] - 12*mm, RM, A4[1] - 12*mm)
        canvas.setStrokeColor(HexColor("#3949ab"))
        canvas.setLineWidth(0.5)
        canvas.line(LM, 20, RM, 20)
        canvas.setFont(_f("Ital"), 7.5)
        canvas.setFillColor(HexColor("#3949ab"))
        if doc.page == 1:
            canvas.drawString(LM, 10,
                "ExamCraft  ·  Created by Laxman Nimmagadda"
                "  (if the paper is hard, I am not guilty)")
        canvas.setFillColor(HexColor("#1a237e"))
        canvas.drawRightString(RM, 10, f"Page {doc.page}")
        canvas.restoreState()


# ═══════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════
def _sec_banner(text, st, pw):
    p = Paragraph(f'<b>{text}</b>', st["SecBanner"])
    t = Table([[p]], colWidths=[pw])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), HexColor("#e8eaf6")),
        ("LINEBELOW",     (0,0),(-1,-1), 2.0, HexColor("#3949ab")),
        ("LINETOP",       (0,0),(-1,-1), 0.5, HexColor("#3949ab")),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
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
    h_time  = _pull(r'Time\s*(?:Allowed|:)\s*([^\n]+)', "3 Hours 15 Minutes")
    h_class = _pull(r'Class\s*[:/]?\s*(\d+\w*)', "")
    h_board = board or _pull(r'Board\s*[:/]\s*([^\n]+)', "")

    disp_title   = subject or "Question Paper"
    disp_chapter = chapter or ""

    title_str = disp_title
    if disp_chapter:
        title_str += f"  —  {disp_chapter}"

    # ── Navy header band ─────────────────────────────────────────────
    tbl_title = Table(
        [[Paragraph(title_str, st["PTitle"])]],
        colWidths=[PW])
    tbl_title.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_HDR),
        ("TOPPADDING",    (0,0),(-1,-1), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("ROUNDEDCORNERS", [4, 4, 0, 0]),
    ]))

    left_meta  = "  |  ".join(x for x in [h_board, f"Class {h_class}" if h_class else ""] if x)
    right_meta = f"Total Marks: {h_marks}   |   Time: {h_time}"
    tbl_meta = Table(
        [[Paragraph(left_meta,  st["PMeta"]),
          Paragraph(right_meta, st["PMetaR"])]],
        colWidths=[PW*0.50, PW*0.50])
    tbl_meta.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_HDR),
        ("LINEBELOW",     (0,0),(-1,-1), 2.0, HexColor("#ffd600")),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("ROUNDEDCORNERS", [0, 0, 4, 4]),
    ]))

    elems += [tbl_title, tbl_meta, Spacer(1, 10)]

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
            ("BACKGROUND",    (0,0),(-1,-1), C_HDR),
            ("LINEBELOW",     (0,0),(-1,-1), 2.5, HexColor("#ffd600")),
            ("TOPPADDING",    (0,0),(-1,-1), 10),
            ("BOTTOMPADDING", (0,0),(-1,-1), 10),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ]))
        elems += [kt, Spacer(1, 12)]

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
                    generation_config={"temperature": 0.3, "max_output_tokens": 8192, "top_p": 0.8})
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
# ═══════════════════════════════════════════════════════════════════════
# SIMPLE, CLEAN PROMPT BUILDER  (replaces the old 800-line monster)
# One function, no hallucination-inducing chapter banks.
# The LLM generates from its own knowledge; we just tell it the rules.
# ═══════════════════════════════════════════════════════════════════════

def build_prompt(class_name, subject, chapter, board, exam_type,
                 difficulty, marks, suggestions):

    m   = max(10, int(marks) if str(marks).isdigit() else 100)
    cls = class_name or "10"

    extra = f"\nTEACHER NOTES: {suggestions.strip()}\n" if (suggestions or "").strip() else ""

    board_l = (board or "").lower()
    subj_l  = (subject or "").lower()

    is_stem = any(k in subj_l for k in [
        "math", "maths", "science", "physics", "chemistry",
        "biology", "algebra", "geometry", "trigonometry", "statistics"
    ])
    math_notation = (
        "\nMATH NOTATION — use $...$ for every expression:\n"
        "  Powers: $x^{2}$   Fractions: $\\frac{a}{b}$   Roots: $\\sqrt{2}$\n"
        "  Greek: $\\theta$ $\\alpha$ $\\pi$   Trig: $\\sin\\theta$ $\\cos 60^{\\circ}$\n"
        "  Subscripts: $H_{2}O$ $v_{0}$   Blanks: __________\n"
    ) if is_stem else ""

    # --- Competitive exam ---
    comp_map = {"ntse": "NTSE", "nso": "NSO", "imo": "IMO", "ijso": "IJSO"}
    for key, val in comp_map.items():
        if key in board_l:
            return _simple_competitive(val, subject, chapter, cls, m, difficulty, extra, math_notation)

    # --- State board 9-10 ---
    cls_n = int(re.search(r'\d+', str(cls)).group()) if re.search(r'\d+', str(cls)) else 10
    if cls_n >= 9:
        return _simple_state_board(subject, chapter, board, cls, m, difficulty, extra, math_notation)
    else:
        return _simple_lower_class(subject, chapter, board, cls, m, difficulty, extra, math_notation)


def _compute_structure(marks):
    """Dynamically compute AP/TS-style paper structure for any mark value."""
    m = max(10, int(marks))
    partA = round(m * 0.20)
    partB = m - partA

    # Part A sections
    mcq_marks  = round(partA * 0.50)
    fill_marks = round(partA * 0.25)
    match_marks = partA - mcq_marks - fill_marks
    n_mcq   = mcq_marks          # 1 mark each
    n_fill  = fill_marks         # 1 mark each
    n_match = max(2, match_marks) # pairs; each pair = 1 mark

    # Part B sections (percentage-based, marks per question fixed)
    vsq_marks  = round(partB * 0.25)
    sa_marks   = round(partB * 0.20)
    la_marks   = round(partB * 0.30)
    app_marks  = partB - vsq_marks - sa_marks - la_marks

    n_vsq       = max(2, vsq_marks  // 2)       # 2 marks each, all compulsory
    n_sa_att    = max(2, sa_marks   // 4)       # attempt N
    n_sa_given  = n_sa_att + 2                  # give N+2
    n_la_att    = max(1, la_marks   // 6)       # attempt N
    n_la_given  = n_la_att + 2
    marks_per_app = 10 if app_marks >= 10 else 8 if app_marks >= 8 else max(4, (app_marks // 2) * 2)
    n_app_att   = max(1, app_marks  // marks_per_app)
    n_app_given = n_app_att + 1

    actual_vsq   = n_vsq * 2
    actual_sa    = n_sa_att * 4
    actual_la    = n_la_att * 6
    actual_app   = n_app_att * marks_per_app
    actual_partB = actual_vsq + actual_sa + actual_la + actual_app
    actual_total = partA + actual_partB

    return dict(
        m=m, partA=partA, partB=actual_partB, total=actual_total,
        n_mcq=n_mcq, n_fill=n_fill, n_match=n_match,
        mcq_marks=mcq_marks, fill_marks=fill_marks, match_marks=match_marks,
        n_vsq=n_vsq, vsq_total=actual_vsq,
        n_sa_given=n_sa_given, n_sa_att=n_sa_att, sa_total=actual_sa,
        n_la_given=n_la_given, n_la_att=n_la_att, la_total=actual_la,
        n_app_given=n_app_given, n_app_att=n_app_att, marks_per_app=marks_per_app, app_total=actual_app,
        iv_start=1, iv_end=n_vsq,
        v_start=n_vsq+1, v_end=n_vsq+n_sa_given,
        vi_start=n_vsq+n_sa_given+1, vi_end=n_vsq+n_sa_given+n_la_given,
        vii_start=n_vsq+n_sa_given+n_la_given+1,
        vii_end=n_vsq+n_sa_given+n_la_given+n_app_given,
    )


def _simple_state_board(subject, chapter, board, cls, marks, difficulty, extra, math_notation):
    chap_str = chapter or "as per syllabus"
    diff_mix = {
        "Easy":   "50% recall/understand, 30% apply, 20% analyse",
        "Medium": "25% recall, 40% apply, 25% analyse, 10% evaluate",
        "Hard":   "10% recall, 20% understand, 35% apply, 25% analyse, 10% evaluate",
    }.get(difficulty, "25% recall, 40% apply, 25% analyse, 10% evaluate")

    s = _compute_structure(marks)
    actual = s['total']

    # Build timing based on marks
    if actual <= 30:
        time_str = "1 Hour"
    elif actual <= 60:
        time_str = "2 Hours"
    else:
        time_str = "3 Hours 15 Minutes"

    match_word = "pairs" if s['n_match'] != 1 else "pair"

    return f"""You are an experienced {board} Class {cls} examiner. Generate a complete, ready-to-print exam paper.
{extra}
PAPER DETAILS
Subject   : {subject}
Chapter   : {chap_str}
Class     : {cls}   Board: {board}
Total     : {actual} marks   Difficulty: {difficulty} ({diff_mix})

STRUCTURE (follow exactly — question counts computed from {actual}-mark blueprint):

PART A — OBJECTIVE ({s['partA']} marks)
Section I   — {s['n_mcq']} MCQ × 1 mark = {s['mcq_marks']} marks  [Q1–Q{s['n_mcq']}]
Section II  — {s['n_fill']} Fill-in-the-blank × 1 mark = {s['fill_marks']} marks  [Q{s['n_mcq']+1}–Q{s['n_mcq']+s['n_fill']}]
Section III — 1 Match-the-following ({s['n_match']} {match_word}) = {s['match_marks']} marks  [Q{s['n_mcq']+s['n_fill']+1}]
                              Subtotal = {s['partA']} marks

PART B — WRITTEN ({s['partB']} marks)
Section IV  — {s['n_vsq']} Very Short Answer (ALL compulsory) × 2 marks = {s['vsq_total']} marks  [Q{s['iv_start']}–Q{s['iv_end']}]
Section V   — {s['n_sa_given']} Short Answer given, attempt any {s['n_sa_att']} × 4 marks = {s['sa_total']} marks  [Q{s['v_start']}–Q{s['v_end']}]
Section VI  — {s['n_la_given']} Long Answer given, attempt any {s['n_la_att']} × 6 marks = {s['la_total']} marks  [Q{s['vi_start']}–Q{s['vi_end']}, each with OR option]
Section VII — {s['n_app_given']} Application/Problem given, attempt any {s['n_app_att']} × {s['marks_per_app']} marks = {s['app_total']} marks  [Q{s['vii_start']}–Q{s['vii_end']}]
                              Subtotal = {s['partB']} marks
                         GRAND TOTAL = {actual} marks ✓
{math_notation}
FORMATTING RULES:
- Every question ends with its mark tag: [1 Mark] [2 Marks] [4 Marks] [6 Marks] [{s['marks_per_app']} Marks]
- MCQ: exactly 4 options (A)(B)(C)(D), line ends with (   ) for student to write answer
- Fill-blank: use __________ for the blank
- Match: pipe table with exactly {s['n_match']} data rows:
  | Group A | Group B |
  |---|---|
  | item | match |
- Every Section VI question needs an OR alternative
- Diagrams: write [DIAGRAM: description] on its own line, nothing else
- All questions must be about "{chap_str}" only
- No two questions should test the same thing

After all questions, write:

ANSWER KEY

Then give complete answers with full worked solutions.

BEGIN the paper now. Write the header then Part A directly.

{subject} — {chap_str}
{board} | Class {cls}   Total Marks: {actual}   Time: {time_str}

PART A — OBJECTIVE  ({s['partA']} Marks)
(Answer on this sheet. Submit after 30 minutes.)

Section I — Multiple Choice Questions  [1 Mark each]
"""


def _simple_lower_class(subject, chapter, board, cls, marks, difficulty, extra, math_notation):
    chap_str = chapter or "as per syllabus"
    return f"""You are a {board} Class {cls} examiner. Generate a complete exam paper.
{extra}
Subject: {subject}  |  Chapter: {chap_str}  |  Class: {cls}  |  Total: 50 marks
Difficulty: {difficulty}
{math_notation}
STRUCTURE:
Section A — Objective (10 marks): 5 MCQ [Q1–5] + 3 Fill-blank [Q6–8] + 1 Match 2-pair [Q9] = 10 marks
Section B — Very Short Answer (20 marks): 10 questions × 2 marks [ALL compulsory, Q1–10]
Section C — Short Answer (10 marks): 4 questions, attempt any 2 × 5 marks [Q11–14]
Section D — Long Answer (10 marks): 2 questions, attempt any 1 × 10 marks [Q15–16]
Total = 50 marks

RULES:
- All questions about "{chap_str}" only
- MCQ: 4 options (A)(B)(C)(D), line ends with (   )
- Fill-blank: use __________ for the blank
- Every question ends with mark tag [1 Mark] [2 Marks] [5 Marks] [10 Marks]

After questions, write ANSWER KEY with full answers.

BEGIN:

Subject: {subject}   Class: {cls}   Total: 50 Marks   Board: {board}

Section A — Objective  (10 Marks)
"""


def _simple_competitive(exam, subject, chapter, cls, marks, difficulty, extra, math_notation):
    chap_str = chapter or "full syllabus"

    if exam == "NTSE":
        subj_l = (subject or "").lower()
        if "mat" in subj_l or "mental" in subj_l or "reasoning" in subj_l:
            return f"""Generate a complete NTSE MAT (Mental Ability Test) practice paper.
{extra}Class: {cls}   Total: 100 questions × 1 mark = 100 marks   Time: 2 hours   No negative marking
Difficulty: {difficulty}

QUESTION TYPE DISTRIBUTION (must total 100):
Q1–12: Verbal Analogy (12)
Q13–22: Number/Letter Series (10)
Q23–32: Non-Verbal Analogy — describe figures in text (10)
Q33–40: Coding-Decoding (8)
Q41–46: Blood Relations (6)
Q47–52: Direction & Distance (6)
Q53–58: Ranking & Ordering (6)
Q59–64: Clock & Calendar (6)
Q65–70: Venn Diagrams (6)
Q71–76: Mirror/Water Image — describe in text (6)
Q77–82: Classification/Odd-One-Out (6)
Q83–88: Pattern Completion — describe in text (6)
Q89–94: Mathematical Operations (6)
Q95–100: Mixed Reasoning (6)

FORMAT: Q[n]. [question] [1 Mark]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY after all 100 questions: Q1.(B) Q2.(A) ... (10 per line). Then explain Q1–Q20 reasoning.

BEGIN:
Exam: NTSE MAT Practice   Class: {cls}   Marks: 100   Time: 2 Hours

Q1–Q12 — Verbal Analogy  [1 Mark each]
"""
        return f"""Generate a complete NTSE SAT practice paper.
{extra}Class: {cls}   Topic: {chap_str}   Total: 100 × 1 mark = 100 marks   Time: 2 hours
{math_notation}
SECTION DISTRIBUTION:
Science Q1–Q40: Physics Q1–13, Chemistry Q14–26, Biology Q27–40
Social Science Q41–Q80: History Q41–53, Geography Q54–66, Civics Q67–73, Economics Q74–80
Mathematics Q81–Q100: all Class {cls} topics

FORMAT: Q[n]. [question] [1 Mark]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY after all 100 questions. Explain Maths answers Q81–Q100 step by step.

BEGIN:
Exam: NTSE SAT Practice   Class: {cls}   Marks: 100   Time: 2 Hours

Science — Physics (Q1–Q13)  [1 Mark each]
"""

    if exam in ("NSO", "IMO"):
        label = "Science" if exam == "NSO" else "Mathematics"
        struct = (
            "Section 1 — Logical Reasoning Q1–10 (10 × 1M)\n"
            f"Section 2 — {label} Q11–45 (35 × 1M)\n"
            "Section 3 — Achiever's Section Q46–50 (5 × 3M)\n"
            "Total = 60 marks"
        ) if exam == "NSO" else (
            "Section 1 — Logical Reasoning Q1–10 (10 × 1M)\n"
            "Section 2 — Mathematical Reasoning Q11–35 (25 × 1M)\n"
            "Section 3 — Everyday Mathematics Q36–45 (10 × 1M)\n"
            "Section 4 — Achiever's Section Q46–50 (5 × 3M)\n"
            "Total = 60 marks"
        )
        return f"""Generate a complete {exam} practice paper.
{extra}Class: {cls}   Topic: {chap_str}   60 marks   1 hour   No negative marking
Difficulty: {difficulty}
{math_notation}
STRUCTURE:
{struct}

Section 1: Pure reasoning only — no direct subject content.
Achiever's Section: Hard HOT questions, 3 marks each, need 3+ reasoning steps.

FORMAT: Q[n]. [question] [mark]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY: Q1.(B) Q2.(A) ... (10 per line). For Achiever's questions explain why correct and why best wrong option is wrong.

BEGIN:
Exam: {exam} Practice   Class: {cls}   Topic: {chap_str}   Marks: 60   Time: 1 Hour

Section 1 — Logical Reasoning  [Q1–Q10 | 1 Mark each]
"""

    # IJSO
    return f"""Generate a complete IJSO/NSEJS Stage 1 practice paper.
{extra}Class: {cls}   Topic: {chap_str}   80 questions   Marking: +3 correct / −1 wrong   Time: 2 hours
Difficulty: {difficulty}
{math_notation}
STRUCTURE:
Physics Q1–Q27 (27 questions)
Chemistry Q28–Q54 (27 questions)
Biology Q55–Q80 (26 questions)
Total = 80 questions

Every question requires conceptual understanding, not just recall.
Wrong options must represent specific named misconceptions.

FORMAT: Q[n]. [question] [+3/−1]
(A) opt   (B) opt   (C) opt   (D) opt

ANSWER KEY: list all 80. Then for each: correct letter + one sentence why correct + why best distractor is wrong.

BEGIN:
Exam: IJSO/NSEJS Stage 1 Practice   Class: {cls}   Marking: +3/−1/0   Time: 2 Hours

Physics (Q1–Q27)  [+3/−1 each]
"""


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
                               m, difficulty, extra, math_note, pat, user_marks=m)



# ========================================================================
# AP/TS CLASS 9-10  SSC  (100-mark official pattern)
# Board-accurate: exact section counts, topic-locked, chapter content banks
# ========================================================================

# Per-chapter content banks for Mathematics
_MATH_CHAPTER_TOPICS = {
    "trigonometry": {
        "concepts": [
            "sin, cos, tan, cot, sec, cosec as ratios in a right triangle",
            "Trigonometric ratios of standard angles: 0 deg, 30 deg, 45 deg, 60 deg, 90 deg",
            "Fundamental identities: sin2+cos2=1, 1+tan2=sec2, 1+cot2=cosec2",
            "Complementary angle relations: sin(90-T)=cosT, tan(90-T)=cotT, etc.",
            "Finding one ratio given another using identities",
            "Evaluating expressions using standard angle values",
            "Proving trigonometric identities algebraically",
        ],
        "mcq": [
            ("The value of sin 30 + cos 60 is", ["1", "0", "1/2", "sq3/2"], 0),
            ("tan 45 equals", ["0", "1", "sq3", "1/sq3"], 1),
            ("If sin T = 3/5, then cos T equals", ["4/5", "3/4", "5/4", "5/3"], 0),
            ("sin2 60 + cos2 60 equals", ["1", "0", "3/4", "1/4"], 0),
            ("The value of sec2 45 - tan2 45 is", ["1", "0", "2", "sq2"], 0),
            ("(1 - sin2 T) equals", ["cos2 T", "tan2 T", "sec2 T", "cosec2 T"], 0),
            ("tan T in terms of sin T and cos T is", ["sinT/cosT", "cosT/sinT", "1/sinT", "1/cosT"], 0),
            ("cosec 30 equals", ["2", "1", "1/2", "sq3"], 0),
            ("The value of sin 0 + cos 90 is", ["0", "1", "2", "sq2"], 0),
            ("If tan T = 1 then T equals", ["45 deg", "30 deg", "60 deg", "90 deg"], 0),
        ],
        "fill": [
            "sin2 T + cos2 T = __________",
            "tan(90 deg - T) = __________",
            "The value of cos 0 deg is __________",
            "sec2 T - tan2 T = __________",
            "sin 60 deg = __________",
        ],
        "match_a": ["sin2 T + cos2 T", "1 + tan2 T", "sin(90 deg - T)", "tan T", "cosec T"],
        "match_b": ["1", "sec2 T", "cos T", "sinT / cosT", "1 / sin T"],
        "vsq": [
            "If sin A = 1/2, find the values of cos A and tan A. [2 Marks]",
            "Evaluate: 2 tan2 45 + cos2 30 - sin2 60 [2 Marks]",
            "If tan T = 3/4, find sin T and cos T. [2 Marks]",
            "Show that sin 30 cos 60 + cos 30 sin 60 = sin 90. [2 Marks]",
            "Find the value of (sin 30 + cos 30) - (sin 60 + cos 60). [2 Marks]",
            "If A = 45 deg, verify that sin 2A = 2 sin A cos A. [2 Marks]",
            "Evaluate: cos2 45 / sin2 30 [2 Marks]",
            "If tan(A+B) = sq3 and tan(A-B) = 1/sq3, 0 < A+B <= 90, A > B, find A and B. [2 Marks]",
            "Prove that cosec2 T - cot2 T = 1. [2 Marks]",
            "Evaluate: (sin 45 + cos 45)^2 [2 Marks]",
        ],
        "sa": [
            "Prove that (sin T + cosec T)^2 + (cos T + sec T)^2 = 7 + tan2 T + cot2 T. [4 Marks]",
            "If tan T + cot T = 5, find the value of tan2 T + cot2 T. [4 Marks]",
            "Prove: (1 + tan2 T)/(1 + cot2 T) = tan2 T [4 Marks]",
            "If sin T + cos T = sq2 cos T, prove that cos T - sin T = sq2 sin T. [4 Marks]",
            "If sin T = cos T, find the value of 2 tan T + cos2 T. [4 Marks]",
            "Prove: sinT/(1 - cosT) + sinT/(1 + cosT) = 2 cosecT [4 Marks]",
        ],
        "la": [
            "Prove that (sinA - cosecA)^2 + (cosA - secA)^2 = cot2 A + tan2 A - 1. [6 Marks]",
            "Prove: (sinT + cosT)(tanT + cotT) = secT + cosecT [6 Marks]",
            "If cosecT - sinT = m and secT - cosT = n, prove that (m^2 n)^(2/3) + (mn^2)^(2/3) = 1. [6 Marks]",
            "If tanA = n tanB and sinA = m sinB, prove that cos2 A = (m^2 - 1)/(n^2 - 1). [6 Marks]",
            "Prove: cosA/(1 - tanA) + sinA/(1 - cotA) = sinA + cosA [6 Marks]",
            "If x = a secT + b tanT and y = a tanT + b secT, prove that x^2 - y^2 = a^2 - b^2. [6 Marks]",
        ],
        "app": [
            ("Verify the three fundamental identities for T = 30 deg, 45 deg and 60 deg.",
             ["Calculate sin2(30)+cos2(30), and comment.", "Calculate 1+tan2(45) and sec2(45) and compare.", "Calculate 1+cot2(60) and cosec2(60) and compare.", "State the three identities proved."]),
            ("Evaluate without using tables:",
             ["sin2 30 + cos2 60", "cos2 45 + sin2 30 + sin2 60", "sin30 cos60 + cos30 sin60", "(tan2 60 - tan2 45)/(1 + tan2 60 tan2 45)"]),
        ],
    },
    "applications of trigonometry": {
        "concepts": [
            "Angle of elevation: angle measured upward from horizontal to line of sight",
            "Angle of depression: angle measured downward from horizontal to line of sight",
            "Height and distance problems using tan T = opposite/adjacent",
            "Problems with two angles of elevation from two positions",
            "Problems with an observer at a height above ground",
            "Use of sq3 = 1.732 in numerical answers",
        ],
        "mcq": [
            ("The angle of elevation of the top of a tower from a point 20 m away is 45 deg. Height of tower is", ["20 m","10 m","40 m","20sq3 m"], 0),
            ("A ladder 10 m long makes 60 deg with the ground. Height reached on the wall is", ["5sq3 m","5 m","10 m","5sq2 m"], 0),
            ("Angle of depression of a boat from top of 50 m cliff is 30 deg. Distance of boat from base is", ["50sq3 m","50 m","100 m","25sq3 m"], 0),
            ("Shadow of a 6 m pole is 6sq3 m. Angle of elevation of sun is", ["30 deg","45 deg","60 deg","90 deg"], 0),
            ("A kite flies at 60 m. String makes 60 deg with horizontal. String length is", ["40sq3 m","60sq2 m","120 m","40 m"], 0),
            ("From top of 50 m tower, angle of depression of point is 45 deg. Distance of point from base is", ["50 m","25 m","100 m","50sq3 m"], 0),
            ("Pole casts 2sq3 m shadow when sun elevation is 60 deg. Height of pole is", ["6 m","2 m","4 m","2sq3 m"], 0),
            ("From a point 40 m from base, elevation of top of pole is 30 deg. Height of pole is", ["40/sq3 m","40sq3 m","20 m","80 m"], 0),
            ("Observer 1.5 m tall, 28.5 m from building, elevation of top is 45 deg. Building height is", ["30 m","28.5 m","31.5 m","29 m"], 0),
            ("From top of cliff 150 m high, depression of ship is 30 deg. Distance of ship from base is", ["150sq3 m","150 m","75sq3 m","300 m"], 0),
        ],
        "fill": [
            "The angle of elevation is measured __________ from the horizontal line of sight",
            "The angle of depression is measured __________ from the horizontal line of sight",
            "If angle of elevation of sun is 45 deg, shadow of a pole equals __________ its height",
            "tan(angle of elevation) = height / __________",
            "When the angle of depression equals the angle of elevation, the two points are at __________ height",
        ],
        "match_a": ["Angle of elevation", "Angle of depression", "tan 30 deg", "tan 60 deg", "tan 45 deg"],
        "match_b": ["1", "1/sq3", "sq3", "Angle above horizontal", "Angle below horizontal"],
        "vsq": [
            "From a point 15 m away, angle of elevation of top of a tower is 60 deg. Find height. [2 Marks]",
            "A ladder 10 m leans against a wall at 30 deg with the wall. Find distance of foot from wall. [2 Marks]",
            "Angle of depression of car from top of 50 m cliff is 30 deg. Find distance of car from base. [2 Marks]",
            "From a point, angles of elevation of bottom and top of a transmission tower on a 20 m building are 45 deg and 60 deg. Find tower height. [2 Marks]",
            "A 1.5 m boy stands from a 30 m building with angle of elevation 30 deg. Find his distance from building. [2 Marks]",
            "A kite flies at 75 m. String makes 60 deg with horizontal. Find length of string. [2 Marks]",
            "Shadow of a building is 20 m when sun elevation is 60 deg. Find height of building. [2 Marks]",
            "From a 7 m building, elevation of top of tower is 60 deg and depression of foot is 45 deg. Find height of tower. [2 Marks]",
            "Two poles of equal height stand 80 m apart. From a point between them, elevations are 60 deg and 30 deg. Find height of poles. [2 Marks]",
            "A statue 1.6 m stands on a pedestal. Elevation of top of statue is 60 deg and of top of pedestal is 45 deg. Find height of pedestal. [2 Marks]",
        ],
        "sa": [
            "From top of a hill, angles of depression of two consecutive km stones due east are 45 deg and 30 deg. Find height of hill. [4 Marks]",
            "Two ships on either side of 200 m lighthouse. Angles of depression are 60 deg and 45 deg. Find distance between ships. [4 Marks]",
            "A man on deck 10 m above water observes top of hill at 60 deg elevation and base at 30 deg depression. Find distance and height of hill. [4 Marks]",
            "Angles of elevation of a tower from points P and Q, 4 m and 9 m from base, are complementary. Find height. [4 Marks]",
            "From two points A and B on same side of tower, elevations are 30 deg and 60 deg. AB = 48 m. Find height of tower. [4 Marks]",
            "A boy at A observes top of building at 60 deg. Walks 40 m to B, angle becomes 75 deg. Find height of building. [4 Marks]",
        ],
        "la": [
            "A man on tower observes car at 30 deg depression. Six seconds later angle is 60 deg. Find time for car to reach base. [6 Marks]",
            "Elevation of jet from point A due north is 60 deg. From B due west of A, it is 30 deg. AB = 1800 m. Find height of jet. [6 Marks]",
            "From window 10 m above street, elevation of top of building across is 60 deg and depression of foot is 45 deg. Find width of road and height of building. [6 Marks]",
            "A round balloon of radius r subtends angle a at eye of observer. Elevation of centre is T. Prove distance of centre = r cosecT sin(a/2). [6 Marks]",
            "Two poles AB and CD of heights a and b stand on ground. P between them: angles of elevation of tops are equal. Find height and position of P. [6 Marks]",
            "From a point P on ground, elevation of top of tower is T. On walking a metres towards tower, elevation is phi. Prove height = a tanT tan phi / (tan phi - tanT). [6 Marks]",
        ],
        "app": [
            ("A student uses angles of elevation from two points to find building height.",
             ["Draw a neat labelled diagram showing points A, B and the building.", "From A the angle is 30 deg and from B (20 m closer) it is 60 deg. Find height of building.", "Find distance of B from base.", "Verify distance AB = 20 m using your answers."]),
            ("A lighthouse 80 m tall. Two boats on opposite sides. Angles of depression 45 deg and 30 deg.",
             ["Draw a neat labelled diagram.", "Find distance of boat 1 from base.", "Find distance of boat 2 from base.", "Find total distance between the two boats."]),
        ],
    },
    "similar triangles": {
        "concepts": [
            "Basic Proportionality Theorem (Thales): DE || BC => AD/DB = AE/EC",
            "Converse of BPT",
            "AA, SSS, SAS similarity criteria",
            "Ratio of areas of similar triangles = square of ratio of corresponding sides",
            "Pythagoras theorem and its converse",
            "Altitude on hypotenuse of right triangle creates similar triangles",
        ],
        "mcq": [
            ("In △ABC, DE || BC. If AD=3 cm, DB=6 cm, AE=4 cm, then EC is", ["8 cm","6 cm","2 cm","12 cm"], 0),
            ("Ratio of areas of two similar triangles is 25:36. Ratio of corresponding sides is", ["5:6","25:36","6:5","sq25:sq36"], 0),
            ("△ABC~△PQR and AB/PQ=2/3. Ratio Area(ABC):Area(PQR) is", ["4:9","2:3","9:4","3:2"], 0),
            ("Which criterion CANNOT prove similarity?", ["RHS","AA","SSS","SAS"], 0),
            ("Hypotenuse 13 cm, one side 5 cm. Third side is", ["12 cm","8 cm","10 cm","11 cm"], 0),
            ("Perimeters of similar triangles are 30 cm and 20 cm. Side of first is 12 cm. Corresponding side of second is", ["8 cm","10 cm","15 cm","6 cm"], 0),
            ("△ABC~△DEF, angle A=47 deg, angle E=83 deg. Angle C equals", ["50 deg","47 deg","83 deg","90 deg"], 0),
            ("A 6 m pole casts 4 m shadow. Tower casts 28 m shadow. Height of tower is", ["42 m","36 m","24 m","18 m"], 0),
            ("In △PQR, PS=2 cm, PQ=6 cm, ST||QR. Ratio PT:TR is", ["1:2","2:1","1:3","3:1"], 0),
            ("Ratio of areas of two similar triangles is 16:25. Ratio of altitudes is", ["4:5","16:25","2:5","8:25"], 0),
        ],
        "fill": [
            "If DE || BC in triangle ABC, then AD/DB = __________ (BPT)",
            "Ratio of areas of similar triangles = ratio of __________ of corresponding sides",
            "In a right triangle, square of hypotenuse = __________ of squares of other two sides",
            "If △ABC~△PQR, AB=3 cm, PQ=6 cm, ratio of perimeters is __________",
            "All congruent figures are similar but similar figures are not necessarily __________",
        ],
        "match_a": ["Basic Proportionality Theorem", "Area theorem for similar triangles", "Pythagoras theorem", "AAA similarity", "Altitude on hypotenuse"],
        "match_b": ["All three angles equal", "AD/DB = AE/EC", "c^2 = a^2 + b^2", "Area ratio = (side ratio)^2", "Creates triangles similar to original"],
        "vsq": [
            "In △PQR, ST||QR. PS=x, SQ=x-2, PT=x+2, TR=x-1. Find x. [2 Marks]",
            "△ABC: angle A=50, angle B=60. △DEF: angle D=50, angle F=70. Are they similar? State criterion. [2 Marks]",
            "Areas of two similar triangles are 100 cm2 and 49 cm2. Side of larger is 15 cm. Find corresponding side of smaller. [2 Marks]",
            "In right-angled △ABC at B, AB=8 cm, BC=6 cm. Find AC. [2 Marks]",
            "△ABC~△PQR, perimeters 48 cm and 32 cm. Find ratio of corresponding medians. [2 Marks]",
            "D on AB, E on AC: AD=5, DB=10, AE=4, EC=8. Show DE||BC. [2 Marks]",
            "Girl height 90 cm walks from 3.6 m lamp at 1.2 m/s. Find shadow length after 4 s. [2 Marks]",
            "In △PQR, MN||QR. PM=4, MQ=6, PN=2. Find NR. [2 Marks]",
            "Isosceles △ABC right-angled at C. Prove AB^2 = 2AC^2. [2 Marks]",
            "State AAA similarity criterion for triangles. [2 Marks]",
        ],
        "sa": [
            "Prove BPT: line parallel to one side divides other two sides in same ratio. [4 Marks]",
            "ABCD trapezium, AD||BC, diagonals meet at O. Prove AO/OC = BO/OD. [4 Marks]",
            "△PQR right-angled at P, M on QR, PM perpendicular to QR. Show PM^2 = QM x MR. [4 Marks]",
            "Areas of △ABC and △PQR are 64 cm2 and 121 cm2. QR=15.4 cm. Find BC. [4 Marks]",
            "D on BC of △ABC with angle ADC = angle BAC. Show CA^2 = CB x CD. [4 Marks]",
            "AD is altitude of △ABC. AD^2 = BD x CD. Prove △ABC is right-angled at A. [4 Marks]",
        ],
        "la": [
            "State and prove Basic Proportionality Theorem with neat diagram. [6 Marks]",
            "State and prove converse of BPT. [6 Marks]",
            "Prove: ratio of areas of similar triangles = ratio of squares of corresponding sides. [6 Marks]",
            "State and prove Pythagoras theorem with neat diagram. [6 Marks]",
            "In △ABC, AD median, E midpoint of AD, BE produced meets AC at F. Prove AF = (1/3)AC. [6 Marks]",
            "ABCD trapezium AB||DC, diagonals meet at O, EF through O parallel to AB. Prove EO = FO. [6 Marks]",
        ],
        "app": [
            ("Construct △ABC: BC=6 cm, AB=5 cm, angle ABC=60 deg. Construct similar triangle with sides (3/4) of △ABC.",
             ["Draw △ABC with given measurements. Write all steps.", "Mark ray BX at acute angle to BC.", "Mark 4 equal parts on BX, join B4 to C.", "Draw B3C' parallel to B4C. Draw C'A' parallel to CA. Measure and state ratio of sides."]),
            ("A 1.6 m girl stands 3.2 m from lamp post, shadow 4.8 m.",
             ["Draw a neat labelled diagram.", "Identify the two similar triangles and state why they are similar.", "Set up the proportion and find height of lamp post.", "Verify your answer."]),
            ("In △ABC, right angle at B. D on AB, E on BC. Prove AE^2 + CD^2 = AC^2 + DE^2.",
             ["Draw a neat diagram.", "Apply Pythagoras in right △ABE.", "Apply Pythagoras in right △DBC.", "Add the equations and simplify to get the result."]),
        ],
    },
    "tangents and secants to a circle": {
        "concepts": [
            "Tangent to a circle: perpendicular to radius at point of contact",
            "Length of tangent from external point = sqrt(d^2 - r^2)",
            "Two tangents from an external point are equal in length",
            "Angle between tangent and chord = angle in alternate segment",
            "Secant-tangent relation: PA^2 = PB x PC",
            "Quadrilateral circumscribing a circle: AB + CD = BC + DA",
        ],
        "mcq": [
            ("Tangent to a circle is __________ to the radius at point of contact", ["perpendicular","parallel","equal","bisecting"], 0),
            ("From point 13 cm from centre, radius 5 cm. Tangent length is", ["12 cm","8 cm","10 cm","13 cm"], 0),
            ("Two tangents PA and PB from P. PA = 10 cm. PB equals", ["10 cm","5 cm","20 cm","15 cm"], 0),
            ("If angle APB = 80 deg (tangents PA PB), then angle AOB equals", ["100 deg","80 deg","40 deg","160 deg"], 0),
            ("Number of tangents from a point inside a circle is", ["0","1","2","infinite"], 0),
            ("TP and TQ tangents from T, angle PTQ = 70 deg. Angle POQ equals", ["110 deg","70 deg","140 deg","35 deg"], 0),
            ("Tangent PT and secant PAB from P: PA=4 cm, PB=9 cm. PT equals", ["6 cm","5 cm","36 cm","13 cm"], 0),
            ("Circle touches all four sides of quadrilateral ABCD. AB=12, CD=8, BC=10. AD equals", ["10 cm","6 cm","8 cm","14 cm"], 0),
            ("Two concentric circles radii 5 cm and 3 cm. Length of chord of outer tangent to inner circle is", ["8 cm","4 cm","6 cm","10 cm"], 0),
            ("Angle between tangent to circle and chord through contact point equals angle in", ["alternate segment","same segment","semicircle","major segment"], 0),
        ],
        "fill": [
            "The tangent to a circle is __________ to the radius at the point of contact",
            "Two tangents drawn from an external point to a circle are __________ in length",
            "From a point 5 cm from a circle of radius 3 cm, tangent length = __________",
            "PA^2 = PB x PC where PA is tangent and PBC is a __________ from P",
            "If a quadrilateral circumscribes a circle: AB + CD = __________",
        ],
        "match_a": ["Tangent-radius relationship", "Tangents from external point", "Tangent-chord angle", "Secant-tangent theorem", "Cyclic quadrilateral circumscribing circle"],
        "match_b": ["AB + CD = BC + DA", "PA^2 = PB x PC", "Angle in alternate segment", "Equal lengths", "90 degrees"],
        "vsq": [
            "Find tangent length from point 13 cm from centre of circle of radius 5 cm. [2 Marks]",
            "PA and PB tangents from P to circle. PA = 10 cm. Find PB. State the theorem used. [2 Marks]",
            "OQ = 13 cm, radius = 5 cm, PQ tangent at P. Find PQ. [2 Marks]",
            "Two concentric circles radii 5 cm and 3 cm. Find length of chord of outer tangent to inner. [2 Marks]",
            "State and prove: tangent is perpendicular to radius at point of contact. [2 Marks]",
            "Tangent PT and secant PAB from P: PA=6, PB=4. Find PB and PC. [2 Marks]",
            "Quadrilateral ABCD circumscribes circle. AB=12, BC=10, CD=8. Find AD. [2 Marks]",
            "PA and PB tangents from P. Angle APB = 70 deg. Find angle AOB. [2 Marks]",
            "Chord of circle of radius 10 cm makes 30 deg at centre. Find tangent length at one end. [2 Marks]",
            "Tangent PT and secant PAB from P: PT=8 cm, PA=4 cm. Find AB. [2 Marks]",
        ],
        "sa": [
            "Prove tangents from an external point to a circle are equal in length. [4 Marks]",
            "Circle inscribed in △ABC touches BC at D, CA at E, AB at F. AB=12, BC=8, CA=10. Find AF, BD, CE. [4 Marks]",
            "Prove: if two circles touch internally/externally, point of contact lies on line joining centres. [4 Marks]",
            "PA and PB tangents from P. Prove angle APB + angle AOB = 180 deg. [4 Marks]",
            "Tangent PT and secant PAB from external P. Prove PT^2 = PA x PB. [4 Marks]",
            "Two tangents PA and PB from P to circle, angle APB = 60 deg, radius = r. Find OP and tangent length. [4 Marks]",
        ],
        "la": [
            "State and prove: tangent at any point of circle is perpendicular to radius through that point. [6 Marks]",
            "State and prove: tangents from external point are equal. Draw neat diagram. [6 Marks]",
            "Prove: if circle touches all four sides of quadrilateral, sum of opposite sides are equal. [6 Marks]",
            "Prove: angle between tangent to circle and chord through contact = angle in alternate segment. [6 Marks]",
            "Draw tangents to circle of radius 4 cm from point 8 cm away. Write steps and find tangent length. [6 Marks]",
            "Two tangents PA and PB from P, angle between them 60 deg, radius r. Find OP, tangent length, and area of quadrilateral PAOB. [6 Marks]",
        ],
        "app": [
            ("Circle of radius 5 cm inscribed in right triangle with sides 12 cm, 13 cm, 5 cm.",
             ["Find tangent lengths from each vertex using tangent properties.", "Verify tangent lengths add to side lengths correctly.", "Find area of triangle using base and height.", "Verify: Area = inradius x semi-perimeter. What is the inradius here?"]),
            ("Two circles of radii 7 cm and 3 cm touch externally.",
             ["Draw the configuration and mark all tangent lines.", "Find length of common external tangent.", "Find length of common internal tangent.", "Find distance between centres and verify."]),
        ],
    },
    "mensuration": {
        "concepts": [
            "Surface area and volume: cube, cuboid, cylinder, cone, sphere, hemisphere",
            "Frustum of cone: l = sqrt(h^2+(r1-r2)^2), LSA = pi(r1+r2)l, V = (pi*h/3)(r1^2+r2^2+r1*r2)",
            "Combination of solids (cone + cylinder, hemisphere + cylinder, etc.)",
            "Conversion of solids: melting and recasting -- volumes are equal",
            "Cost problems: cost = rate x area or volume",
        ],
        "mcq": [
            ("Volume of sphere of radius r is", ["(4/3)pi*r^3","(2/3)pi*r^3","4*pi*r^2","pi*r^3"], 0),
            ("CSA of cone of radius r and slant height l is", ["pi*r*l","pi*r^2","2*pi*r*l","pi*r*(r+l)"], 0),
            ("TSA of cylinder of radius r height h is", ["2*pi*r*(r+h)","2*pi*r*h","pi*r^2*h","pi*r*(r+2h)"], 0),
            ("Volume of hemisphere of radius r is", ["(2/3)pi*r^3","(4/3)pi*r^3","(1/3)pi*r^3","(3/2)pi*r^3"], 0),
            ("Volume of cone of radius r and height h is", ["(1/3)pi*r^2*h","pi*r^2*h","(2/3)pi*r^3","(1/2)pi*r^2*h"], 0),
            ("Slant height of frustum: h=8, r1=10, r2=6. Slant height l is", ["sqrt(80)","sqrt(100)","sqrt(116)","10"], 0),
            ("TSA of hemisphere of radius r is", ["3*pi*r^2","2*pi*r^2","4*pi*r^2","pi*r^2"], 0),
            ("A solid sphere of radius 3 cm melted into small spheres of radius 0.5 cm. Number of small spheres is", ["216","27","72","108"], 0),
            ("Volume of frustum: r1=6, r2=3, h=4. Volume is", ["84*pi","76*pi","36*pi","108*pi"], 0),
            ("Cylinder r=7 cm, h=20 cm. Volume (pi=22/7) is", ["3080 cm3","2200 cm3","4400 cm3","1540 cm3"], 0),
        ],
        "fill": [
            "Volume of a sphere = __________",
            "Curved surface area of a cone = __________",
            "Volume of frustum = (pi*h/3)(r1^2 + r2^2 + r1*r2) where h is the __________",
            "Total surface area of a hemisphere = __________",
            "When one solid is melted and recast as another, their __________ remain equal",
        ],
        "match_a": ["Volume of sphere", "CSA of cylinder", "Volume of cone", "TSA of hemisphere", "CSA of cone"],
        "match_b": ["pi*r*l", "3*pi*r^2", "(1/3)*pi*r^2*h", "2*pi*r*h", "(4/3)*pi*r^3"],
        "vsq": [
            "Find volume of sphere of radius 7 cm. (pi=22/7) [2 Marks]",
            "Cone radius 7 cm, slant height 25 cm. Find CSA. [2 Marks]",
            "Cylinder radius 7 cm, height 20 cm. Find volume. [2 Marks]",
            "Hemisphere radius 10.5 cm. Find TSA. [2 Marks]",
            "Solid sphere radius 3 cm melted into small spheres radius 0.5 cm. Find number. [2 Marks]",
            "Frustum: r1=8, r2=4, h=6 cm. Find volume. [2 Marks]",
            "Cone: volume=1570 cm3, height=15 cm. Find radius. [2 Marks]",
            "Two spheres radii 1 cm and 6 cm melted into one. Find radius of new sphere. [2 Marks]",
            "Cuboid 8x5x3 cm melted to form cylinder radius 2 cm. Find height. [2 Marks]",
            "Metallic sphere radius 4.2 cm recast into cylinders radius 0.7 cm, height 2.4 cm. Find number. [2 Marks]",
        ],
        "sa": [
            "Solid = cone (height 12 cm, radius 3 cm) on hemisphere (radius 3 cm). Find TSA and volume. [4 Marks]",
            "Tent: cylindrical up to 3 m height, conical top slant height 5 m, diameter 14 m. Find canvas needed. [4 Marks]",
            "Bucket (frustum): radii 15 cm and 5 cm, depth 24 cm. Find capacity and metal sheet needed. [4 Marks]",
            "A wooden article: hemisphere scooped from each end of cylinder (h=10, r=3.5 cm). Find TSA. [4 Marks]",
        ],
        "la": [
            "Solid = cone (h=4 cm) on hemisphere (r=2.1 cm). Find volume and TSA of solid. [6 Marks]",
            "45 gulab jamuns, each = cylinder with 2 hemispherical ends, length 5 cm, diameter 2.8 cm. 30% syrup by volume. Find total syrup. [6 Marks]",
            "Frustum (r1=12, r2=3, h=12) full of ice cream for 10 children in cones (r=3, h=12) with hemispherical tops. Find depth of ice cream in each cone. [6 Marks]",
            "Water flows through cylindrical pipe (diameter 1.4 cm) at 3 km/h into rectangular tank 1.1m x 44cm. Time to fill 40 cm deep. [6 Marks]",
        ],
        "app": [
            ("A building = cuboid (8m x 6m x 4m) with conical top (r=4m, slant h=5m). Sheet metal needed.",
             ["Find TSA of cuboidal portion (exclude top face).", "Find CSA of cone.", "Find total sheet metal required.", "If sheet costs Rs 80 per m2, find total cost."]),
        ],
    },
    "statistics": {
        "concepts": [
            "Mean of grouped data: direct method, assumed mean method, step-deviation method",
            "Mode formula: l + [(f1-f0)/(2f1-f0-f2)] x h",
            "Median formula: l + [(n/2 - cf)/f] x h",
            "Ogive: less-than and more-than cumulative frequency curves",
            "Empirical relation: Mode = 3 Median - 2 Mean",
        ],
        "mcq": [
            ("Class mark of class interval 10-20 is", ["15","10","20","12.5"], 0),
            ("Mean of first 10 natural numbers is", ["5.5","5","10","6"], 0),
            ("In mode formula l+[(f1-f0)/(2f1-f0-f2)]xh, f1 is", ["frequency of modal class","frequency before modal class","frequency after modal class","total frequency"], 0),
            ("In median formula, cf stands for", ["cumulative frequency before median class","class frequency","cumulative frequency of median class","total frequency"], 0),
            ("Empirical relation between mean, median and mode is", ["Mode = 3 Median - 2 Mean","Mode = 2 Median - 3 Mean","Mean = 3 Mode - 2 Median","Median = 3 Mode - 2 Mean"], 0),
            ("If mean=25 and mode=22, then median is", ["24","23","25","26"], 0),
            ("A less-than ogive is drawn using", ["upper class limits","lower class limits","class marks","mid-values"], 0),
            ("Modal class for data 0-10(f=5), 10-20(f=12), 20-30(f=8), 30-40(f=3) is", ["10-20","20-30","0-10","30-40"], 0),
            ("For median, n/2 = 20, cf = 14, f = 12, l = 30, h = 10. Median is", ["35","30","34","40"], 0),
            ("An ogive is a graph of", ["cumulative frequency","frequency","relative frequency","class marks"], 0),
        ],
        "fill": [
            "Class mark of 20-30 is __________",
            "Mode = 3 Median - __________ x Mean",
            "In median formula, h is the __________",
            "If mean=25 and mode=22, then median = __________",
            "An ogive is a __________ frequency curve",
        ],
        "match_a": ["Direct method", "Step-deviation method", "Mode formula", "Median formula", "Empirical relation"],
        "match_b": ["Mode = 3 Median - 2 Mean", "l + [(f1-f0)/(2f1-f0-f2)]xh", "l + [(n/2-cf)/f]xh", "Sum(fi*xi)/Sum(fi)", "Sum(fi*ui)/Sum(fi) x h + a"],
        "vsq": [
            "Find mean of 5, 10, 15, 20, 25. [2 Marks]",
            "Find mode of: 2, 3, 5, 2, 7, 3, 2. [2 Marks]",
            "Mean=30, Median=27. Find mode using empirical formula. [2 Marks]",
            "Find class marks of intervals: 0-8, 8-16, 16-24, 24-32. [2 Marks]",
            "Modal class: l=20, f0=5, f1=8, f2=3, h=10. Find mode. [2 Marks]",
            "Median: l=25, n/2=20, cf=15, f=10, h=5. Find median. [2 Marks]",
            "Find mean by step-deviation: 0-10(f=5), 10-20(f=10), 20-30(f=15). a=15, h=10. [2 Marks]",
            "Mode=36, Mean=30. Find median using empirical relation. [2 Marks]",
            "n=40, cumulative frequencies: 5, 15, 25, 35, 40. Identify the median class. [2 Marks]",
            "Define: (a) class mark (b) modal class (c) cumulative frequency [2 Marks]",
        ],
        "sa": [
            "Find mean weight: 40-45(f=5), 45-50(f=15), 50-55(f=20), 55-60(f=8), 60-65(f=2). Use assumed mean method. [4 Marks]",
            "Find mode: 0-20(f=5), 20-40(f=10), 40-60(f=12), 60-80(f=9), 80-100(f=4). [4 Marks]",
            "Find median of marks: 0-10(5), 10-20(10), 20-30(25), 30-40(30), 40-50(15), 50-60(10), 60-70(5). [4 Marks]",
            "Draw less-than ogive: 0-10(5), 10-20(8), 20-30(12), 30-40(10), 40-50(5). [4 Marks]",
        ],
        "la": [
            "Find mean, median and mode for: 0-20(6), 20-40(8), 40-60(10), 60-80(9), 80-100(7). Verify empirical relation. [6 Marks]",
            "Draw less-than and more-than ogives and find median from their intersection for: 10-20(5), 20-30(8), 30-40(20), 40-50(15), 50-60(7), 60-70(5). [6 Marks]",
        ],
        "app": [
            ("Daily wages of 50 workers given in table. Find:",
             ["Mean wage by step-deviation method.", "Modal wage (identify modal class, apply formula).", "Median wage using formula.", "Verify empirical relation: Mode ~= 3 Median - 2 Mean."]),
        ],
    },
    "probability": {
        "concepts": [
            "Classical probability = number of favourable outcomes / total equally likely outcomes",
            "Complementary events: P(E) + P(not E) = 1",
            "Range: 0 <= P(E) <= 1; impossible event P=0, certain event P=1",
            "Sample space for dice, coins, cards, numbered balls",
            "Events involving two dice, two coins simultaneously",
        ],
        "mcq": [
            ("A die thrown once. Probability of a prime number is", ["1/2","1/3","2/3","1/6"], 0),
            ("Card drawn from 52. Probability of a red ace is", ["1/26","1/13","2/52","1/52"], 0),
            ("Two coins tossed. Probability of at least one head is", ["3/4","1/4","1/2","2/4"], 0),
            ("Probability of number > 4 on a die is", ["1/3","2/3","1/6","1/2"], 0),
            ("Bag has 3 red, 4 blue balls. Probability of drawing red is", ["3/7","4/7","3/4","1/2"], 0),
            ("Cards 1-25 shuffled. Probability of a multiple of 5 is", ["1/5","5/25","4/25","6/25"], 0),
            ("Two dice thrown. Probability of sum = 7 is", ["1/6","7/36","6/36","5/36"], 0),
            ("Letters of MATHEMATICS on cards. Probability of a vowel is", ["4/11","5/11","3/11","2/5"], 0),
            ("Probability of getting a face card from 52 is", ["3/13","1/13","12/52","4/13"], 0),
            ("A bag has 5 red, 7 blue, 3 green. One drawn. Probability of not blue is", ["8/15","7/15","5/15","1/3"], 0),
        ],
        "fill": [
            "Probability of an impossible event is __________",
            "P(E) + P(not E) = __________",
            "Probability of a certain event is __________",
            "Total number of outcomes when a die is rolled = __________",
            "Probability that drawn card from 52 is a king = __________",
        ],
        "match_a": ["Probability range", "Complementary events", "Impossible event", "Certain event", "Classical probability"],
        "match_b": ["Favourable/Total outcomes", "P = 0", "P = 1", "0 <= P <= 1", "P(E) + P(E') = 1"],
        "vsq": [
            "A die thrown. P(number < 3) and P(factor of 6). [2 Marks]",
            "Card drawn from 52. P(king) and P(red card). [2 Marks]",
            "Two coins tossed. P(two heads) and P(at least one tail). [2 Marks]",
            "Bag has 5 red, 7 blue. Ball drawn. P(red) and P(not red). [2 Marks]",
            "Number chosen from 1-20. P(prime) and P(composite). [2 Marks]",
            "Die thrown twice. P(same number both times). [2 Marks]",
            "Cards 1-25 shuffled. Card drawn. P(multiple of 5). [2 Marks]",
            "Wheel numbered 1-10 spun. P(even), P(prime), P(multiple of 3). [2 Marks]",
            "From 52 cards: P(heart) and P(face card). [2 Marks]",
            "MATHEMATICS letters on cards. Card picked. P(vowel). [2 Marks]",
        ],
        "sa": [
            "Cards numbered 1-50. P(prime), P(multiple of 7), P(perfect square), P(two-digit number). [4 Marks]",
            "Die thrown once. P(prime), P(not prime), P(odd prime), P(factor of 12). [4 Marks]",
            "Two dice thrown. P(sum=7), P(sum>=10), P(doublet), P(sum<5). [4 Marks]",
            "Cards of one suit removed from 52. From remaining: P(red card), P(king), P(queen of removed suit). [4 Marks]",
        ],
        "la": [
            "From 52 well-shuffled cards: P(face card), P(not face card), P(red face card), P(black king), P(diamond), P(numbered card). [6 Marks]",
            "Box has discs 1-90. P(two-digit), P(perfect square), P(divisible by 5), P(not divisible by 10). [6 Marks]",
        ],
        "app": [
            ("Spinner has 8 equal sectors numbered 1-8.",
             ["List the complete sample space.", "Find P(prime number on spinner).", "Find P(factor of 8).", "Are the events 'prime' and 'factor of 8' mutually exclusive? Explain with working."]),
        ],
    },
}


def _get_chapter_bank(chap: str) -> dict:
    """Return content bank for given chapter.
    Strategy: exact match first, then longest-key substring match (prevents
    'trigonometry' matching 'applications of trigonometry')."""
    cl = chap.lower().strip()
    # 1. Exact match
    if cl in _MATH_CHAPTER_TOPICS:
        return _MATH_CHAPTER_TOPICS[cl]
    # 2. Check if chap IS a key (case-insensitive already handled above)
    # 3. Longest-key-first substring: the INPUT must contain the key
    #    (e.g. "applications of trigonometry" contains "trigonometry" but we
    #     want to match it to its specific longer key first)
    keys_longest_first = sorted(_MATH_CHAPTER_TOPICS.keys(), key=len, reverse=True)
    for key in keys_longest_first:
        if key in cl:  # key is substring of chapter name
            return _MATH_CHAPTER_TOPICS[key]
    # 4. Key contains chapter name as substring
    for key in keys_longest_first:
        if cl in key:
            return _MATH_CHAPTER_TOPICS[key]
    # 5. Word overlap fallback
    chap_words = set(cl.split())
    best_key, best_score = None, 0
    for key in _MATH_CHAPTER_TOPICS:
        score = len(chap_words & set(key.split()))
        if score > best_score:
            best_score, best_key = score, key
    return _MATH_CHAPTER_TOPICS.get(best_key, {}) if best_score >= 1 else {}


def _build_math_guidance(chap, cls_str, board, bank):
    """Build fully-expanded subject guidance with real sample questions."""
    if not bank:
        return (f"SUBJECT: Mathematics  |  CHAPTER: {chap}  |  Class {cls_str}  |  {board}\n\n"
                f"TOPIC RULE: Every question MUST be exclusively about \"{chap}\" as per {board} "
                f"Class {cls_str} textbook. Any off-topic question = paper rejected.\n\n"
                f"Cover: definitions, formulae, theorems, numericals, proofs, applications "
                f"within \"{chap}\" only.\nNumericals: Formula -> Substitution -> Steps -> Answer with unit.\n"
                f"Proofs: Given / To Prove / Steps with Reasons numbered.\n"
                f"MCQ options: all 4 distinct, plausible from student errors.")

    concepts_str = "\n".join(f"  * {c}" for c in bank["concepts"])

    # MCQ samples
    mcq_lines = []
    for i, (stem, opts, ans) in enumerate(bank["mcq"]):
        opt_str = "   ".join(f"({chr(65+j)}) {o}" for j, o in enumerate(opts))
        mcq_lines.append(f"  {i+1}. {stem} [1 Mark]\n     {opt_str}   (   )")
    mcq_block = "\n".join(mcq_lines)

    # Fill blank samples
    fill_block = "\n".join(f"  {i+11}. {q} [1 Mark]" for i, q in enumerate(bank["fill"]))

    # Match samples
    match_block = "  | Group A | Group B |\n  |---|---|\n"
    match_block += "\n".join(f"  | {a} | {b} |" for a, b in zip(bank["match_a"], bank["match_b"]))

    # VSQ samples
    vsq_block = "\n".join(f"  {i+1}. {q}" for i, q in enumerate(bank["vsq"]))

    # SA samples
    sa_block = "\n".join(f"  {i+11}. {q}" for i, q in enumerate(bank["sa"]))

    # LA samples
    la_pairs = []
    for i, q in enumerate(bank["la"]):
        n = 17 + i
        la_pairs.append(f"  {n}. (i) {q}\n       OR\n      (ii) [Alternative {chap} proof/problem] [6 Marks]")
    la_block = "\n".join(la_pairs)

    # App samples
    app_lines = []
    for i, item in enumerate(bank["app"]):
        n = 23 + i
        if isinstance(item, tuple):
            intro, parts = item
            sub = "\n".join(f"       ({chr(97+j)}) {p}" for j, p in enumerate(parts))
            app_lines.append(f"  {n}. {intro} [10 Marks]\n{sub}")
        else:
            app_lines.append(f"  {n}. {item} [10 Marks]")
    app_block = "\n".join(app_lines)

    return f"""SUBJECT: Mathematics  |  CHAPTER: {chap}  |  Class {cls_str}  |  {board}

CORE CONCEPTS TO COVER (spread across all sections):
{concepts_str}

ABSOLUTE TOPIC RULE:
  Every question in the paper (all 36 slots) MUST test "{chap}" ONLY.
  Questions from any other chapter will cause the paper to be REJECTED.

USE THESE READY QUESTION STARTERS (modify values/wording as needed):

-- SECTION I: MCQ (choose these 10, adjust numbers for difficulty) --
{mcq_block}

-- SECTION II: FILL IN THE BLANKS (use these 5) --
{fill_block}

-- SECTION III: MATCH THE FOLLOWING --
{match_block}

-- SECTION IV: VSQ (use these 10) --
{vsq_block}

-- SECTION V: SA (6 questions given) --
{sa_block}

-- SECTION VI: LA WITH OR (6 questions given) --
{la_block}

-- SECTION VII: APPLICATION (3 questions given) --
{app_block}

QUALITY RULES:
  * Numericals: Formula -> Substitution (show values + units) -> Steps -> Final answer
  * Proofs: Given | To Prove | Construction (if needed) | Numbered steps with Reasons
  * MCQ wrong options: answers from a specific named error, not random values
  * All 4 MCQ options must be numerically distinct"""


def _prompt_ap_ts_9_10(subject, chap, board, cls_str,
                        m, difficulty, extra, math_note, pat, user_marks=100):
    subj_l = (subject or "").lower()

    diff_mix = {
        "Easy":   "Bloom's: 50% Remember/Understand, 30% Apply, 20% Analyse",
        "Medium": "Bloom's: 25% Remember/Understand, 40% Apply, 25% Analyse, 10% Evaluate",
        "Hard":   "Bloom's: 10% Remember, 20% Understand, 35% Apply, 25% Analyse, 10% Evaluate",
    }.get(difficulty, "Bloom's: 25% Remember/Understand, 40% Apply, 25% Analyse, 10% Evaluate")

    if "math" in subj_l:
        bank = _get_chapter_bank(chap)
        subject_guidance = _build_math_guidance(chap, cls_str, board, bank)

    elif any(k in subj_l for k in ["physics","chemistry","science","biology"]):
        subject_guidance = (
            f"SUBJECT: {subject}  |  CHAPTER: {chap}  |  Class {cls_str}  |  {board}\n\n"
            f"TOPIC RULE: Every question MUST be exclusively about \"{chap}\".\n"
            f"* Numericals: Given -> Formula -> Substitution -> Working -> Answer with unit\n"
            f"* Chemical equations: balanced with state symbols (s) (l) (g) (aq)\n"
            f"* Diagrams: write [DIAGRAM: full description] only -- no extra text\n"
            f"* Section VII: full working required, no steps skipped")

    elif any(k in subj_l for k in ["social","history","geography","civics","economics"]):
        subject_guidance = (
            f"SUBJECT: {subject}  |  CHAPTER: {chap}  |  Class {cls_str}  |  {board}\n\n"
            f"TOPIC RULE: Every question must be about \"{chap}\" only.\n"
            f"* VSQ: one precise factual answer per mark\n"
            f"* SA: 4-5 distinct points, sub-headings helpful\n"
            f"* LA: intro -> 5-6 substantive points -> conclusion\n"
            f"* Section VII: include one map-marking question (5 specific items on outline map)")

    elif "english" in subj_l:
        subject_guidance = (
            f"SUBJECT: English  |  {board} Class {cls_str}\n"
            f"NOTE: English papers have NO Part A (no objective section).\n"
            f"Full 80-mark written paper:\n"
            f"  Section A -- Reading Comprehension (20 marks): unseen passage + 5 questions\n"
            f"  Section B -- Writing (20 marks): formal letter OR essay OR notice/report\n"
            f"  Section C -- Grammar (20 marks): gap-fill, transformation, editing\n"
            f"  Section D -- Literature (40 marks): prescribed {board} Class {cls_str} texts\n"
            f"DO NOT generate Part A for English.")

    else:
        subject_guidance = (
            f"SUBJECT: {subject}  |  CHAPTER: {chap}  |  Class {cls_str}  |  {board}\n"
            f"TOPIC RULE: Every question must be about \"{chap}\" as per the {board} Class {cls_str} textbook.")

    s = _compute_structure(user_marks)
    actual = s['total']
    if actual <= 30:
        time_str = "1 Hour"
    elif actual <= 60:
        time_str = "2 Hours"
    else:
        time_str = "3 Hours 15 Minutes"
    match_word = "pairs" if s['n_match'] != 1 else "pair"
    total_q = s['n_mcq'] + s['n_fill'] + 1 + s['n_vsq'] + s['n_sa_given'] + s['n_la_given'] + s['n_app_given']

    return f"""You are an experienced senior question-paper setter for {board} Class {cls_str} SSC.
You have 15+ years setting official board papers. Financial penalties apply for off-topic or mis-formatted papers.
Accuracy, topic adherence, and correct marks are non-negotiable.
{extra}
PAPER SPECIFICATION
Subject  : {subject}
Chapter  : {chap}
Class    : {cls_str}    Board: {board}
Total    : {actual} marks    Difficulty: {difficulty}
Cognitive: {diff_mix}

MANDATORY PAPER STRUCTURE -- MUST BE REPRODUCED EXACTLY:
PART A -- OBJECTIVE ({s['partA']} marks) -- collected after 30 minutes:
  Section I    {s['n_mcq']} MCQ x 1 mark = {s['mcq_marks']} marks  [Q1-Q{s['n_mcq']}]
  Section II   {s['n_fill']} Fill x 1 mark = {s['fill_marks']} marks  [Q{s['n_mcq']+1}-Q{s['n_mcq']+s['n_fill']}]
  Section III  1 Match ({s['n_match']} {match_word}) = {s['match_marks']} marks  [Q{s['n_mcq']+s['n_fill']+1}]
                              Subtotal = {s['partA']} marks

PART B -- WRITTEN ({s['partB']} marks):
  Section IV   {s['n_vsq']} VSQ ALL compulsory x 2 marks = {s['vsq_total']} marks  [Q{s['iv_start']}-Q{s['iv_end']}]
  Section V    {s['n_sa_given']} SA given, attempt any {s['n_sa_att']} x 4 marks = {s['sa_total']} marks  [Q{s['v_start']}-Q{s['v_end']}]
  Section VI   {s['n_la_given']} LA given, attempt any {s['n_la_att']} x 6 marks = {s['la_total']} marks  [Q{s['vi_start']}-Q{s['vi_end']}, each with OR]
  Section VII  {s['n_app_given']} Application, attempt any {s['n_app_att']} x {s['marks_per_app']} marks = {s['app_total']} marks  [Q{s['vii_start']}-Q{s['vii_end']}]
                              Subtotal = {s['partB']} marks
                         GRAND TOTAL = {actual} marks ✓

SUBJECT AND CHAPTER GUIDANCE:
{subject_guidance}
{math_note}

MANDATORY FORMAT RULES:
R1. MARKS TAG: Every question ends with the correct [N Marks] tag.
R2. MCQ: Exactly 4 options (A)(B)(C)(D). Last item on line is (   ).
    Example:  1. The value of sin 30 is [1 Mark]
              (A) 1/2   (B) 1   (C) sq3/2   (D) 1/sq2   (   )
R3. FILL-BLANK: Use ten underscores __________ for blank.
R4. MATCH: Pipe table, exactly {s['n_match']} data rows.
    | Group A | Group B |
    |---|---|
    | term1 | value1 |
    ... ({s['n_match']} rows total)
R5. LA: Every LA question MUST have an OR alternative.
R6. DIAGRAMS: [DIAGRAM: description] on its own line only. No other figure text.
R7. NO REPETITION: All {total_q} question slots unique.

VERIFY BEFORE OUTPUTTING:
  Section I   = exactly {s['n_mcq']} MCQ, each 4 options, ends (   )
  Section II  = exactly {s['n_fill']} fill-blanks
  Section III = exactly 1 match with {s['n_match']} rows
  Section IV  = exactly {s['n_vsq']} VSQ
  Section V   = exactly {s['n_sa_given']} SA
  Section VI  = exactly {s['n_la_given']} LA each with OR
  Section VII = exactly {s['n_app_given']} application questions
  ALL questions about "{chap}" -- zero from other chapters
  Marks: {s['mcq_marks']}+{s['fill_marks']}+{s['match_marks']}+{s['vsq_total']}+{s['sa_total']}+{s['la_total']}+{s['app_total']} = {actual}

ANSWER KEY FORMAT (write after all questions, on a new page):
Write "ANSWER KEY" then give complete solutions for all sections.
Full step-by-step working for Sections IV-VII.

BEGIN. No preamble. Write paper header then Part A directly.

{subject} -- {chap}
{board} | Class {cls_str}   Total Marks: {actual}   Time: {time_str}

PART A -- OBJECTIVE  ({s['partA']} Marks)
(Answer on this question paper itself. Hand in after 30 minutes.)

Section I -- Multiple Choice Questions  [1 Mark each]

"""


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