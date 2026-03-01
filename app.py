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
C_NAVY  = HexColor("#1a237e")
C_STEEL = HexColor("#1565c0")
C_BODY  = HexColor("#1a1a1a")
C_GREY  = HexColor("#546e7a")
C_LIGHT = HexColor("#e8eaf6")
C_RULE  = HexColor("#90a4ae")
C_MARK  = HexColor("#2e7d32")
C_KRED  = HexColor("#c62828")
C_KFILL = HexColor("#fff8f8")
C_STEP  = HexColor("#37474f")


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
      alignment=TA_CENTER, leading=22, spaceAfter=0, spaceBefore=0)
    S("PMeta",     fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_LEFT, leading=13, spaceAfter=0)
    S("PMetaR",    fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_RIGHT, leading=13, spaceAfter=0)
    S("PMetaC",    fontName=R, fontSize=9, textColor=C_BODY,
      alignment=TA_CENTER, leading=13, spaceAfter=0)
    S("SecBanner", fontName=B, fontSize=11, textColor=C_NAVY,
      leading=15, spaceAfter=0, spaceBefore=0)
    S("InstrHead", fontName=B, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, spaceBefore=4)
    S("Instr",     fontName=R, fontSize=9.5, textColor=C_BODY,
      leading=14, spaceAfter=2, leftIndent=18, firstLineIndent=-18)
    S("Q",         fontName=R, fontSize=11, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=17, spaceBefore=8, spaceAfter=2,
      leftIndent=26, firstLineIndent=-26)
    S("QCont",     fontName=R, fontSize=11, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=17, spaceBefore=1, spaceAfter=2, leftIndent=26)
    S("QSub",      fontName=R, fontSize=11, textColor=C_BODY,
      alignment=TA_JUSTIFY, leading=17, spaceBefore=3, spaceAfter=2,
      leftIndent=42, firstLineIndent=-16)
    S("Opt",       fontName=R, fontSize=10.5, textColor=C_BODY,
      leading=15, spaceAfter=0, leftIndent=0)
    S("KTitle",    fontName=B, fontSize=14, textColor=C_KRED,
      alignment=TA_CENTER, leading=18, spaceAfter=6, spaceBefore=0)
    S("KSec",      fontName=B, fontSize=10.5, textColor=C_KRED,
      leading=14, spaceAfter=2, spaceBefore=6)
    S("KQ",        fontName=B, fontSize=10.5, textColor=C_STEEL,
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
        canvas.setStrokeColor(C_NAVY)
        canvas.setLineWidth(1.5)
        canvas.line(LM, A4[1] - 12*mm, RM, A4[1] - 12*mm)
        canvas.setStrokeColor(C_RULE)
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
        ("BACKGROUND",    (0,0),(-1,-1), C_LIGHT),
        ("LINEBELOW",     (0,0),(-1,-1), 1.5, C_NAVY),
        ("LINETOP",       (0,0),(-1,-1), 0.4, C_RULE),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
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
        ("BACKGROUND",     (0,0),(-1,0),  C_LIGHT),
        ("TEXTCOLOR",      (0,0),(-1,0),  C_NAVY),
        ("FONTNAME",       (0,0),(-1,0),  B),
        ("GRID",           (0,0),(-1,-1), 0.4, C_RULE),
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
        ("BACKGROUND",    (0,0),(-1,-1), C_NAVY),
        ("TOPPADDING",    (0,0),(-1,-1), 9),
        ("BOTTOMPADDING", (0,0),(-1,-1), 9),
        ("LEFTPADDING",   (0,0),(-1,-1), 12),
        ("RIGHTPADDING",  (0,0),(-1,-1), 12),
    ]))

    left_meta  = "  |  ".join(x for x in [h_board, f"Class {h_class}" if h_class else ""] if x)
    right_meta = f"Total Marks: {h_marks}   |   Time: {h_time}"
    tbl_meta = Table(
        [[Paragraph(left_meta,  st["PMeta"]),
          Paragraph(right_meta, st["PMetaR"])]],
        colWidths=[PW*0.55, PW*0.45])
    tbl_meta.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_LIGHT),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))

    tbl_school = Table(
        [[Paragraph("School / Institution: " + "_"*34
                    + "   Date: " + "_"*12,
                    st["PMetaC"])]],
        colWidths=[PW])
    tbl_school.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), white),
        ("BOX",           (0,0),(-1,-1), 0.5, C_RULE),
        ("TOPPADDING",    (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
    ]))

    elems += [tbl_title, tbl_meta, tbl_school, Spacer(1, 8)]

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

        if _is_hrule(line):
            flush_opts()
            elems.append(HRFlowable(width="100%", thickness=0.4,
                                    color=C_RULE, spaceBefore=3, spaceAfter=3))
            continue

        if s.startswith('[DIAGRAM:') or s.lower().startswith('[draw'):
            flush_opts()
            label   = s.strip('[]')
            desc    = re.sub(r'^DIAGRAM:\s*', '', label, flags=re.I).strip()
            elems.append(Paragraph(f'<i>Figure: {desc}</i>', st["DiagLabel"]))

            drawing = None
            if diagrams:
                for d_key, d_svg in diagrams.items():
                    if d_svg and (d_key.lower() in desc.lower()
                                  or desc.lower() in d_key.lower()):
                        drawing = svg_to_rl_image(d_svg, width_pt=PW * 0.82)
                        break
                if drawing is None and desc in diagrams:
                    drawing = svg_to_rl_image(diagrams[desc], width_pt=PW * 0.82)

            if drawing is not None:
                elems.append(Spacer(1, 3))
                elems.append(drawing)
            else:
                box = Table([['']],  colWidths=[PW*0.7], rowHeights=[70])
                box.setStyle(TableStyle([
                    ('BOX',        (0,0),(-1,-1), 0.8, C_RULE),
                    ('BACKGROUND', (0,0),(-1,-1), HexColor('#f8f9fa')),
                ]))
                outer = Table([[box]], colWidths=[PW])
                outer.setStyle(TableStyle([
                    ('ALIGN',          (0,0),(-1,-1), 'CENTER'),
                    ('TOPPADDING',     (0,0),(-1,-1), 2),
                    ('BOTTOMPADDING',  (0,0),(-1,-1), 2),
                ]))
                elems.append(outer)
            elems.append(Spacer(1, 5))
            continue

        if _is_general_instr(s):
            flush_opts()
            in_instr = True
            elems.append(Spacer(1, 4))
            elems.append(Paragraph(f'<b>{s}</b>', st["InstrHead"]))
            continue

        if _is_sec_hdr(line) and not _is_general_instr(s):
            flush_opts()
            in_instr = False
            elems.append(Spacer(1, 7))
            elems.append(_sec_banner(s, st, PW))
            elems.append(Spacer(1, 5))
            continue

        if _is_instr_line(s):
            flush_opts()
            m_i = re.match(r'^(\d+)\.\s+(.+)$', s)
            if m_i:
                elems.append(Paragraph(
                    f'<b>{m_i.group(1)}.</b>  {_process(m_i.group(2))}',
                    st["Instr"]))
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
            mk_m = re.search(r'(\[\s*\d+\s*[Mm]arks?\s*\])\s*$', qbody)
            mark_tag = ''
            if mk_m:
                mark_tag = mk_m.group(1)
                qbody    = qbody[:mk_m.start()].strip()
            body_rl = _process(qbody)
            mark_rl = (f'  <font color="{C_MARK.hexval()}" size="9.5">'
                       f'<b>{mark_tag}</b></font>') if mark_tag else ''
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
                    ("BACKGROUND",    (0,0),(-1,-1), C_KFILL),
                    ("LINEBELOW",     (0,0),(-1,-1), 1.2, C_KRED),
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
                    f'<font color="{C_KRED.hexval()}"><b>{q_km.group(2)}.</b></font>'
                    f'  {body_rl}{mk_str}',
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
        preferred = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        ordered   = [p for p in preferred if any(p in n for n in models)]
        rest      = [n for n in models if not any(p in n for p in preferred)]
        _discovered_models = ordered + rest
        return _discovered_models
    except Exception:
        return ["gemini-1.5-flash", "gemini-pro"]


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
        "\nMATH NOTATION — wrap EVERY mathematical expression in $...$:\n"
        "  Superscripts:  $x^{2}$  $a^{3}$  $10^{-3}$  $v^{2}$        NOT: x2, a3\n"
        "  Subscripts:    $H_{2}O$  $v_{0}$  $x_{1}$                   NOT: H2O, v0\n"
        "  Fractions:     $\\frac{a}{b}$  $\\frac{1}{f}$  $\\frac{mv^{2}}{r}$\n"
        "  Square root:   $\\sqrt{2}$  $\\sqrt{34}$\n"
        "  Greek:         $\\theta$  $\\alpha$  $\\pi$  $\\omega$  $\\lambda$\n"
        "  Trig:          $\\sin\\theta$  $\\cos 60^{\\circ}$  $\\tan\\alpha$\n"
        "  Units in text: write 'm/s', 'kg', 'N', 'Ω' as plain text outside $\n"
        "  Fill-in-blank: use __________ (plain underscores, no backslash)\n"
    )


# ═══════════════════════════════════════════════════════════════════════
# PROMPT BUILDER — routes to AP/TS or Competitive
# ═══════════════════════════════════════════════════════════════════════
def _class_int(cls_str):
    m = re.search(r'\d+', str(cls_str or "10"))
    return int(m.group()) if m else 10


def build_prompt(class_name, subject, chapter, board, exam_type, difficulty, marks, suggestions):
    m       = max(10, int(marks) if str(marks).isdigit() else 100)
    cls_str = class_name or "10"
    cls_n   = _class_int(cls_str)
    chap    = chapter or "as per syllabus"
    extra   = f"Teacher's instructions: {suggestions.strip()}\n" if (suggestions or "").strip() else ""
    board_l = (board or "").lower()

    subj_l  = (subject or "").lower()
    is_stem = any(k in subj_l for k in [
        "math", "maths", "science", "physics", "chemistry", "biology",
        "algebra", "geometry", "trigonometry", "statistics"
    ])
    math_note = _math_rules() if is_stem else ""

    # Route competitive exams
    comp_map = {
        "ntse": "NTSE", "nso": "NSO", "imo": "IMO", "ijso": "IJSO"
    }
    for key, val in comp_map.items():
        if key in board_l:
            return _prompt_competitive(val, subject, chap, cls_str, m, difficulty, extra, math_note)

    # AP / TS state boards
    return _prompt_ap_ts(subject, chap, board, cls_str, cls_n, m, difficulty, extra, math_note)


# ═══════════════════════════════════════════════════════════════════════
# AP / TELANGANA STATE BOARD PROMPT
# Uses the actual exam pattern from ap_ts.json
# ═══════════════════════════════════════════════════════════════════════
def _prompt_ap_ts(subject, chap, board, cls_str, cls_n, m, difficulty, extra, math_note):
    pat = _PATTERN_AP_TS

    if cls_n <= 8:
        # Classes 6–8: 50-mark SA pattern
        return _prompt_ap_ts_6_8(subject, chap, board, cls_str, m, difficulty, extra, math_note, pat)
    else:
        # Classes 9–10: 100-mark SSC pattern
        return _prompt_ap_ts_9_10(subject, chap, board, cls_str, m, difficulty, extra, math_note, pat)


