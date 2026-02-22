"""
ExamCraft — AI Question Paper Generator
Fixed Flask backend with proper PDF generation and all routes working.
"""

import io
import os
import re
import base64
from typing import Any, Dict, Optional, Tuple

from flask import Flask, render_template, request, jsonify, make_response, send_from_directory
from openai import OpenAI

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
    static_url_path="/static"
)

# ── OpenAI client ──
api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    import warnings
    warnings.warn("OPENAI_API_KEY not set — API calls will fail.", RuntimeWarning)

client = OpenAI(api_key=api_key) if api_key else None


# ══════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════

def split_key(text: str) -> Tuple[str, Optional[str]]:
    """Split answer key from paper text if marker present."""
    parts = re.split(r"(?im)^answer\s+key\s*:?\s*$", text, maxsplit=1)
    if len(parts) == 1:
        # try inline split
        parts = re.split(r"(?i)answer key[:]?\s*", text, maxsplit=1)
    if len(parts) >= 2:
        return parts[0].strip(), parts[1].strip()
    return text.strip(), None


def build_prompt(data: Dict[str, Any]) -> str:
    """Build the GPT prompt from form data."""
    sections_raw = data.get("sections", "")
    sections = sections_raw if sections_raw else "MCQ, Short Answer, Long Answer, Case Study"

    lines = [
        f"You are an expert {data.get('board', 'CBSE')} board exam paper setter for school students.",
        "Generate a complete, professional question paper following the exact board examination format.",
        "",
        "=== PAPER DETAILS ===",
        f"Class      : {data.get('class', '10')}",
        f"Board      : {data.get('board', 'CBSE')}",
        f"Subject    : {data.get('subject', 'Mathematics')}",
    ]

    if data.get("chapter"):
        lines.append(f"Chapter    : {data['chapter']}")

    lines += [
        f"Difficulty : {data.get('difficulty', 'Medium')}",
        f"Total Marks: {data.get('marks', 100)}",
        f"Sections   : {sections}",
        "",
        "=== FORMATTING RULES ===",
        "1. Start with a proper exam header: School name (if provided), Subject, Class, Time, Marks",
        "2. Include general instructions (attempt all / time allowed etc.)",
        "3. Use Section A, B, C, D labels with marks per question clearly mentioned",
        "4. Section A — MCQ (1 mark each) with 4 options (a,b,c,d)",
        "5. Section B — Short Answer (2-3 marks each)",
        "6. Section C — Long Answer (5 marks each)",
        "7. Section D — Case Study / Application (4-5 marks)",
        "8. Ensure total marks add up to exactly the specified total",
        "9. Do NOT include answers in the question paper (unless an answer key section is requested)",
        "10. Use proper numbering and sub-numbering for all questions",
    ]

    if data.get("board") == "Andhra Board":
        lines.append("11. Follow Andhra Pradesh State Board (BSEAP) syllabus and style conventions")

    if data.get("school_name"):
        lines.append(f"School Name: {data['school_name']}")

    if data.get("user_name"):
        lines.append(f"Prepared by: {data['user_name']}")

    if data.get("include_key") in (True, "true", "True"):
        lines += [
            "",
            "=== ANSWER KEY ===",
            "After the question paper, add a clearly separated section.",
            "Begin this section with exactly this text on its own line: ANSWER KEY:",
            "Provide concise answers/key points for all questions.",
        ]

    if data.get("instructions"):
        lines += ["", f"=== EXTRA INSTRUCTIONS ===", data["instructions"]]

    return "\n".join(lines)


# ══════════════════════════════════════════════════
# PDF Generation using fpdf2
# ══════════════════════════════════════════════════

