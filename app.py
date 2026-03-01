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
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.colors import HexColor

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

# -------------------------------------------------------
# EXACT model IDs visible in your rate-limits screenshot.
# Ordered best-first. Sunset models (gemini-pro,
# gemini-1.0-pro) are intentionally excluded.
# -------------------------------------------------------
PREFERRED_MODELS = [
    "gemini-2.5-flash",           # best free tier — 5 RPM, 255K TPM
    "gemini-2.5-flash-lite",      # lightweight 2.5 variant
    "gemini-2.0-flash",           # stable workhorse
    "gemini-2.0-flash-lite",      # lighter 2.0
    "gemini-2.0-flash-exp",       # experimental 2.0
    "gemini-1.5-flash",           # 5 RPM, 255K TPM
    "gemini-1.5-flash-8b",        # smallest, still works
    "gemini-1.5-pro",             # paid tier, high quality
    "gemini-2.5-pro",             # paid tier
]

# Runtime-discovered models (populated once via ListModels)
_discovered_models: list = []
_discovery_done: bool = False


def discover_models() -> list:
    """
    Query the live Gemini ListModels endpoint once per process.
    Returns model short-names that support generateContent,
    sorted to match PREFERRED_MODELS priority order.
    Falls back to PREFERRED_MODELS if discovery fails or API key missing.
    """
    global _discovered_models, _discovery_done
    if _discovery_done:
        return _discovered_models

    _discovery_done = True  # only attempt once

    if not (GEMINI_KEY and GENAI_AVAILABLE):
        _discovered_models = PREFERRED_MODELS[:]
        return _discovered_models

    try:
        available = set()
        for m in genai.list_models():
            methods = getattr(m, "supported_generation_methods", []) or []
            if "generateContent" in methods:
                # m.name is like "models/gemini-2.5-flash"
                short = m.name.split("/")[-1] if "/" in m.name else m.name
                available.add(short)

        # Respect preference order, then append discovered extras
        ordered = [p for p in PREFERRED_MODELS if p in available]
        for m in available:
            if m not in ordered and "embed" not in m and "aqa" not in m:
                ordered.append(m)

        _discovered_models = ordered if ordered else PREFERRED_MODELS[:]
    except Exception:
        _discovered_models = PREFERRED_MODELS[:]

    return _discovered_models