def _prompt_ap_ts_9_10(subject, chap, board, cls_str, m, difficulty, extra, math_note, pat):
    p   = pat.get("ssc_class_9_10", {})
    dur = p.get("duration", "3 Hours 15 Minutes")

    # Scale section counts to requested marks (default 100)
    # If teacher requests fewer marks, scale proportionally but keep structure
    scale = m / 100.0

    n_mcq     = max(5,  round(10  * scale))
    n_fib     = max(3,  round(5   * scale))
    n_match   = max(3,  round(5   * scale))
    n_vsq     = max(4,  round(10  * scale))   # Section IV, 2 marks each
    n_sq_give = max(4,  round(6   * scale))   # Section V given, 4 marks each
    n_sq_att  = max(3,  round(4   * scale))   # attempt
    n_lq_give = max(4,  round(6   * scale))   # Section VI given, 6 marks each
    n_lq_att  = max(3,  round(4   * scale))   # attempt
    n_app_give= max(2,  round(3   * scale))   # Section VII given, 10 marks each
    n_app_att = max(1,  round(2   * scale))   # attempt

    obj_marks = n_mcq + n_fib + n_match
    vsq_marks = n_vsq * 2
    sq_marks  = n_sq_att * 4
    lq_marks  = n_lq_att * 6
    app_marks = n_app_att * 10
    total_b   = vsq_marks + sq_marks + lq_marks + app_marks
    total     = obj_marks + total_b

    # Build subject-specific guidance
    subj_l = (subject or "").lower()
    subj_hint = ""
    specs = p.get("subject_specifics", {})
    if "math" in subj_l:
        subj_hint = specs.get("Mathematics", "")
    elif "science" in subj_l or "physics" in subj_l or "chemistry" in subj_l:
        subj_hint = specs.get("Science_Physics_Chemistry", "")
    elif "biology" in subj_l:
        subj_hint = specs.get("Science_Biology", "")
    elif "social" in subj_l or "history" in subj_l or "geography" in subj_l:
        subj_hint = specs.get("Social_Studies", "")
    elif "english" in subj_l:
        subj_hint = specs.get("English", "")

    instrs = p.get("general_instructions", [])

    prompt = f"""You are a senior examiner producing an official {board} practice paper for Class {cls_str}.
Subject: {subject}   Chapter/Topic: {chap}   Total Marks: {total}   Time: {dur}   Difficulty: {difficulty}
{extra}
REAL EXAM PATTERN (AP/Telangana SSC):
This paper has TWO parts. Part A (Objective, {obj_marks} marks) is answered in the question paper itself and collected after 30 minutes. Part B (Written, {total_b} marks) is answered in the answer booklet.

GENERAL INSTRUCTIONS (print exactly as given):
{chr(10).join(instrs)}

ABSOLUTE RULES — every violation is an error:
R1. Output ONLY the paper and answer key. No meta-commentary. No square-bracket placeholders like [write here]. Every line is real exam content.
R2. Questions must be 100% curriculum-accurate for {board} Class {cls_str} {subject}.
R3. Every question must show its mark in brackets at the end: [1 Mark] [2 Marks] [4 Marks] [6 Marks] [10 Marks]
R4. MCQ options go on ONE LINE in format: (A) ...  (B) ...  (C) ...  (D) ...  followed by (   ) on the same line for the student to write.
R5. Section headers go on their own line exactly as shown in the template.
R6. For diagrams: write [DIAGRAM: detailed description] on its own line.
R7. For tables: use | col | col | pipe format.
R8. Write ANSWER KEY on its own line to separate paper from answers.
R9. Answer key must show complete working — formula, substitution, every step, unit.
R10. OR alternatives in Section VI/VII must be genuine alternatives of equal difficulty.
{f"Subject note: {subj_hint}" if subj_hint else ""}
{math_note}
NOW WRITE THE COMPLETE PAPER using this EXACT template structure:

Subject: {subject}   Class: {cls_str}   Total Marks: {total}
Board: {board}   Time: {dur}

GENERAL INSTRUCTIONS
1. Answer all the questions under Part-A on the question paper itself and attach it to the answer booklet at the end.
2. Read the instructions carefully and answer only the required number of questions in each section.
3. Figures to the right indicate marks allotted.
4. Neat and fully labelled diagrams must be drawn wherever required.
5. Write the question number and sub-question number clearly.

PART A — OBJECTIVE  ({obj_marks} Marks)
(Answer in the question paper itself. Hand it over after 30 minutes.)

Section-I — Multiple Choice Questions  [1 Mark each]

1. [question stem relevant to {chap}] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...   (   )
""" + "".join(
    f"{i}. [question stem] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...   (   )\n"
    for i in range(2, n_mcq + 1)
) + f"""
Section-II — Fill in the Blanks  [1 Mark each]

{n_mcq + 1}. __________ [1 Mark]
""" + "".join(
    f"{n_mcq + i}. __________ [1 Mark]\n"
    for i in range(2, n_fib + 1)
) + f"""
Section-III — Match the Following  [1 Mark each]

{n_mcq + n_fib + 1}. Match Group-A with Group-B: [5 Marks]

| Group A | Group B |
|---|---|
| [term 1] | [matching item] |
| [term 2] | [matching item] |
| [term 3] | [matching item] |
| [term 4] | [matching item] |
| [term 5] | [matching item] |

PART B — WRITTEN  ({total_b} Marks)

Section-IV — Very Short Answer Questions  [2 Marks each]
(Answer ALL {n_vsq} questions. Each answer in not more than 5 lines.)

1. [question] [2 Marks]
""" + "".join(
    f"{i}. [question] [2 Marks]\n"
    for i in range(2, n_vsq + 1)
) + f"""
Section-V — Short Answer Questions  [4 Marks each]
(Answer any {n_sq_att} of the following {n_sq_give} questions. Each answer in not more than one page.)

{n_vsq + 1}. [question] [4 Marks]
""" + "".join(
    f"{n_vsq + i}. [question] [4 Marks]\n"
    for i in range(2, n_sq_give + 1)
) + f"""
Section-VI — Long Answer / Essay Questions  [6 Marks each]
(Answer any {n_lq_att} of the following {n_lq_give} questions. Each answer in not more than two pages.)

{n_vsq + n_sq_give + 1}. (i) [question] [6 Marks]
OR
{n_vsq + n_sq_give + 1}. (ii) [alternate question of equal difficulty] [6 Marks]
""" + "".join(
    f"{n_vsq + n_sq_give + i}. (i) [question] [6 Marks]\nOR\n{n_vsq + n_sq_give + i}. (ii) [alternate question] [6 Marks]\n"
    for i in range(2, n_lq_give + 1)
) + f"""
Section-VII — Activity / Application / Problem Solving  [10 Marks each]
(Answer any {n_app_att} of the following {n_app_give} questions.)

{n_vsq + n_sq_give + n_lq_give + 1}. [multi-part application question with sub-parts (a)(b)(c)] [10 Marks]
""" + "".join(
    f"{n_vsq + n_sq_give + n_lq_give + i}. [multi-part application question] [10 Marks]\n"
    for i in range(2, n_app_give + 1)
) + f"""
ANSWER KEY

Section-I (MCQ):
1. (X) — [brief reason]
""" + "".join(f"{i}. (X) — [reason]\n" for i in range(2, n_mcq + 1)) + f"""
Section-II (Fill in the Blank):
{n_mcq + 1}. [answer]
""" + "".join(f"{n_mcq + i}. [answer]\n" for i in range(2, n_fib + 1)) + f"""
Section-III (Match):
[1→?, 2→?, 3→?, 4→?, 5→?]

Section-IV (Very Short Answer):
1. [complete answer with definition/formula/explanation as appropriate]
""" + "".join(f"{i}. [complete answer]\n" for i in range(2, n_vsq + 1)) + f"""
Section-V (Short Answer):
{n_vsq + 1}. [step-by-step solution with formula, working, diagram if needed]
""" + "".join(f"{n_vsq + i}. [complete solution]\n" for i in range(2, n_sq_att + 1)) + f"""
Section-VI (Long Answer):
{n_vsq + n_sq_give + 1}. (i) [detailed solution — derivation/proof/explanation with diagram]
""" + "".join(
    f"{n_vsq + n_sq_give + i}. [detailed solution]\n"
    for i in range(2, n_lq_att + 1)
) + f"""
Section-VII (Application):
{n_vsq + n_sq_give + n_lq_give + 1}. (a) [working] (b) [working] (c) [working]
""" + "".join(
    f"{n_vsq + n_sq_give + n_lq_give + i}. [complete solution]\n"
    for i in range(2, n_app_att + 1)
) + f"""
Now replace EVERY placeholder with real, curriculum-accurate content for {board} Class {cls_str} {subject}, chapter: {chap}.
Difficulty: {difficulty}. All questions must be original and exam-ready. Begin:"""

    return prompt