def create_pdf(paper_text: str, key_text: Optional[str], data: Dict[str, Any]) -> bytes:
    """Generate PDF using fpdf2 with Unicode support via a built-in font."""
    try:
        from fpdf import FPDF
        from fpdf.enums import XPos, YPos
    except ImportError:
        raise RuntimeError("fpdf2 not installed. Run: pip install fpdf2")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_left_margin(18)
    pdf.set_right_margin(18)

    # ── Page 1: Question Paper ──
    pdf.add_page()

    # Header band
    pdf.set_fill_color(30, 33, 53)
    pdf.rect(0, 0, 210, 28, style="F")

    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(165, 180, 252)
    school_name = data.get("school_name") or "ExamCraft AI"
    pdf.set_xy(10, 6)
    pdf.cell(0, 10, school_name.upper(), align="C")

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(160, 168, 204)
    pdf.set_xy(10, 17)
    pdf.cell(0, 6, "Powered by ExamCraft AI  •  AI-Generated Question Paper", align="C")

    pdf.ln(16)
    pdf.set_text_color(30, 33, 53)

    # Meta table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 242, 255)
    pdf.set_draw_color(200, 204, 240)
    row_h = 8

    meta = [
        ("Board",    data.get("board", "—")),
        ("Class",    f"Class {data.get('class', '—')}"),
        ("Subject",  data.get("subject", "—")),
        ("Chapter",  data.get("chapter") or "Full Syllabus"),
        ("Marks",    str(data.get("marks", "—"))),
        ("Difficulty", data.get("difficulty", "—")),
    ]
    if data.get("user_name"):
        meta.append(("Prepared by", data["user_name"]))

    col_w = (210 - 36) / 2  # half page width for 2-col layout
    for i, (k, v) in enumerate(meta):
        if i % 2 == 0:
            pdf.set_x(18)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(235, 237, 255)
        pdf.cell(col_w * 0.38, row_h, k + ":", fill=True, border=1)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_fill_color(250, 250, 255)
        pdf.cell(col_w * 0.62, row_h, v, fill=True, border=1)
        if i % 2 == 1 or i == len(meta) - 1:
            pdf.ln()

    pdf.ln(5)

    # Horizontal rule
    pdf.set_draw_color(99, 102, 241)
    pdf.set_line_width(0.5)
    pdf.line(18, pdf.get_y(), 192, pdf.get_y())
    pdf.ln(4)

    # Paper body — clean, readable
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 33, 53)
    pdf.set_line_width(0.2)
    pdf.set_draw_color(200, 200, 200)

    # Parse lines and style them
    for line in paper_text.splitlines():
        stripped = line.strip()
        if not stripped:
            pdf.ln(3)
            continue

        # Section headers
        if re.match(r"^(SECTION|Section)\s+[A-D]", stripped) or re.match(r"^Section\s+[A-D]", stripped):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(99, 102, 241)
            pdf.set_fill_color(240, 242, 255)
            pdf.cell(0, 9, "  " + stripped, fill=True, border=0,
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(30, 33, 53)
            pdf.set_font("Helvetica", "", 10)
            pdf.ln(1)
        # Question numbers
        elif re.match(r"^Q?\d+[\.\)]\s", stripped):
            pdf.set_font("Helvetica", "B", 10)
            _write_wrapped(pdf, stripped)
            pdf.set_font("Helvetica", "", 10)
        # MCQ options
        elif re.match(r"^\([a-d]\)|^[a-d][\.\)]\s", stripped):
            pdf.set_x(28)
            _write_wrapped(pdf, stripped, x_offset=28)
        # Sub-questions
        elif re.match(r"^\(i+\)|\(a\)|\(b\)", stripped):
            pdf.set_x(26)
            _write_wrapped(pdf, stripped, x_offset=26)
        # Instructions / General lines
        elif stripped.startswith("General Instructions") or stripped.startswith("Note:") or stripped.startswith("Time:"):
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 100, 130)
            _write_wrapped(pdf, stripped)
            pdf.set_text_color(30, 33, 53)
            pdf.set_font("Helvetica", "", 10)
        else:
            _write_wrapped(pdf, stripped)

    # ── Page 2: Answer Key (if requested) ──
    if key_text:
        pdf.add_page()

        pdf.set_fill_color(16, 43, 30)
        pdf.rect(0, 0, 210, 22, style="F")
        pdf.set_font("Helvetica", "B", 14)
        pdf.set_text_color(212, 244, 212)
        pdf.set_xy(10, 4)
        pdf.cell(0, 14, "ANSWER KEY", align="C")
        pdf.ln(20)

        pdf.set_text_color(30, 33, 53)
        pdf.set_font("Helvetica", "", 10)

        for line in key_text.splitlines():
            stripped = line.strip()
            if not stripped:
                pdf.ln(3)
                continue
            if re.match(r"^Q?\d+[\.\)]", stripped):
                pdf.set_font("Helvetica", "B", 10)
                _write_wrapped(pdf, stripped)
                pdf.set_font("Helvetica", "", 10)
            else:
                _write_wrapped(pdf, stripped)

    # Output
    raw = pdf.output()
    return bytes(raw) if not isinstance(raw, bytes) else raw