# ==========================================
# UTIL: SPLIT PAPER / ANSWER KEY
# ==========================================
def split_key(text: str):
    """Split generated text into (paper_body, answer_key)."""
    patterns = [
        r'\n\s*={3,}\s*\n\s*answer\s+key\s*\n',
        r'\n\s*-{3,}\s*\n\s*answer\s+key\s*\n',
        r'\n\s*answer\s+key[:\s]*\n',
        r'\nANSWER KEY\n',
        r'\nAnswer Key\n',
        r'(?i)\nANSWER KEY:?\s*\n',
    ]
    for pat in patterns:
        parts = re.split(pat, text, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    # Last-resort inline split
    parts = re.split(r'(?i)answer\s+key[:\s]+', text, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return text.strip(), None


# ==========================================
# SAFE TEXT: Unicode -> ReportLab XML
# ==========================================
def sanitize_line(text: str) -> str:
    """
    Make a raw text line safe for ReportLab Paragraph XML.

    Execution order matters:
      1. Escape & < > (XML safety)
      2. Unicode superscript/subscript digits -> <super>/<sub> tags
      3. Math/science unicode -> XML entities  (&#NNN;)
      4. Strip box-drawing chars that leak from prompts
    """
    # 1. XML escape
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # 2. Unicode SUPERSCRIPTS -> <super>
    for ch, val in {
        "\u2070":"0","\u00b9":"1","\u00b2":"2","\u00b3":"3",
        "\u2074":"4","\u2075":"5","\u2076":"6","\u2077":"7",
        "\u2078":"8","\u2079":"9","\u207f":"n","\u2071":"i",
    }.items():
        text = text.replace(ch, f"<super rise='3' size='8'>{val}</super>")

    # 3. Unicode SUBSCRIPTS -> <sub>
    for ch, val in {
        "\u2080":"0","\u2081":"1","\u2082":"2","\u2083":"3",
        "\u2084":"4","\u2085":"5","\u2086":"6","\u2087":"7",
        "\u2088":"8","\u2089":"9",
    }.items():
        text = text.replace(ch, f"<sub rise='-2' size='8'>{val}</sub>")

    # 4. Math/science unicode -> XML numeric entities
    for ch, ent in {
        "\u2192":"&#8594;", "\u2190":"&#8592;", "\u2194":"&#8596;",
        "\u21cc":"&#8652;", "\u27f6":"&#10230;",
        "\u2022":"&#8226;", "\u00b7":"&#183;",
        "\u00b0":"&#176;",  "\u00d7":"&#215;",  "\u00f7":"&#247;",
        "\u00b1":"&#177;",  "\u2264":"&#8804;", "\u2265":"&#8805;",
        "\u2260":"&#8800;", "\u2248":"&#8776;", "\u221e":"&#8734;",
        "\u2211":"&#8721;", "\u222b":"&#8747;", "\u2202":"&#8706;",
        "\u221a":"&#8730;", "\u03c0":"&#960;",  "\u03b8":"&#952;",
        "\u03b1":"&#945;",  "\u03b2":"&#946;",  "\u03b3":"&#947;",
        "\u03b4":"&#948;",  "\u03bb":"&#955;",  "\u03bc":"&#956;",
        "\u03c3":"&#963;",  "\u03c9":"&#969;",  "\u0394":"&#916;",
        "\u03a9":"&#937;",  "\u00bd":"&#189;",  "\u00bc":"&#188;",
        "\u00be":"&#190;",  "\u2212":"&#8722;",
    }.items():
        text = text.replace(ch, ent)

    # 5. Strip box-drawing / border chars
    for ch in "═║╔╗╚╝╠╣╦╩╬─│┌┐└┘├┤┬┴┼\u2550\u2551":
        text = text.replace(ch, "")

    return text


# ==========================================
# LINE-TYPE HELPERS
# ==========================================
def is_separator_line(line: str) -> bool:
    return bool(re.match(r'^[=\-_]{3,}$', line.strip()))


def is_section_header(line: str) -> bool:
    s = line.strip()
    if re.match(r'^(SECTION|Section|PART|Part)\s+[A-Da-d](\s|[-:]|$)', s):
        return True
    if re.match(
        r'^(General Instructions|Instructions|ANSWER KEY|Answer Key|'
        r'EXAMINATION PAPER|Question Paper|Exam Header)',
        s, re.IGNORECASE
    ):
        return True
    clean = re.sub(r'[^A-Za-z\s]', '', s)
    if clean.strip() == clean.strip().upper() and 4 < len(clean.strip()) < 80:
        return True
    return False


def is_table_row(line: str) -> bool:
    return line.count("|") >= 2


def is_divider_row(line: str) -> bool:
    return bool(re.match(r'^\|[\s\-:|]+\|$', line.strip()))


# ==========================================
# PDF GENERATOR
# ==========================================
def create_exam_pdf(
    text: str,
    subject: str,
    chapter: str,
    answer_key: str = None,
    include_key: bool = False,
) -> bytes:
    """
    Renders exam paper (+ optional answer key) to PDF bytes.

    Key fixes vs original:
    - doc.build() called ONCE after ALL elements assembled
      (original called it before appending the answer-key page — key was lost)
    - Unicode math converted via sanitize_line() before ReportLab sees it
    - Markdown table divider rows (|---|---) detected & skipped
    - Font registration is idempotent (no double-register crash)
    - Table columns auto-sized to page width
    """
    buffer = BytesIO()

    # ---- Font registration (idempotent) ----
    _base = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(_base, "static", "fonts", "DejaVuSans.ttf")
    font_bold_path = os.path.join(_base, "static", "fonts", "DejaVuSans-Bold.ttf")

    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
    except Exception:
        pass  # already registered

    bold_font = "DejaVu"
    try:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", font_bold_path))
        bold_font = "DejaVu-Bold"
    except Exception:
        pass

    # ---- Document ----
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=50, leftMargin=50,
        topMargin=50, bottomMargin=50,
    )

    ACCENT  = HexColor("#1a237e")
    KEY_RED = HexColor("#b71c1c")

    # ---- Styles ----
    styles = getSampleStyleSheet()

    def add_style(name, **kw):
        if name not in styles:
            styles.add(ParagraphStyle(name=name, **kw))

    add_style("ExamTitle",
        fontName=bold_font, fontSize=16, alignment=TA_CENTER,
        textColor=ACCENT, spaceAfter=4)
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
        fontName="DejaVu", fontSize=10, leading=15, spaceAfter=3)

    # ---- Elements ----
    elements = []

    elements.append(Paragraph(sanitize_line(subject or "Question Paper"), styles["ExamTitle"]))
    if chapter:
        elements.append(Paragraph(sanitize_line(f"Chapter: {chapter}"), styles["ExamSubtitle"]))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT, spaceAfter=12))

    table_data: list = []
    in_table: bool = False

    def flush_table():
        nonlocal table_data, in_table
        if not table_data:
            return
        max_cols = max(len(r) for r in table_data)
        rows = [r + [""] * (max_cols - len(r)) for r in table_data]
        col_w = (A4[0] - 100) / max(max_cols, 1)
        tbl = Table(rows, colWidths=[col_w] * max_cols)
        tbl.setStyle(TableStyle([
            ("FONTNAME",       (0,0), (-1,-1), "DejaVu"),
            ("FONTSIZE",       (0,0), (-1,-1), 9.5),
            ("BACKGROUND",     (0,0), (-1, 0), HexColor("#e8eaf6")),
            ("TEXTCOLOR",      (0,0), (-1, 0), ACCENT),
            ("FONTNAME",       (0,0), (-1, 0), bold_font),
            ("GRID",           (0,0), (-1,-1), 0.5, HexColor("#9e9e9e")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1),
             [HexColor("#ffffff"), HexColor("#f3f3f3")]),
            ("PADDING",        (0,0), (-1,-1), 6),
            ("VALIGN",         (0,0), (-1,-1), "MIDDLE"),
        ]))
        elements.append(Spacer(1, 6))
        elements.append(tbl)
        elements.append(Spacer(1, 10))
        table_data.clear()
        in_table = False

    for line in text.split("\n"):
        raw = line.rstrip()

        # ---- Table ----
        if is_table_row(raw):
            if is_divider_row(raw):
                continue
            cells = [sanitize_line(c.strip()) for c in raw.split("|") if c.strip()]
            if cells:
                table_data.append(cells)
                in_table = True
            continue
        else:
            if in_table:
                flush_table()

        # ---- Blank ----
        if not raw.strip():
            elements.append(Spacer(1, 6))
            continue

        # ---- HR ----
        if is_separator_line(raw):
            elements.append(HRFlowable(
                width="100%", thickness=0.5,
                color=HexColor("#cccccc"), spaceBefore=4, spaceAfter=4))
            continue

        # ---- Diagram placeholder ----
        if raw.strip().startswith("[DIAGRAM:"):
            elements.append(
                Paragraph(f"<i>{sanitize_line(raw.strip())}</i>", styles["DiagramBox"]))
            elements.append(Spacer(1, 8))
            continue

        # ---- Section header ----
        if is_section_header(raw):
            elements.append(
                Paragraph(f"<b>{sanitize_line(raw.strip())}</b>", styles["SectionHeader"]))
            continue

        # ---- Normal body ----
        safe = sanitize_line(raw)
        safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
        safe = re.sub(r'\*(.+?)\*',     r'<i>\1</i>', safe)
        elements.append(Paragraph(safe, styles["ExamBody"]))

    if in_table:
        flush_table()

    # ---- Answer Key page ----
    if include_key and answer_key and answer_key.strip():
        elements.append(PageBreak())
        elements.append(HRFlowable(width="100%", thickness=2, color=KEY_RED, spaceAfter=10))
        elements.append(Paragraph("ANSWER KEY", styles["KeyTitle"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=KEY_RED, spaceAfter=10))
        for ln in answer_key.split("\n"):
            raw = ln.rstrip()
            if not raw.strip():
                elements.append(Spacer(1, 4))
                continue
            safe = sanitize_line(raw)
            safe = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe)
            elements.append(Paragraph(safe, styles["KeyBody"]))

    # ---- BUILD ONCE — critical fix (original built too early) ----
    doc.build(elements)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