def _prompt_ap_ts_6_8(subject, chap, board, cls_str, m, difficulty, extra, math_note, pat):
    p   = pat.get("classes_6_8", {})
    dur = "2 Hours 30 Minutes"

    # Scale to requested marks
    obj_m  = max(5,  round(m * 0.20))
    vsq_m  = max(10, round(m * 0.40))
    sa_m   = max(5,  round(m * 0.20))
    la_m   = m - obj_m - vsq_m - sa_m

    n_obj  = obj_m
    n_vsq  = vsq_m // 2
    n_sa_g = max(4, (sa_m // 5) + 2)
    n_sa_a = sa_m // 5
    n_la_g = max(2, (la_m // 10) + 1)
    n_la_a = la_m // 10

    prompt = f"""You are a senior examiner creating an official {board} practice paper for Class {cls_str}.
Subject: {subject}   Chapter/Topic: {chap}   Total Marks: {m}   Time: {dur}   Difficulty: {difficulty}
{extra}
ABSOLUTE RULES:
R1. Output ONLY paper and answer key. No placeholders, no meta-commentary.
R2. Questions must be 100% curriculum-accurate for Class {cls_str} {subject}.
R3. Mark allocation shown in [brackets] at end of every question.
R4. MCQ options: (A) ...  (B) ...  (C) ...  (D) ...  (   )  all on ONE line.
R5. Answer key must show complete working for every question.
{math_note}

Subject: {subject}   Class: {cls_str}   Total Marks: {m}
Board: {board}   Time: {dur}

GENERAL INSTRUCTIONS
1. Answer ALL questions in Section A.
2. Answer ALL questions in Section B.
3. Answer any {n_sa_a} questions from Section C.
4. Answer any {n_la_a} question from Section D.
5. Figures to the right indicate marks. Draw neat diagrams wherever required.

Section A — Objective  ({obj_m} Marks)  [1 Mark each]
(Choose correct answer / fill blank / match)

1. [MCQ question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...   (   )
""" + "".join(
    f"{i}. [MCQ/FIB/Match question] [1 Mark]\n"
    for i in range(2, n_obj + 1)
) + f"""
Section B — Very Short Answer  ({vsq_m} Marks)  [2 Marks each]
(Answer ALL questions in 1–2 sentences.)

{n_obj + 1}. [question] [2 Marks]
""" + "".join(
    f"{n_obj + i}. [question] [2 Marks]\n"
    for i in range(2, n_vsq + 1)
) + f"""
Section C — Short Answer  ({sa_m} Marks)  [5 Marks each]
(Answer any {n_sa_a} of the following {n_sa_g} questions.)

{n_obj + n_vsq + 1}. [question] [5 Marks]
""" + "".join(
    f"{n_obj + n_vsq + i}. [question] [5 Marks]\n"
    for i in range(2, n_sa_g + 1)
) + f"""
Section D — Long Answer  ({la_m} Marks)  [10 Marks each]
(Answer any {n_la_a} of the following {n_la_g} questions.)

{n_obj + n_vsq + n_sa_g + 1}. [question with sub-parts] [10 Marks]
""" + "".join(
    f"{n_obj + n_vsq + n_sa_g + i}. [question] [10 Marks]\n"
    for i in range(2, n_la_g + 1)
) + f"""
ANSWER KEY

Section A:
1. (X)
""" + "".join(f"{i}. [answer]\n" for i in range(2, n_obj + 1)) + f"""
Section B:
{n_obj + 1}. [complete answer]
""" + "".join(f"{n_obj + i}. [answer]\n" for i in range(2, n_vsq + 1)) + f"""
Section C:
{n_obj + n_vsq + 1}. [step-by-step solution]
""" + "".join(f"{n_obj + n_vsq + i}. [solution]\n" for i in range(2, n_sa_a + 1)) + f"""
Section D:
{n_obj + n_vsq + n_sa_g + 1}. [detailed solution with diagram if needed]

Replace ALL placeholders with real curriculum-accurate content for {board} Class {cls_str} {subject}, chapter: {chap}.
Difficulty: {difficulty}. Begin:"""

    return prompt


# ═══════════════════════════════════════════════════════════════════════
# COMPETITIVE EXAM PROMPT (NTSE / NSO / IMO / IJSO)
# Uses the actual pattern from competitive.json
# ═══════════════════════════════════════════════════════════════════════
def _prompt_competitive(exam, subject, chap, cls_str, m, difficulty, extra, math_note):
    comp = _PATTERN_COMP.get("exams", {}).get(exam, {})
    exam_full = comp.get("full_name", exam)
    body  = comp.get("body", comp.get("conducting_body", ""))
    elig  = comp.get("eligibility", f"Class {cls_str}")
    style = comp.get("question_style", "All MCQ. 4 options. One correct.")
    p_note= comp.get("paper_generation_note", "")

    # Exam-specific structure
    if exam == "NTSE":
        return _prompt_ntse(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note)
    elif exam == "NSO":
        return _prompt_nso(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note)
    elif exam == "IMO":
        return _prompt_imo(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note)
    elif exam == "IJSO":
        return _prompt_ijso(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note)
    else:
        return _prompt_generic_comp(exam, subject, chap, cls_str, m, difficulty, extra, math_note)


def _prompt_ntse(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note):
    """NTSE has MAT + SAT as separate papers. Generate as requested."""
    stage_info = comp.get("stages", {})
    s1 = stage_info.get("Stage_1_State", {})
    marking = comp.get("marking_scheme", s1.get("marking", "No negative marking at Stage 1."))

    # Detect which paper is being asked (MAT vs SAT)
    subj_l = (subject or "").lower()
    if "mat" in subj_l or "mental" in subj_l or "reasoning" in subj_l or "ability" in subj_l:
        # MAT paper: 100 questions, 100 marks, 2 hours
        n_q = min(100, m)
        return f"""You are a senior examiner creating an official NTSE Stage 1 MAT (Mental Ability Test) practice paper.
Exam: {exam_full} — MAT (Mental Ability Test)   Class: {cls_str}   Questions: {n_q}   Marks: {n_q}   Time: 2 Hours
Difficulty: {difficulty}
{extra}
MAT PATTERN:
- All questions are MCQ with 4 options (A) (B) (C) (D).
- Each carries 1 mark. {marking}
- Question types to include: Verbal Analogy, Non-Verbal Analogy, Number Series, Letter Series, Mixed Series, Coding–Decoding, Blood Relations, Direction & Distance, Ranking & Ordering, Clock & Calendar, Venn Diagrams, Mirror Image, Paper Folding, Embedded Figures, Figure Matrix, Mathematical Reasoning.
- Distribute approximately: Analogy (15Q), Series (15Q), Coding/Decoding (10Q), Blood Relations (8Q), Direction/Distance (8Q), Ranking/Ordering (8Q), Clock/Calendar (5Q), Figure-based (15Q), Mathematical Reasoning (16Q).

ABSOLUTE RULES:
R1. Every question must be fully formed — no placeholders.
R2. MCQ options: (A) ...  (B) ...  (C) ...  (D) ... on ONE line after the question.
R3. Mark each question [1 Mark].
R4. No hints or labels revealing the question type embedded in the question.
R5. Difficulty: {difficulty}. NTSE questions are moderately challenging.
{math_note}

Exam: {exam_full} — Mental Ability Test
Class: {cls_str}                                                   Total Marks: {n_q}
                                                                    Time: 2 Hours

INSTRUCTIONS
1. This paper contains {n_q} Multiple Choice Questions.
2. Each question carries 1 mark. {marking}
3. Choose the correct option and darken the appropriate circle on the OMR sheet.

1. [MAT question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [MAT question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_q + 1)
) + f"""
ANSWER KEY
""" + "".join(f"{i}. (X) — [explanation]\n" for i in range(1, n_q + 1)) + f"""
Replace ALL placeholders with real, well-formed NTSE MAT questions. Difficulty: {difficulty}. Begin:"""

    else:
        # SAT paper: 100Q — 40 Science + 40 Social Science + 20 Maths
        n_sci = 40; n_soc = 40; n_mat = 20
        total_q = n_sci + n_soc + n_mat
        topic = chap if chap and chap != "as per syllabus" else "Class 10 syllabus (all topics)"

        return f"""You are a senior examiner creating an official NTSE Stage 1 SAT (Scholastic Aptitude Test) practice paper.
Exam: {exam_full} — SAT (Scholastic Aptitude Test)   Class: {cls_str}   Questions: {total_q}   Marks: {total_q}   Time: 2 Hours
Topic focus: {topic}   Difficulty: {difficulty}
{extra}
SAT PATTERN:
- Science: {n_sci} questions (Physics ~13, Chemistry ~13, Biology ~14)
- Social Science: {n_soc} questions (History ~13, Geography ~13, Civics ~7, Economics ~7)
- Mathematics: {n_mat} questions
- All MCQ, 1 mark each, 4 options. {marking}
- Questions are numbered sequentially 1–{total_q} across all subjects.

ABSOLUTE RULES:
R1. Every question is complete, curriculum-accurate, original.
R2. Options: (A) ...  (B) ...  (C) ...  (D) ... on one line after question.
R3. Mark each [1 Mark]. No category labels within question text.
R4. Wrong options must be plausible (not obviously wrong).
R5. Language must match NCERT/State Board textbook terminology.
{math_note}

Exam: {exam_full} — Scholastic Aptitude Test
Class: {cls_str}   Topic: {topic}                                  Total Marks: {total_q}
                                                                    Time: 2 Hours

INSTRUCTIONS
1. This paper contains {total_q} questions — Science ({n_sci}), Social Science ({n_soc}), Mathematics ({n_mat}).
2. Each question carries 1 mark. {marking}

SCIENCE  (Questions 1–{n_sci})

1. [Science question — Physics/Chemistry/Biology] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [Science question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_sci + 1)
) + f"""
SOCIAL SCIENCE  (Questions {n_sci+1}–{n_sci+n_soc})

{n_sci+1}. [Social Science question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{n_sci+i}. [Social Science question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_soc + 1)
) + f"""
MATHEMATICS  (Questions {n_sci+n_soc+1}–{total_q})

{n_sci+n_soc+1}. [Maths question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{n_sci+n_soc+i}. [Maths question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_mat + 1)
) + f"""
ANSWER KEY
""" + "".join(f"{i}. (X) — [explanation]\n" for i in range(1, total_q + 1)) + f"""
Replace ALL placeholders with real NTSE-level questions. Difficulty: {difficulty}. Topic: {topic}. Begin:"""


def _prompt_nso(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note):
    patt = comp.get("paper_structure", {}).get("Classes_6_10", {})
    secs = patt.get("sections", [])
    total_q = patt.get("total_questions", 50)
    total_m = patt.get("total_marks", 60)
    dur = patt.get("duration", "1 Hour")
    marking = comp.get("marking", "No negative marking.")

    # Section details
    s1_q = 10; s1_m = 10   # Logical Reasoning, 1 mark each
    s2_q = 35; s2_m = 35   # Science, 1 mark each
    s3_q = 5;  s3_m = 15   # Achiever's, 3 marks each

    topic = chap if chap and chap != "as per syllabus" else f"Class {cls_str} Science syllabus"

    return f"""You are a senior examiner creating an official NSO (National Science Olympiad) practice paper.
Exam: {exam_full}   Class: {cls_str}   Total Questions: {total_q}   Total Marks: {total_m}   Time: {dur}
Topic: {topic}   Difficulty: {difficulty}
{extra}
NSO PATTERN (SOF):
- Section 1 — Logical Reasoning: {s1_q} questions × 1 mark = {s1_m} marks
- Section 2 — Science: {s2_q} questions × 1 mark = {s2_m} marks (from Class {cls_str} science syllabus)
- Section 3 — Achiever's Section: {s3_q} questions × 3 marks = {s3_m} marks (HOT — higher order thinking)
- All MCQ, 4 options, ONE correct answer. {marking}

ABSOLUTE RULES:
R1. Section 1: pure logical reasoning questions (analogy, series, coding, mirror image, figure, etc.).
R2. Section 2: science questions exactly from Class {cls_str} syllabus, topic: {topic}.
R3. Section 3: challenging application questions from the same syllabus — multi-concept or data-based.
R4. Wrong options must be plausible. Questions must be complete and original.
R5. Options format: (A) ...  (B) ...  (C) ...  (D) ... on one line after question.
R6. Mark each question: Section 1 and 2 = [1 Mark], Section 3 = [3 Marks].
{math_note}

Exam: {exam_full}
Class: {cls_str}   Topic: {topic}   Total Marks: {total_m}   Time: {dur}

INSTRUCTIONS
1. Total {total_q} questions: Section 1 ({s1_q}Q × 1M), Section 2 ({s2_q}Q × 1M), Section 3 ({s3_q}Q × 3M).
2. All questions are MCQ. 4 options. {marking}

Section 1 — Logical Reasoning  ({s1_m} Marks)

1. [Logical Reasoning question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [Logical Reasoning question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s1_q + 1)
) + f"""
Section 2 — Science  ({s2_m} Marks)

{s1_q+1}. [Science question from {topic}] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{s1_q+i}. [Science question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s2_q + 1)
) + f"""
Section 3 — Achiever's Section  ({s3_m} Marks)
(Higher Order Thinking — 3 marks each)

{s1_q+s2_q+1}. [Challenging HOT science question] [3 Marks]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{s1_q+s2_q+i}. [HOT question] [3 Marks]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s3_q + 1)
) + f"""
ANSWER KEY
""" + "".join(f"{i}. (X) — [explanation]\n" for i in range(1, total_q + 1)) + f"""
Replace ALL placeholders with real NSO-quality questions. Class {cls_str}. Topic: {topic}. Difficulty: {difficulty}. Begin:"""


def _prompt_imo(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note):
    patt = comp.get("paper_structure", {}).get("Classes_6_10", {})
    total_q = patt.get("total_questions", 50)
    total_m = patt.get("total_marks", 60)
    dur = patt.get("duration", "1 Hour")
    marking = comp.get("marking", "No negative marking.")

    s1_q = 10; s1_m = 10    # Logical Reasoning
    s2_q = 25; s2_m = 25    # Mathematical Reasoning
    s3_q = 10; s3_m = 10    # Everyday Mathematics
    s4_q = 5;  s4_m = 15    # Achiever's Section, 3 marks each

    topic = chap if chap and chap != "as per syllabus" else f"Class {cls_str} Mathematics"

    return f"""You are a senior examiner creating an official IMO (International Mathematics Olympiad, SOF) practice paper.
Exam: {exam_full}   Class: {cls_str}   Total Marks: {total_m}   Time: {dur}
Topic: {topic}   Difficulty: {difficulty}
{extra}
IMO PATTERN (SOF):
- Section 1 — Logical Reasoning: {s1_q} questions × 1 mark = {s1_m} marks
- Section 2 — Mathematical Reasoning: {s2_q} questions × 1 mark = {s2_m} marks (syllabus-based)
- Section 3 — Everyday Mathematics: {s3_q} questions × 1 mark = {s3_m} marks (real-life application)
- Section 4 — Achiever's Section: {s4_q} questions × 3 marks = {s4_m} marks (high-difficulty)
- All MCQ, 4 options, ONE correct. {marking}

ABSOLUTE RULES:
R1. Section 1: logical/reasoning questions using numbers, letters, figures.
R2. Section 2: maths questions from Class {cls_str} curriculum, topic {topic}.
R3. Section 3: word problems applying maths to real-world situations.
R4. Section 4: tough multi-step maths problems requiring deep problem-solving.
R5. All wrong options must arise from plausible errors.
R6. Options: (A) ...  (B) ...  (C) ...  (D) ... on one line after question.
{math_note}

Exam: {exam_full}
Class: {cls_str}   Topic: {topic}   Total Marks: {total_m}   Time: {dur}

INSTRUCTIONS
1. Total {total_q} questions across 4 sections. {marking}
2. Section 1 & 2 & 3: 1 mark each. Section 4: 3 marks each.

Section 1 — Logical Reasoning  ({s1_m} Marks)

1. [Logical Reasoning question using numbers/letters/figures] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [Logical Reasoning question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s1_q + 1)
) + f"""
Section 2 — Mathematical Reasoning  ({s2_m} Marks)

{s1_q+1}. [Maths question from {topic}] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{s1_q+i}. [Maths question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s2_q + 1)
) + f"""
Section 3 — Everyday Mathematics  ({s3_m} Marks)

{s1_q+s2_q+1}. [Real-life application word problem] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{s1_q+s2_q+i}. [Word problem] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s3_q + 1)
) + f"""
Section 4 — Achiever's Section  ({s4_m} Marks)
(High difficulty — 3 marks each)

{s1_q+s2_q+s3_q+1}. [Challenging multi-step maths question] [3 Marks]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{s1_q+s2_q+s3_q+i}. [HOT maths question] [3 Marks]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, s4_q + 1)
) + f"""
ANSWER KEY
""" + "".join(f"{i}. (X) — [explanation]\n" for i in range(1, total_q + 1)) + f"""
Replace ALL placeholders with real IMO-quality questions. Class {cls_str}. Topic: {topic}. Difficulty: {difficulty}. Begin:"""


def _prompt_ijso(comp, exam_full, subject, chap, cls_str, m, difficulty, extra, math_note):
    s1 = comp.get("national_selection_stages", {}).get("Stage_1_NSEJS", {})
    n_q = s1.get("questions", 80)
    dur = "2 Hours"
    marking = "+3 correct, −1 wrong"

    # Physics 27, Chemistry 27, Biology 26
    n_phy = 27; n_che = 27; n_bio = 26

    topic = chap if chap and chap != "as per syllabus" else "Integrated Science (Class 9–10 level)"

    return f"""You are a senior examiner creating an official IJSO / NSEJS Stage 1 practice paper.
