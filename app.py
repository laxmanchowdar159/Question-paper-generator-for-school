import os
import re
import json
from pathlib import Path
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.colors import black, grey
from flask import Flask, render_template, request, jsonify, send_file

try:
    import google.generativeai as genai
except Exception:
    genai = None



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

api_key = os.environ.get("GEMINI_API_KEY")

if api_key and genai:
    genai.configure(api_key=api_key)


# ==========================================
# UTIL FUNCTIONS
# ==========================================

def split_key(text: str):
    parts = re.split(r'(?i)answer key[:]?\s*', text, maxsplit=1)
    if len(parts) > 1:
        return parts[0].strip(), parts[1].strip()
    return text.strip(), None


# ==========================================
# PDF GENERATOR (FULLY FIXED)
# ==========================================

def create_exam_pdf(text, subject, chapter, answer_key=None, include_key=False):
    """Return bytes of a PDF containing *text* (the paper).

    If *include_key* is True and *answer_key* is provided, append an
    answer-key page after the main paper.
    """

    buffer = BytesIO()

    font_path = os.path.join("static", "fonts", "DejaVuSans.ttf")

    pdfmetrics.registerFont(TTFont("DejaVu", font_path))

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='ExamTitle',
        fontName='DejaVu',
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=20
    ))

    styles.add(ParagraphStyle(
        name='ExamBody',
        fontName='DejaVu',
        fontSize=11,
        leading=16,
        spaceAfter=6
    ))

    elements = []

    # Title
    title = f"{subject} - {chapter}"
    elements.append(Paragraph(title, styles['ExamTitle']))

    lines = text.split("\n")

    table_data = []
    in_table = False

    for line in lines:

        # Handle table markdown
        if "|" in line:

            parts = [p.strip() for p in line.split("|") if p.strip()]

            if parts:
                table_data.append(parts)
                in_table = True

            continue

        else:

            if in_table and table_data:

                table = Table(table_data)

                table.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,-1), 'DejaVu'),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('GRID', (0,0), (-1,-1), 0.5, grey),
                    ('PADDING', (0,0), (-1,-1), 6)
                ]))

                elements.append(table)
                elements.append(Spacer(1, 10))

                table_data = []
                in_table = False

        # Handle diagram placeholder
        if line.startswith("[DIAGRAM:"):

            elements.append(Paragraph(
                f"<i>{line}</i>",
                styles['ExamBody']
            ))

            elements.append(Spacer(1, 10))

            continue

        # Normal text
        if line.strip():

            elements.append(
                Paragraph(line.replace(" ", "&nbsp;"), styles['ExamBody'])
            )

    doc.build(elements)

    # optionally append answer key
    if include_key and answer_key:
        elements.append(PageBreak())
        elements.append(Paragraph("Answer Key", styles['ExamTitle']))
        for line in answer_key.split("\n"):
            if line.strip():
                elements.append(Paragraph(line.replace(" ", "&nbsp;"), styles['ExamBody']))

    pdf_bytes = buffer.getvalue()
    buffer.close()

    return pdf_bytes

# ==========================================
# FALLBACK GENERATOR
# ==========================================