# ==========================================
# PROMPT BUILDER
# ==========================================
def build_prompt(class_name, subject, chapter, board,
                 exam_type, difficulty, marks, suggestions):
    subj_lower = (subject or "").lower()
    is_stem = any(k in subj_lower for k in [
        "math", "maths", "physics", "chemistry",
        "science", "biology", "computer"
    ])

    notation_block = ""
    if is_stem:
        notation_block = """
--------------------------------------------------
NOTATION RULES - MANDATORY FOR PDF COMPATIBILITY
--------------------------------------------------
Use PLAIN ASCII for all math/science — no Unicode symbols ever:
  Powers       : x^2, a^3, 10^-19     NOT x2 or x squared
  Subscripts   : H_2O, CO_2, O_3      NOT H2O
  Square root  : sqrt(x), sqrt(144)
  Fractions    : 3/4  or  (a+b)/(c+d)
  Pi           : pi
  Greek letters: theta, alpha, beta, delta, lambda, mu
  Arrows       : ->  or  -->
  Multiply     : *  or  x
  Degree       : deg  or  degrees
  Approx equal : ~  or  approx
REASON: Unicode math glyphs render as solid black boxes in PDF output.
--------------------------------------------------
"""

    extra = (
        f"\nSPECIAL INSTRUCTIONS (override all defaults):\n{suggestions}\n"
        if suggestions and suggestions.strip()
        else ""
    )

    return f"""You are a senior board examination authority. Create a complete, official-quality exam paper.

==================================================
CRITICAL OUTPUT RULES
==================================================
1. Plain ASCII ONLY — no Unicode math or science symbols (see notation rules).
2. No Unicode box-drawing characters.
3. End the paper body with exactly this line by itself:
       ANSWER KEY
4. Every question must show its mark value: [2 Marks]
5. Start output directly with the Exam Header — no preamble, no commentary.
{extra}
==================================================
EXAM DETAILS
==================================================
Class        : {class_name or "Not specified"}
Subject      : {subject or "Not specified"}
Chapter/Topic: {chapter or "Full Syllabus"}
Board / Exam : {board}
Exam Type    : {exam_type or "Standard"}
Difficulty   : {difficulty}
Total Marks  : {marks}
==================================================
REQUIRED OUTPUT STRUCTURE (follow exactly)
==================================================

[EXAM HEADER]
  School / Institution: ______________________________
  Subject: {subject}   Class: {class_name}   Board: {board}
  Total Marks: {marks}       Time Allowed: 3 Hours
  Date: ______________

[GENERAL INSTRUCTIONS]
  (6 numbered instructions for students)

SECTION A - Objective Questions  (approx 20% = {int(int(marks)*0.2)} marks)
  - Mix of MCQ, fill-in-blank, and true/false
  - 1 mark each, minimum 10 questions
  - MCQ options labeled (A) (B) (C) (D)

SECTION B - Short Answer Questions  (approx 30% = {int(int(marks)*0.3)} marks)
  - 2 to 3 marks each
  - Minimum 6 questions

SECTION C - Long Answer Questions  (approx 30% = {int(int(marks)*0.3)} marks)
  - 5 marks each, with sub-parts where needed
  - Minimum 4 questions

SECTION D - Case Study / Application  (approx 20% = {int(int(marks)*0.2)} marks)
  - One real-world passage or scenario
  - Followed by 4 sub-questions with marks shown

ANSWER KEY
  Section A: Q1.(B)  Q2.(A)  ... (all answers listed)
  Section B: key points per question (2-3 lines each)
  Section C: step-by-step solutions
  Section D: detailed paragraph answers
{notation_block}
==================================================
QUALITY REQUIREMENTS
==================================================
- Questions must match {board} syllabus for Class {class_name}.
- Difficulty: {difficulty}
- No concept repeated across different questions.
- All marks must sum to exactly {marks}.

Begin the paper now.
"""