Exam: {exam_full} (NSEJS Stage 1 style)   Class: {cls_str}   Questions: {n_q}   Time: {dur}
Marks: +3 correct, −1 wrong   Difficulty: {difficulty}   Topic: {topic}
{extra}
IJSO/NSEJS PATTERN:
- {n_q} MCQ questions: Physics ({n_phy}), Chemistry ({n_che}), Biology ({n_bio})
- 4 options per question, ONE correct answer.
- Marking: {marking}. Total maximum = {n_q*3} marks if all correct.
- Level: Class 10 NCERT standard with deep application and multi-concept questions.
- Questions are numbered sequentially 1–{n_q}.

ABSOLUTE RULES:
R1. Physics, Chemistry, Biology questions must be accurately labelled with section headers.
R2. Every question is complete, original, curriculum-accurate at Class 9–10 NCERT level.
R3. Questions must test understanding and application, not just recall.
R4. Wrong options must arise from plausible misconceptions or partial understanding.
R5. Options: (A) ...  (B) ...  (C) ...  (D) ... on one line after question.
R6. Mark each: [+3/−1]
R7. Diagrams: write [DIAGRAM: description] before the question if diagram-based.
{math_note}

Exam: {exam_full} (NSEJS Stage 1 Practice)
Class: {cls_str}   Topic: {topic}
Total Questions: {n_q}   Marking: +3 correct / −1 wrong   Time: {dur}