def _write_wrapped(pdf, text: str, x_offset: int = None):
    """Write a line with safe multi-cell wrapping."""
    from fpdf.enums import XPos, YPos
    if x_offset:
        pdf.set_x(x_offset)
    # Replace problematic unicode chars for fpdf latin encoding
    safe = text.encode("latin-1", errors="replace").decode("latin-1")
    pdf.multi_cell(
        0, 6, safe,
        new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )


# ══════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/get-chapters", methods=["POST"])
def get_chapters():
    if not client:
        return jsonify({"success": False, "error": "OpenAI key not set", "chapters": []}), 500

    try:
        data      = request.get_json(force=True) or {}
        cls       = data.get("class", "10")
        subject   = data.get("subject", "Mathematics")
        board     = data.get("board", "CBSE")

        prompt = (
            f"List the chapter names for {subject} in Class {cls} under the {board} curriculum. "
            "Return ONLY a comma-separated list of chapter names, nothing else. No numbers, no descriptions."
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a school curriculum expert. Return concise comma-separated chapter lists only."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )

        raw_chapters = resp.choices[0].message.content.strip()
        chapters = [c.strip().strip('"').strip("'") for c in raw_chapters.split(",") if c.strip()]

        return jsonify({"success": True, "chapters": chapters})

    except Exception as e:
        app.logger.error("get_chapters error", exc_info=e)
        return jsonify({"success": False, "error": str(e), "chapters": []}), 500


@app.route("/generate", methods=["POST"])
def generate():
    if not client:
        return jsonify({"success": False, "error": "OpenAI API key not configured on server"}), 500

    try:
        data = request.get_json(force=True) or {}

        # Defaults
        data.setdefault("board", "CBSE")
        data.setdefault("difficulty", "Medium")
        data.setdefault("marks", 100)

        # Validate
        for field in ["class", "board", "subject", "difficulty", "marks"]:
            if not data.get(field):
                return jsonify({"success": False, "error": f"'{field}' is required"}), 400

        try:
            data["marks"] = int(data["marks"])
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "'marks' must be a number"}), 400

        # Strip empties
        for f in ["user_name", "school_name", "chapter", "instructions"]:
            if f in data and not str(data[f]).strip():
                data[f] = ""

        # Generate text
        prompt = build_prompt(data)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional school examination paper setter. Generate well-structured, curriculum-aligned question papers exactly as instructed."},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )

        full_text = response.choices[0].message.content.strip()

        # Split paper/key
        want_key = data.get("include_key") in (True, "true", "True")
        paper_text, key_text = split_key(full_text) if want_key else (full_text, None)

        # Build PDF
        pdf_bytes = create_pdf(paper_text, key_text, data)

        # Encode PDF as latin-1 string for JSON transport
        pdf_encoded = pdf_bytes.decode("latin-1")

        return jsonify({
            "success": True,
            "paper":   full_text,
            "pdf":     pdf_encoded
        })

    except Exception as e:
        app.logger.error("generate error", exc_info=e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/download", methods=["POST"])
def download():
    try:
        body      = request.get_json(force=True) or {}
        pdf_str   = body.get("pdf", "")
        if not pdf_str:
            return jsonify({"error": "No PDF data"}), 400

        pdf_bytes = pdf_str.encode("latin-1")

        response = make_response(pdf_bytes)
        response.headers["Content-Type"]        = "application/pdf"
        response.headers["Content-Disposition"] = 'attachment; filename="ExamCraft_QuestionPaper.pdf"'
        response.headers["Content-Length"]      = str(len(pdf_bytes))
        return response

    except Exception as e:
        app.logger.error("download error", exc_info=e)
        return jsonify({"error": str(e)}), 500


# ── Health check ──
@app.route("/health")
def health():
    return jsonify({"status": "ok", "openai_configured": bool(api_key)})


# ── Local dev runner ──
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, port=port)