# ==========================================
# GEMINI CALL: discover live models + fallback chain
# ==========================================
def call_gemini(prompt: str) -> tuple:
    """
    Returns (generated_text, error_message).
    - Calls ListModels on first use to get live model names.
    - On 429 (quota) or 404 (deprecated): skip to next model immediately.
    - On other errors: retry once, then move on.
    """
    if not (GEMINI_KEY and GENAI_AVAILABLE):
        return None, "Gemini not configured (missing GEMINI_API_KEY or google-generativeai not installed)."

    models_to_try = discover_models()
    if not models_to_try:
        return None, "No Gemini models discovered."

    last_error = ""

    for model_name in models_to_try:
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

                # 429 quota exhausted OR 404 model deprecated/not found
                # → skip immediately, no retry
                if "429" in err_str or "404" in err_str or "quota" in err_str.lower():
                    time.sleep(0.3)
                    break

                # Other transient error → retry once with backoff
                if attempt == 0:
                    time.sleep(1.5)
                    continue

                break  # move to next model

    return None, last_error


# ==========================================
# FALLBACK: local template paper
# ==========================================
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

4. Choose the correct answer:                              [1 Mark]
   (A) Option A   (B) Option B   (C) Option C   (D) Option D

5. Fill in the blank: ________________ is defined as _______.  [1 Mark]

SECTION B - Short Answer Questions [30 Marks]

6. Explain the main concept of {chapter or "this chapter"}.   [3 Marks]

7. State and explain an important theorem or principle.      [3 Marks]

8. Solve the following problem with steps shown.             [3 Marks]

9. Differentiate between two key terms from this chapter.    [3 Marks]

SECTION C - Long Answer Questions [30 Marks]

10. Describe the important principles of {chapter or "this topic"}
    with proofs or derivations where applicable.             [5 Marks]

11. Solve a multi-step problem involving the core concepts.  [5 Marks]

12. Explain with examples how the concepts apply
    to real-world scenarios.                                 [5 Marks]

SECTION D - Case Study [20 Marks]

13. Read the following scenario:
    [A practical situation related to {chapter or "the topic"} is presented.
     Students are expected to apply their conceptual knowledge
     to analyse and solve the following questions.]

    (a) Identify the key concept demonstrated.               [5 Marks]
    (b) Explain the underlying principle involved.           [5 Marks]
    (c) Calculate or determine the required values.          [5 Marks]
    (d) Suggest an improvement or alternative approach.      [5 Marks]

ANSWER KEY

Section A:
1. (B)
2. [Expected answer]
3. True / False — [brief justification]
4. (C)
5. [Expected answer]

Section B:
6. Three key points with brief explanation each.
7. Statement + explanation of the principle.
8. Step 1: setup → Step 2: calculation → Step 3: result.
9. Term A: definition | Term B: definition | Key difference.

Section C:
10. Introduction → Principle → Proof/Derivation → Example → Conclusion.
11. Given → Formula → Substitution → Calculation → Answer with units.
12. Concept → Real-world link → Three examples → Summary.

Section D:
13. (a) Key concept identified and explained.
    (b) Principle stated with reasoning.
    (c) Calculation shown step-by-step with final answer.
    (d) Improvement suggested with justification.
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

        # Extract + clean inputs
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

        # Full-syllabus label
        if not subject and (data.get("scope") == "all" or data.get("all_chapters")):
            subject = "Mixed Subjects"

        use_fallback = str(data.get("use_fallback", "false")).lower() in ("true", "1", "yes")

        # Build prompt (client can override)
        prompt = data.get("prompt") or build_prompt(
            class_name, subject, chapter, board,
            exam_type, difficulty, marks, suggestions
        )

        # ---- Generate ----
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
                    "models_tried": discover_models(),
                    "suggestion": (
                        "All available Gemini models are quota-exhausted or unavailable.\n"
                        "Options:\n"
                        "1. Upgrade your Gemini API plan at https://ai.google.dev/pricing\n"
                        "2. Wait for quota reset (usually midnight US Pacific Time)\n"
                        "3. Send use_fallback=true to get a well-structured template paper immediately"
                    ),
                    "prompt": prompt,
                }), 502

        # Split paper / answer key
        paper, key = split_key(generated_text)

        # ---- PDF-only mode ----
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

        # ---- Normal JSON response ----
        return jsonify({
            "success":       True,
            "paper":         paper,
            "answer_key":    key,
            "api_error":     api_error,
            "prompt":        prompt,
            "scope":         data.get("scope") or ("all" if data.get("all_chapters") else "single"),
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
# DOWNLOAD PDF (separate endpoint)
# ==========================================
@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    """
    Accepts already-generated paper text and returns a PDF.
    Keeps AI generation and PDF rendering fully decoupled.
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
        filename = f"{subject}_{chapter}_Paper.pdf".replace(" ", "_").replace("/", "-")
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
# HEALTH — shows live model list
# ==========================================
@app.route("/health")
def health():
    configured = bool(GEMINI_KEY and GENAI_AVAILABLE)
    models = discover_models() if configured else []
    return jsonify({
        "status":          "ok",
        "gemini":          "configured" if configured else "not configured",
        "models_available": models,
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