INSTRUCTIONS
1. Each question has ONE correct answer. Marking: +3 correct, −1 wrong, 0 unattempted.
2. Questions cover Physics, Chemistry and Biology equally.

PHYSICS  (Questions 1–{n_phy})

1. [Physics question at Class 9–10 level, application-based] [+3/−1]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [Physics question] [+3/−1]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_phy + 1)
) + f"""
CHEMISTRY  (Questions {n_phy+1}–{n_phy+n_che})

{n_phy+1}. [Chemistry question] [+3/−1]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{n_phy+i}. [Chemistry question] [+3/−1]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_che + 1)
) + f"""
BIOLOGY  (Questions {n_phy+n_che+1}–{n_q})

{n_phy+n_che+1}. [Biology question] [+3/−1]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{n_phy+n_che+i}. [Biology question] [+3/−1]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_bio + 1)
) + f"""
ANSWER KEY
""" + "".join(f"{i}. (X) — [explanation: 2 sentences why correct + why main distractor is wrong]\n" for i in range(1, n_q + 1)) + f"""
Replace ALL placeholders with real IJSO/NSEJS-quality questions. Topic: {topic}. Difficulty: {difficulty}. Begin:"""


def _prompt_generic_comp(exam, subject, chap, cls_str, m, difficulty, extra, math_note):
    n_q = m // 4
    return f"""Create a {exam} style practice paper.
Subject: {subject}   Class: {cls_str}   Chapter: {chap}   Marks: {m}   Difficulty: {difficulty}
{extra}
All MCQ, 4 options, 1 mark each. Show ANSWER KEY at the end.
{math_note}
1. [question] [1 Mark]
   (A) ...  (B) ...  (C) ...  (D) ...
""" + "".join(
    f"{i}. [question] [1 Mark]\n   (A) ...  (B) ...  (C) ...  (D) ...\n"
    for i in range(2, n_q + 1)
) + "ANSWER KEY\n" + "".join(f"{i}. (X)\n" for i in range(1, n_q + 1)) + "\nBegin:"


# ═══════════════════════════════════════════════════════════════════════
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
def generate_diagram_svg(description: str):
    prompt = f"""You are an expert scientific illustrator for school textbooks. Create a clean, accurate SVG diagram for:

"{description}"

STRICT RULES:
1. Output ONLY the SVG code. No markdown, no explanation, no code fences.
2. SVG must start with <svg and end with </svg>.
3. Use: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 260" width="400" height="260">
4. Use ONLY black (#111111) and dark grey (#555555) for strokes. White (#ffffff) or very light grey (#f2f2f2) fills only.
5. stroke-width="2" for main lines, stroke-width="1" for detail lines.
6. Add clear text labels: font-size="12" font-family="Arial,sans-serif" fill="#111111"
7. Geometrically accurate. Include all key parts a student needs.
8. NO external resources, NO JavaScript, NO CSS, NO defs/filters — only: line, circle, rect, polygon, polyline, path, text, g.
9. Every text element must have explicit x, y, font-size, font-family, fill attributes.
10. Clean and suitable for a printed exam paper (black on white).

Output only the SVG:"""
    text, err = call_gemini(prompt)
    if not text:
        return None
    svg_match = re.search(r'<svg[\s\S]*?</svg>', text, re.IGNORECASE)
    return svg_match.group(0) if svg_match else None


# ── Pure-Python SVG → ReportLab renderer ──────────────────────────────
def _svg_color(val, default=(0, 0, 0)):
    if not val or val in ('none', 'transparent'):
        return None
    val = val.strip()
    named = {
        'black': (0,0,0), 'white': (1,1,1), 'red': (1,0,0),
        'blue': (0,0,1), 'green': (0,.5,0), 'grey': (.5,.5,.5),
        'gray': (.5,.5,.5), 'lightgrey': (.83,.83,.83),
        'lightgray': (.83,.83,.83), '#111111': (.067,.067,.067),
        '#555555': (.333,.333,.333), '#f2f2f2': (.949,.949,.949),
        '#f0f0f0': (.941,.941,.941), '#ffffff': (1,1,1),
        '#000000': (0,0,0),
    }
    if val.lower() in named:
        return named[val.lower()]
    if val.startswith('#'):
        h = val[1:]
        if len(h) == 3:
            h = h[0]*2 + h[1]*2 + h[2]*2
        if len(h) == 6:
            try:
                return (int(h[0:2],16)/255, int(h[2:4],16)/255, int(h[4:6],16)/255)
            except Exception:
                pass
    return default


def _parse_points(pts_str):
    nums = re.findall(r'[-+]?\d*\.?\d+', pts_str)
    return [(float(nums[i]), float(nums[i+1])) for i in range(0, len(nums)-1, 2)]