def build_local_paper(cls, subject, chapter, marks, difficulty):

    paper = f"""
{subject} Question Paper
Class: {cls}
Chapter: {chapter or 'Full syllabus'}
Marks: {marks}
Difficulty: {difficulty}

SECTION A
1. Define key concept.

SECTION B
2. Explain important principle.

SECTION C
3. Solve analytical question.

SECTION D
4. Case study problem.

ANSWER KEY
1. Definition
2. Explanation
3. Solution
4. Case explanation
"""

    return paper


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

        # Detect form or JSON
        is_form = bool(request.form)

        data = request.form if is_form else request.get_json(force=True)

        # Core fields
        class_name = data.get("class", "")
        subject = data.get("subject", "")
        chapter = data.get("chapter", "")
        marks = data.get("marks", "100")
        difficulty = data.get("difficulty", "Medium")
        # determine board/exam information from form
        state = data.get("state", "")
        competitive_exam = data.get("competitiveExam", "")
        exam_type = data.get("examType", "")

        # determine board string based on explicit type
        if exam_type == "state-board" and state:
            board = f"{state} State Board"
        elif exam_type == "competitive" and competitive_exam:
            board = competitive_exam
        else:
            board = data.get("board", "Standard Curriculum")

        suggestions = data.get("suggestions", "")
        generated_text = None
        api_error = None
        prompt = None

        # if the user didn't pick a subject and we are generating a
        # full‑syllabus paper, give the model a generic value instead of blank
        if not subject and (data.get("scope") == "all" or data.get("all_chapters")):
            subject = "Mixed Subjects"

        # prepare prompt even if we don't call Gemini (useful for debugging)
        prompt = f"""
You are a senior official examination authority responsible for creating real board-level exam papers.

Your output must be equivalent to official CBSE, ICSE, IB, or State Board exam papers.

═══════════════════════════════════════
TOP PRIORITY INSTRUCTION (CRITICAL)
═══════════════════════════════════════

If EXTRA INSTRUCTIONS are provided below, they OVERRIDE all defaults and MUST be followed exactly.

EXTRA INSTRUCTIONS:
{suggestions if suggestions else "None"}

═══════════════════════════════════════
EXAM DETAILS
═══════════════════════════════════════

Class: {class_name}
Subject: {subject or "(none)"}
Chapter: {chapter or "Full syllabus"}
Board/Exam: {board}
Exam Type: {exam_type or "Standard"}
Difficulty: {difficulty}
Total Marks: {marks}

═══════════════════════════════════════
MANDATORY OUTPUT STRUCTURE
═══════════════════════════════════════

The paper MUST include:

1. Professional Exam Header
2. Instructions Section
3. Section A — Objective (MCQ)
4. Section B — Short Answer
5. Section C — Long Answer
6. Section D — Case Study / Application
7. Answer Key with Solutions

═══════════════════════════════════════
MATHEMATICS REQUIREMENTS
═══════════════════════════════

Include real mathematical notation:

Examples:

• a² + b² = c²  
• √144 = 12  
• ∫ x dx  
• θ, α, β symbols  
• Fractions like ½, ¾  

═══════════════════════════════════════
SCIENCE REQUIREMENTS
═══════════════════════════════════════

Include where appropriate:

• Physics formulas: F = ma, V = IR
• Chemistry equations: H₂ + O₂ → H₂O
• Units: m/s, Newton, Joule, Volt
• Scientific notation: 1.6 × 10⁻¹⁹

═══════════════════════════════════════
TABLE REQUIREMENTS
═══════════════════════════════════════

Use Markdown tables where needed:

Example:

| Quantity | Symbol | Unit |
|----------|--------|------|
| Force    | F      | Newton |

═══════════════════════════════════════
DIAGRAM REQUIREMENTS
═══════════════════════════════

Insert placeholders like:

[DIAGRAM: Right triangle ABC with right angle at B]

[DIAGRAM: Electric circuit with battery and resistor]

═══════════════════════════════════════
QUALITY REQUIREMENTS
═══════════════════════════════════════

Ensure:

• Real exam difficulty
• Correct syllabus concepts
• Proper marks distribution
• No repetition
• Professional formatting
• Clear numbering
• Step-by-step solutions

═══════════════════════════════════════

Generate complete paper now.
"""

        # allow override from client
        if data.get("prompt"):
            prompt = data.get("prompt")

        # ==========================================
        # GEMINI GENERATION
        # ==========================================

        # automatically fall back if we don't have an API key or the library
        # isn't imported successfully; this prevents unexpected 502s
        use_fallback = bool(data.get("use_fallback")) or not (api_key and genai)

        if api_key and genai and not use_fallback:

            try:
                # Try latest model first, fallback to older versions if needed
                model_names = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-pro"]
                model = None
                for model_name in model_names:
                    try:
                        model = genai.GenerativeModel(model_name)
                        break
                    except Exception:
                        continue
                if not model:
                    raise Exception("No compatible Gemini models available")

                response = model.generate_content(prompt)

                if response and hasattr(response, "text") and response.text.strip():
                    generated_text = response.text.strip()
                else:
                    api_error = "Empty response from Gemini"
            except Exception as e:
                api_error = str(e)
        else:
            # note for debugging that fallback was chosen automatically
            if not (api_key and genai):
                api_error = "No Gemini API key/library available; using local fallback."
            elif use_fallback:
                api_error = "Requested fallback generation."

        # ==========================================
        # FALLBACK GENERATOR (only used when expressly allowed)
        # ==========================================

        if not generated_text:
            if use_fallback:
                generated_text = build_local_paper(
                    class_name,
                    subject,
                    chapter,
                    marks,
                    difficulty
                )
            else:
                # bail out with error message
                return jsonify({
                    "success": False,
                    "error": "AI generation failed",
                    "api_error": api_error,
                    "prompt": prompt
                }), 502


        # ==========================================
        # SPLIT PAPER AND ANSWER KEY
        # ==========================================

        paper, key = split_key(generated_text)


        # ==========================================
        # PDF REQUEST HANDLING
        # ==========================================

        if data.get("pdf_only"):

            # generate the text (we already ran model above) then render
            text_for_pdf = generated_text

            if not text_for_pdf:
                # early return so client sees error instead of an empty 200
                return jsonify({
                    "success": False,
                    "error": "No paper content available for PDF"
                }), 400

            include_key_flag = bool(data.get("includeKey"))
            answer_text = data.get("answer_key") or ""

            pdf_bytes = create_exam_pdf(
                text_for_pdf,
                subject or "Question Paper",
                chapter or "",
                answer_key=answer_text,
                include_key=include_key_flag
            )

            filename = f"{subject or 'Exam'}_{chapter or ''}_Question_Paper.pdf".replace(" ", "_")

            return send_file(
                BytesIO(pdf_bytes),
                as_attachment=True,
                download_name=filename,
                mimetype="application/pdf"
            )


        # ==========================================
        # NORMAL RESPONSE
        # ==========================================

        return jsonify({

            "success": True,

            "paper": paper,

            "answer_key": key,

            "api_error": api_error,

            "prompt": prompt,

            # echo scope for client awareness ("all" vs "single")
            "scope": data.get("scope") or ("all" if data.get("all_chapters") else "single"),

            # inform client when fallback was used
            "used_fallback": use_fallback

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500

# ==========================================
# HEALTH
# ==========================================

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


# ==========================================
# CHAPTERS
# ==========================================

@app.route("/chapters")
def chapters():

    try:

        data_path = Path("data/curriculum.json")

        if not data_path.exists():
            return jsonify({"success": False})

        with open(data_path, encoding="utf-8") as f:
            data = json.load(f)

        # If a class query param is provided, return only that class's subjects
        cls = request.args.get("class") or request.args.get("cls")

        if cls and cls in data:
            return jsonify({
                "success": True,
                "data": data[cls]
            })

        # Otherwise return full dataset
        return jsonify({
            "success": True,
            "data": data
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        })


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 3000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )