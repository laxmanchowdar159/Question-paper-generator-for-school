import os
import re
import json
import time
from pathlib import Path
from io import BytesIO

# ==========================================
# PDF IMPORTS
# ==========================================
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Table, TableStyle, PageBreak, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, grey, black

from flask import Flask, render_template, request, jsonify, send_file

# ==========================================
# GEMINI IMPORT
# ==========================================
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except Exception:
    genai = None
    GENAI_AVAILABLE = False


# ==========================================
# FLASK INIT
# ==========================================
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static"
)

# ==========================================
# GEMINI CONFIG
# ==========================================
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

if GEMINI_KEY and GENAI_AVAILABLE:
    genai.configure(api_key=GEMINI_KEY)

# Model priority list — newest first, older as fallback
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.0-pro",
    "gemini-pro",
]


# ==========================================
# UTIL: SPLIT PAPER / ANSWER KEY
# ==========================================
def split_key(text: str):
    """Split generated text into (paper_body, answer_key)."""
    patterns = [
        r'\n\s*={3,}\s*\n\s*answer\s+key\s*\n',
        r'\n\s*-{3,}\s*\n\s*answer\s+key\s*\n',
        r'\n\s*answer\s+key[:\s]*\n',
        r'\n\s*\*{1,2}answer\s+key\*{0,2}[:\s]*\n',
        r'\nANSWER KEY\n',
        r'answer\s+key[:\s]+',
    ]
    for pat in patterns:
        parts = re.split(pat, text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    return text.strip(), None


# ==========================================
# SAFE TEXT: Unicode -> ReportLab XML
# ==========================================
def sanitize_line(text: str) -> str:
    """
    Convert raw text to ReportLab-safe XML.
    NEVER pass Unicode sub/superscripts to ReportLab — renders black boxes.
    Also escape & < > to prevent XML parse errors.
    """
    # 1. Escape XML special chars FIRST
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # 2. Unicode SUPERSCRIPT digits -> <super>
    sup_map = {
        "\u2070": "0", "\u00b9": "1", "\u00b2": "2", "\u00b3": "3",
        "\u2074": "4", "\u2075": "5", "\u2076": "6", "\u2077": "7",
        "\u2078": "8", "\u2079": "9", "\u207f": "n", "\u2071": "i",
    }
    for ch, val in sup_map.items():
        text = text.replace(ch, f"<super rise='3' size='8'>{val}</super>")

    # 3. Unicode SUBSCRIPT digits -> <sub>
    sub_map = {
        "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3",
        "\u2084": "4", "\u2085": "5", "\u2086": "6", "\u2087": "7",
        "\u2088": "8", "\u2089": "9",
    }
    for ch, val in sub_map.items():
        text = text.replace(ch, f"<sub rise='-2' size='8'>{val}</sub>")

    # 4. Arrows and math operators -> XML entities
    replacements = {
        "\u2192": "&#8594;",   # ->
        "\u2190": "&#8592;",   # <-
        "\u2194": "&#8596;",   # <->
        "\u21cc": "&#8652;",   # equilibrium
        "\u27f6": "&#10230;",  # long arrow
        "\u2022": "&#8226;",   # bullet
        "\u00b7": "&#183;",    # middle dot
        "\u00b0": "&#176;",    # degree
        "\u00d7": "&#215;",    # multiply
        "\u00f7": "&#247;",    # divide
        "\u00b1": "&#177;",    # plus-minus
        "\u2264": "&#8804;",   # <=
        "\u2265": "&#8805;",   # >=
        "\u2260": "&#8800;",   # !=
        "\u2248": "&#8776;",   # approx
        "\u221e": "&#8734;",   # infinity
        "\u2211": "&#8721;",   # sum
        "\u222b": "&#8747;",   # integral
        "\u2202": "&#8706;",   # partial
        "\u221a": "&#8730;",   # sqrt
        "\u03c0": "&#960;",    # pi
        "\u03b8": "&#952;",    # theta
        "\u03b1": "&#945;",    # alpha
        "\u03b2": "&#946;",    # beta
        "\u03b3": "&#947;",    # gamma
        "\u03b4": "&#948;",    # delta
        "\u03bb": "&#955;",    # lambda
        "\u03bc": "&#956;",    # mu
        "\u03c3": "&#963;",    # sigma
        "\u03c9": "&#969;",    # omega
        "\u0394": "&#916;",    # Delta
        "\u03a9": "&#937;",    # Omega
        "\u00bd": "&#189;",    # 1/2
        "\u00bc": "&#188;",    # 1/4
        "\u00be": "&#190;",    # 3/4
        "\u2212": "&#8722;",   # minus sign
    }
    for ch, entity in replacements.items():
        text = text.replace(ch, entity)

    # 5. Box-drawing chars (from the prompt itself leaking in) -> nothing
    box_chars = "═║╔╗╚╝╠╣╦╩╬─│┌┐└┘├┤┬┴┼"
    for ch in box_chars:
        text = text.replace(ch, "")

    return text


# ==========================================
# LINE TYPE DETECTORS
# ==========================================
def is_separator_line(line: str) -> bool:
    s = line.strip()
    return bool(re.match(r'^[=\-_*#]{3,}$', s))


def is_section_header(line: str) -> bool:
    s = line.strip()
    if re.match(
        r'^(SECTION\s+[A-D]|Section\s+[A-Da-d]|PART\s+[A-D])',
        s, re.IGNORECASE
    ):
        return True
    if re.match(
        r'^(General Instructions|Instructions|Answer Key|ANSWER KEY)',
        s, re.IGNORECASE
    ):
        return True
    # All-caps lines (headers like "MATHEMATICS QUESTION PAPER")
    if s.isupper() and len(s) > 4 and len(s) < 80:
        return True
    return False


def is_table_row(line: str) -> bool:
    return line.count("|") >= 2


def is_divider_row(line: str) -> bool:
    return bool(re.match(r'^\|[\s\-:|]+\|$', line.strip()))


# ==========================================
# PDF GENERATOR — FULLY REWRITTEN
# ==========================================
def create_exam_pdf(
    text: str,
    subject: str,
    chapter: str,
    answer_key: str = None,
    include_key: bool = False,
) -> bytes:
    """
    Render exam paper (+ optional answer key) to PDF bytes.

    KEY FIXES vs original:
    - doc.build() called ONCE (original called it before answer key appended)
    - Unicode sub/superscripts converted to ReportLab XML tags (no black boxes)
    - Markdown divider rows (|---|---) skipped
    - Section headers get distinct styled paragraphs
    - Separator lines render as thin HR rules
    - Safe font registration (no crash on double-register)
    - Table columns auto-sized
    """

    buffer = BytesIO()

    # --- Font registration (idempotent) ---
    font_path      = os.path.join("static", "fonts", "DejaVuSans.ttf")
    font_bold_path = os.path.join("static", "fonts", "DejaVuSans-Bold.ttf")

    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    except Exception:
        pass

    bold_font = "DejaVu"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
        bold_font = "DejaVu-Bold"
    except Exception:
        pass

    # --- Document ---
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
    )

    # --- Styles ---
    styles = getSampleStyleSheet()
    ACCENT   = HexColor("#1a237e")
    KEY_RED  = HexColor("#b71c1c")

    def add_style(name, **kwargs):
        if name not in styles:
            styles.add(ParagraphStyle(name=name, **kwargs))

    add_style("ExamTitle",
        fontName=bold_font, fontSize=16, alignment=TA_CENTER,
        textColor=ACCENT, spaceAfter=4, spaceBefore=0)

    add_style("ExamSubtitle",
        fontName="DejaVu", fontSize=11, alignment=TA_CENTER,
        textColor=HexColor("#444444"), spaceAfter=14)

    add_style("SectionHeader",
        fontName=bold_font, fontSize=12, textColor=ACCENT,
        spaceBefore=14, spaceAfter=6)

    add_style("ExamBody",
        fontName="DejaVu", fontSize=10.5,
        leading=16, spaceAfter=4, alignment=TA_JUSTIFY)

    add_style("DiagramBox",
        fontName="DejaVu", fontSize=10, leading=14, spaceAfter=8,
        textColor=HexColor("#555555"),
        borderColor=HexColor("#aaaaaa"), borderWidth=1,
        borderPad=6, backColor=HexColor("#f5f5f5"))

    add_style("KeyTitle",
        fontName=bold_font, fontSize=14, alignment=TA_CENTER,
        textColor=KEY_RED, spaceAfter=10)

    add_style("KeyBody",
        fontName="DejaVu", fontSize=10,
        leading=15, spaceAfter=3)

    # ---- Build elements list ----
    elements = []

    # Title block
    elements.append(Paragraph(sanitize_line(subject), styles["ExamTitle"]))
    if chapter:
        elements.append(
            Paragraph(sanitize_line(f"Chapter: {chapter}"), styles["ExamSubtitle"])
        )
    elements.append(
        HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=12)
    )

    # ---- Parse body lines ----
    lines = text.split("\n")
    table_data  = []
    in_table    = False

    def flush_table():
        nonlocal table_data, in_table
        if not table_data:
            return
        max_cols = max(len(r) for r in table_data)
        normalized = [r + [""] * (max_cols - len(r)) for r in table_data]
        col_w = (A4[0] - 100) / max(max_cols, 1)
        tbl = Table(normalized, colWidths=[col_w] * max_cols)
        tbl.setStyle(TableStyle([
            ("FONTNAME",       (0, 0), (-1, -1), "DejaVu"),
            ("FONTSIZE",       (0, 0), (-1, -1), 9.5),
            ("BACKGROUND",     (0, 0), (-1, 0),  HexColor("#e8eaf6")),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  ACCENT),
            ("FONTNAME",       (0, 0), (-1, 0),  bold_font),
            ("GRID",           (0, 0), (-1, -1), 0.5, HexColor("#9e9e9e")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [HexColor("#ffffff"), HexColor("#f3f3f3")]),
            ("PADDING",        (0, 0), (-1, -1), 6),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(Spacer(1, 6))
        elements.append(tbl)
        elements.append(Spacer(1, 10))
        table_data.clear()
        in_table = False

    for line in lines:
        raw = line.rstrip()

        # Table row
        if is_table_row(raw):
            if is_divider_row(raw):
                continue  # skip |---|---| separators
            cells = [
                sanitize_line(c.strip())
                for c in raw.split("|")
                if c.strip()
            ]
            if cells:
                table_data.append(cells)
                in_table = True
            continue
        else:
            if in_table:
                flush_table()

        # Empty line
        if not raw.strip():
            elements.append(Spacer(1, 6))
            continue

        # Horizontal rule
        if is_separator_line(raw):
            elements.append(HRFlowable(
                width="100%", thickness=0.5,
                color=HexColor("#cccccc"),
                spaceBefore=4, spaceAfter=4
            ))
            continue

        # Diagram placeholder
        if raw.strip().startswith("[DIAGRAM:"):
            safe = sanitize_line(raw.strip())
            elements.append(Paragraph(f"<i>{safe}</i>", styles["DiagramBox"]))
            elements.append(Spacer(1, 8))
            continue

        # Section header
        if is_section_header(raw):
            safe = sanitize_line(raw.strip())
            elements.append(Paragraph(f"<b>{safe}</b>", styles["SectionHeader"]))
            continue

        # Normal body line — process markdown bold/italic
        safe = sanitize_line(raw)
        safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
        safe = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', safe)
        elements.append(Paragraph(safe, styles["ExamBody"]))

    if in_table:
        flush_table()

    # ---- Answer Key section ----
    if include_key and answer_key and answer_key.strip():
        elements.append(PageBreak())
        elements.append(
            HRFlowable(width="100%", thickness=2, color=KEY_RED, spaceAfter=10)
        )
        elements.append(Paragraph("ANSWER KEY", styles["KeyTitle"]))
        elements.append(
            HRFlowable(width="100%", thickness=1, color=KEY_RED, spaceAfter=10)
        )
        for line in answer_key.split("\n"):
            raw = line.rstrip()
            if not raw.strip():
                elements.append(Spacer(1, 4))
                continue
            safe = sanitize_line(raw)
            safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
            elements.append(Paragraph(safe, styles["KeyBody"]))

    # ---- Build PDF ONCE (critical bug fix) ----
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ==========================================
# PROMPT BUILDER
# ==========================================
def build_prompt(
    class_name, subject, chapter, board,
    exam_type, difficulty, marks, suggestions
):
    """
    Clean ASCII-only prompt. No box-drawing chars.
    Instructs model to avoid Unicode math symbols that corrupt PDF.
    """
    subj_lower = (subject or "").lower()
    is_stem = any(k in subj_lower for k in [
        "math", "maths", "physics", "chemistry",
        "science", "biology", "computer"
    ])

    notation_block = ""
    if is_stem:
        notation_block = """
--------------------------------------------------
NOTATION RULES (MANDATORY — PDF COMPATIBILITY)
--------------------------------------------------
Write ALL math/science notation in plain ASCII:
  Superscripts : x^2, a^3, 10^-19   (NOT x2, a3)
  Subscripts   : H_2O, CO_2          (NOT H2O)
  Square root  : sqrt(144)           (NOT sqrt symbol)
  Fractions    : 3/4 or (a+b)/(c+d)
  Pi           : pi                  (NOT symbol)
  Greek letters: theta, alpha, beta  (NOT th, a, b)
  Arrows       : -->  or  ->         (NOT arrow symbol)
  Multiply     : *  or  x            (NOT x symbol)
  Degree       : degrees             (NOT degree symbol)

REASON: Unicode math symbols render as black boxes in PDF.
"""

    suggestions_block = (
        f"\nSPECIAL INSTRUCTIONS (OVERRIDE DEFAULTS):\n{suggestions}\n"
        if suggestions and suggestions.strip()
        else ""
    )

    return f"""You are a senior board examination authority. Generate a complete, official-quality exam paper.

==================================================
CRITICAL OUTPUT RULES
==================================================
1. Plain ASCII text ONLY — no Unicode math/science symbols.
2. No box-drawing characters (=== --- is fine, but not Unicode box chars).
3. Separate the Answer Key with exactly this line on its own:
       ANSWER KEY
4. Every question must show mark value in brackets: [2 Marks]
5. Do NOT add any preamble — start directly with the exam header.
{suggestions_block}
==================================================
EXAM DETAILS
==================================================
Class        : {class_name or "Not specified"}
Subject      : {subject or "Not specified"}
Chapter      : {chapter or "Full Syllabus"}
Board / Exam : {board}
Exam Type    : {exam_type or "Standard"}
Difficulty   : {difficulty}
Total Marks  : {marks}
==================================================
REQUIRED STRUCTURE (follow exactly)
==================================================

[EXAM HEADER]
  - School / Institution name: ________________________
  - Subject, Class, Board, Date
  - Total Marks: {marks}  |  Time Allowed: 3 Hours

[GENERAL INSTRUCTIONS]
  - 5 to 6 numbered instructions

SECTION A - Objective Questions
  (MCQ, fill-in-blanks, true/false — 1 mark each)
  Minimum 10 questions totalling approx 20% of {marks} marks.

SECTION B - Short Answer Questions
  (2-3 marks each)
  Minimum 6 questions totalling approx 30% of {marks} marks.

SECTION C - Long Answer Questions
  (5 marks each, with sub-parts if needed)
  Minimum 4 questions totalling approx 30% of {marks} marks.

SECTION D - Case Study / Application
  (A passage or scenario followed by 3-4 questions)
  Total approx 20% of {marks} marks.

ANSWER KEY
  - MCQ answers: Q1. (B), Q2. (A) ...
  - Short answers: key points only
  - Long answers: step-by-step solutions
  - Case study: detailed answers
{notation_block}
==================================================
QUALITY REQUIREMENTS
==================================================
- Questions must match {board} syllabus for Class {class_name}.
- Difficulty level: {difficulty}
- No two questions should test the same concept.
- MCQ options labeled (A) (B) (C) (D)
- Mark distribution must total exactly {marks}.

Generate the complete exam paper now.
"""


# ==========================================
# GEMINI: multi-model retry with 429 handling
# ==========================================
def call_gemini(prompt: str) -> tuple:
    """
    Returns (generated_text, error_message).
    Tries each model in GEMINI_MODELS in order.
    On 429 quota error, immediately moves to next model.
    On other errors, retries once then moves on.
    """
    if not (GEMINI_KEY and GENAI_AVAILABLE):
        return None, "Gemini not configured (missing API key or library)."

    last_error = "No models attempted."

    for model_name in GEMINI_MODELS:
        for attempt in range(2):  # max 2 attempts per model
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
                break  # try next model

            except Exception as e:
                err_str = str(e)
                last_error = f"{model_name} (attempt {attempt+1}): {err_str}"

                # 429 = quota exhausted — no point retrying same model
                if "429" in err_str or "quota" in err_str.lower():
                    time.sleep(1)
                    break  # next model

                # Other error — wait and retry once
                if attempt == 0:
                    time.sleep(1.5)
                    continue

                break  # next model

    return None, last_error


# ==========================================
# FALLBACK LOCAL PAPER
# ==========================================
def build_local_paper(cls, subject, chapter, marks, difficulty):
    return f"""{subject or "General"} Question Paper
Class: {cls}   |   Marks: {marks}   |   Time: 3 Hours
Chapter: {chapter or "Full Syllabus"}   |   Difficulty: {difficulty}

General Instructions:
1. All questions are compulsory.
2. Read each question carefully.
3. Marks for each question are in brackets.
4. Attempt all sections.
5. Write clearly and neatly.

SECTION A - Objective Questions [20 Marks]

1. Choose the correct option:                          [1 Mark]
   (A) Option 1   (B) Option 2   (C) Option 3   (D) Option 4

2. Fill in the blank: ________________               [1 Mark]

3. State whether True or False: ________________     [1 Mark]

SECTION B - Short Answer Questions [30 Marks]

4. Explain the main concept of this chapter.         [3 Marks]

5. What are the key characteristics? Give examples.  [3 Marks]

6. Describe the importance of this topic.            [3 Marks]

SECTION C - Long Answer Questions [30 Marks]

7. Describe in detail the important principles with examples. [5 Marks]

8. Analyze the key aspects and their real-world applications. [5 Marks]

SECTION D - Case Study [20 Marks]

9. Read the following passage and answer the questions:
   [A scenario related to {chapter or "the topic"} would appear here.]

   (a) What is the main idea presented?              [5 Marks]
   (b) Analyze the implications described.           [5 Marks]
   (c) Suggest improvements or alternatives.        [5 Marks]
   (d) Connect this to real-world examples.          [5 Marks]

ANSWER KEY

1. (B) Option 2
2. [Expected answer for the blank]
3. True/False with brief justification
4. Main concept: [3 key points with explanation]
5. Characteristics: point 1, point 2, point 3 with examples
6. Importance: introduction, 2 main reasons, conclusion
7. Detailed explanation: introduction, principles, examples, conclusion
8. Analysis: aspects listed, applications explained, conclusion
9. (a) Main idea: [answer]
   (b) Implications: [analysis]
   (c) Suggestions: [alternatives]
   (d) Real-world: [examples]
"""


# ==========================================
# ROUTES
# ==========================================
@app.route("/")
def index():
    return render_template("index.html")


# ==========================================
# GENERATE PAPER
# ==========================================
@app.route("/generate", methods=["POST"])
def generate():
    try:
        is_form = bool(request.form)
        data = request.form if is_form else (request.get_json(force=True) or {})

        # Extract fields
        class_name       = (data.get("class") or "").strip()
        subject          = (data.get("subject") or "").strip()
        chapter          = (data.get("chapter") or "").strip()
        marks            = (data.get("marks") or "100").strip()
        difficulty       = (data.get("difficulty") or "Medium").strip()
        state            = (data.get("state") or "").strip()
        competitive_exam = (data.get("competitiveExam") or "").strip()
        exam_type        = (data.get("examType") or "").strip()
        suggestions      = (data.get("suggestions") or "").strip()

        # Board string
        if exam_type == "state-board" and state:
            board = f"{state} State Board"
        elif exam_type == "competitive" and competitive_exam:
            board = competitive_exam
        else:
            board = (data.get("board") or "Standard Curriculum").strip()

        # Full-syllabus subject fallback
        if not subject and (data.get("scope") == "all" or data.get("all_chapters")):
            subject = "Mixed Subjects"

        use_fallback = str(data.get("use_fallback", "false")).lower() in ("true", "1", "yes")

        # Build prompt (allow client override)
        prompt = data.get("prompt") or build_prompt(
            class_name, subject, chapter, board,
            exam_type, difficulty, marks, suggestions
        )

        # Generate
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
                    "success":    False,
                    "error":      "AI generation failed. All Gemini models exhausted or quota exceeded.",
                    "api_error":  api_error,
                    "suggestion": (
                        "Your Gemini free-tier daily quota is exhausted. Options:\n"
                        "1. Upgrade at https://ai.google.dev/pricing\n"
                        "2. Wait until quota resets (usually midnight Pacific Time)\n"
                        "3. Add use_fallback=true to get a template-based paper"
                    ),
                    "prompt": prompt,
                }), 502

        # Split answer key
        paper, key = split_key(generated_text)

        # PDF-only mode
        if data.get("pdf_only"):
            include_key_flag = str(data.get("includeKey", "false")).lower() == "true"
            answer_text = data.get("answer_key") or key or ""

            pdf_bytes = create_exam_pdf(
                paper,
                subject or "Question Paper",
                chapter or "",
                answer_key=answer_text,
                include_key=include_key_flag,
            )
            filename = (
                f"{subject or 'Exam'}_{chapter or 'Paper'}_Question_Paper.pdf"
                .replace(" ", "_").replace("/", "-")
            )
            return send_file(
                BytesIO(pdf_bytes),
                as_attachment=True,
                download_name=filename,
                mimetype="application/pdf",
            )

        # Normal JSON response
        return jsonify({
            "success":      True,
            "paper":        paper,
            "answer_key":   key,
            "api_error":    api_error,
            "prompt":       prompt,
            "scope":        data.get("scope") or ("all" if data.get("all_chapters") else "single"),
            "used_fallback": use_fallback,
        })

    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error":   str(e),
            "trace":   traceback.format_exc(),
        }), 500