def svg_to_rl_image(svg_str: str, width_pt: float = 360):
    from reportlab.graphics.shapes import Drawing, Line, Circle, Rect, Polygon, PolyLine, String, Group
    from reportlab.lib.colors import Color

    try:
        clean = re.sub(r'<(\/?)\\w+:', r'<\1', svg_str)
        clean = re.sub(r'\\s\\w+:\\w+="[^"]*"', '', clean)
        root = ET.fromstring(clean)

        vb = root.get('viewBox', '0 0 400 260')
        vb_parts = [float(x) for x in re.findall(r'[-\d.]+', vb)]
        svg_w = vb_parts[2] if len(vb_parts) >= 3 else float(root.get('width', 400))
        svg_h = vb_parts[3] if len(vb_parts) >= 4 else float(root.get('height', 260))

        scale_x = width_pt / svg_w
        height_pt = svg_h * scale_x
        drawing = Drawing(width_pt, height_pt)

        def tx(x): return float(x) * scale_x
        def ty(y): return height_pt - float(y) * scale_x

        def get_attr(el, *names, default='0'):
            for n in names:
                v = el.get(n)
                if v is not None:
                    return v
            return default

        def make_color(val, default_rgb=(0,0,0), alpha=1.0):
            rgb = _svg_color(val, default_rgb)
            if rgb is None:
                return None
            return Color(rgb[0], rgb[1], rgb[2], alpha)

        def parse_sw(el):
            sw = el.get('stroke-width', el.get('strokeWidth', '1.5'))
            try:
                return max(0.5, float(sw) * scale_x)
            except Exception:
                return 1.0

        NS = '{http://www.w3.org/2000/svg}'

        def render_element(el, group):
            tag      = el.tag.replace(NS, '').lower()
            stroke_c = make_color(el.get('stroke', '#111111'))
            fill_c   = make_color(el.get('fill', 'none'))
            sw       = parse_sw(el)

            if tag == 'line':
                shape = Line(tx(get_attr(el,'x1')), ty(get_attr(el,'y1')),
                             tx(get_attr(el,'x2')), ty(get_attr(el,'y2')))
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)
            elif tag == 'circle':
                shape = Circle(tx(get_attr(el,'cx','0')), ty(get_attr(el,'cy','0')),
                               float(get_attr(el,'r','5')) * scale_x)
                shape.fillColor   = fill_c or Color(1,1,1)
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)
            elif tag == 'rect':
                x = tx(get_attr(el,'x','0'))
                y = ty(float(get_attr(el,'y','0')) + float(get_attr(el,'height','10')))
                w = float(get_attr(el,'width','10'))  * scale_x
                h = float(get_attr(el,'height','10')) * scale_x
                shape = Rect(x, y, w, h)
                shape.fillColor   = fill_c or Color(1,1,1)
                shape.strokeColor = stroke_c or Color(0,0,0)
                shape.strokeWidth = sw
                group.add(shape)
            elif tag in ('polygon', 'polyline'):
                pairs = _parse_points(el.get('points', ''))
                if len(pairs) >= 2:
                    pts = []
                    for (px, py) in pairs:
                        pts += [tx(px), ty(py)]
                    shape = Polygon(pts) if tag == 'polygon' else PolyLine(pts)
                    shape.fillColor   = fill_c or (Color(1,1,1) if tag == 'polygon' else None)
                    shape.strokeColor = stroke_c or Color(0,0,0)
                    shape.strokeWidth = sw
                    group.add(shape)
            elif tag == 'path':
                d = el.get('d', '')
                tokens = re.findall(r'[MLZmlz]|[-+]?\d*\.?\d+', d)
                pts, cmd, cur_x, cur_y = [], 'M', 0.0, 0.0
                i2 = 0
                while i2 < len(tokens):
                    t = tokens[i2]
                    if t in 'MLml': cmd = t; i2 += 1; continue
                    if t in 'Zz':
                        if len(pts) >= 4: pts += [pts[0], pts[1]]
                        i2 += 1; continue
                    try:
                        vx = float(t); vy = float(tokens[i2+1]); i2 += 2
                        if cmd == 'm': vx += cur_x; vy += cur_y
                        if cmd == 'l': vx += cur_x; vy += cur_y
                        cur_x, cur_y = vx, vy
                        pts += [tx(vx), ty(vy)]
                    except Exception:
                        i2 += 1
                if len(pts) >= 4:
                    shape = Polygon(pts) if fill_c else PolyLine(pts)
                    if fill_c: shape.fillColor = fill_c
                    shape.strokeColor = stroke_c or Color(0,0,0)
                    shape.strokeWidth = sw
                    if not fill_c: shape.fillColor = None
                    group.add(shape)
            elif tag == 'text':
                x = tx(float(get_attr(el,'x','0')))
                y = ty(float(get_attr(el,'y','0')))
                try:
                    fs_raw = el.get('font-size', el.get('fontSize', '12'))
                    fs = max(6, float(re.findall(r'[\d.]+', fs_raw)[0]) * scale_x)
                except Exception:
                    fs = 10
                txt = (el.text or '').strip()
                for tspan in el:
                    if tspan.tag.replace(NS,'').lower() == 'tspan':
                        txt += (tspan.text or '')
                if txt:
                    fc = make_color(el.get('fill', '#111111'), (0,0,0))
                    s = String(x, y - fs * 0.3, txt)
                    s.fontSize  = fs
                    s.fillColor = fc or Color(0,0,0)
                    ff = el.get('font-family', 'Helvetica')
                    s.fontName  = 'Helvetica-Bold' if 'bold' in ff.lower() else 'Helvetica'
                    group.add(s)
            elif tag == 'g':
                sub = Group()
                for child in el:
                    render_element(child, sub)
                group.add(sub)

        top_group = Group()
        for child in root:
            render_element(child, top_group)
        drawing.add(top_group)
        return drawing
    except Exception:
        return None


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
            diag_descs = re.findall(
                r'\[DIAGRAM:\s*([^\]]+)\]|\[draw\s+([^\]]+)\]',
                paper_text, re.IGNORECASE)
            for d1, d2 in diag_descs:
                desc = (d1 or d2).strip()
                if desc and desc not in diagrams:
                    svg = generate_diagram_svg(desc)
                    if svg:
                        diagrams[desc] = svg

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