# ==========================================
# SEPARATE PDF DOWNLOAD ENDPOINT
# ==========================================
@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    """
    Client sends already-generated paper text + optional answer key.
    Decouples AI generation from PDF rendering for better error isolation.
    """
    try:
        data = request.get_json(force=True) or {}

        paper_text  = data.get("paper", "")
        answer_key  = data.get("answer_key", "")
        subject     = (data.get("subject") or "Question Paper").strip()
        chapter     = (data.get("chapter") or "").strip()
        include_key = str(data.get("includeKey", "false")).lower() == "true"

        if not paper_text.strip():
            return jsonify({"success": False, "error": "No paper text provided"}), 400

        pdf_bytes = create_exam_pdf(
            paper_text, subject, chapter,
            answer_key=answer_key,
            include_key=include_key,
        )

        filename = (
            f"{subject}_{chapter}_Paper.pdf"
            .replace(" ", "_").replace("/", "-")
        )
        return send_file(
            BytesIO(pdf_bytes),
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf",
        )

    except Exception as e:
        import traceback
        return jsonify({
            "success": False,
            "error":   str(e),
            "trace":   traceback.format_exc(),
        }), 500


# ==========================================
# HEALTH
# ==========================================
@app.route("/health")
def health():
    return jsonify({
        "status":          "ok",
        "gemini":          "configured" if (GEMINI_KEY and GENAI_AVAILABLE) else "not configured",
        "models_priority": GEMINI_MODELS,
    })


# ==========================================
# CHAPTERS
# ==========================================
@app.route("/chapters")
def chapters():
    try:
        data_path = Path("data/curriculum.json")
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


# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=False)