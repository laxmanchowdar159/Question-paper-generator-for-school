
import os
import re
from flask import Flask, render_template, request, jsonify, make_response
from openai import OpenAI
from fpdf import FPDF

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
    static_url_path="/static"
)

# OpenAI client
api_key = os.environ.get("OPENAI_API_KEY")
client = None
if api_key:
    client = OpenAI(api_key=api_key)

def split_key(text):
    parts = re.split(r"(?i)answer key[:]?\s*", text, maxsplit=1)
    if len(parts) > 1:
        return parts[0], parts[1]
    return text, None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    try:
        if not client:
            return jsonify({"success": False, "error": "API key not configured. Please set OPENAI_API_KEY environment variable."}), 500
        
        data = request.json
        
                # Accept either JSON (AJAX) or form POST (multipart/form-data) from the UI
                if request.form:
                    form = request.form
                    cls = form.get('class') or form.get('grade') or ''
                    subject = form.get('subject') or ''
                    chapter = form.get('chapter') or ''
                    difficulty = form.get('difficulty') or 'Medium'
                    suggestions = form.get('suggestions') or ''
                    # build prompt
                    prompt = f"""
        Create a professional question paper.

        Class: {cls}
        Subject: {subject}
        Chapter: {chapter}
        Difficulty: {difficulty}

        Structure into Sections A, B, C, D with appropriate marks and provide an answer key at the end.
        Extra instructions: {suggestions}
        """
                else:
                    data = request.get_json(force=True, silent=True) or {}
                    cls = data.get('class') or ''
                    subject = data.get('subject') or ''
                    chapter = data.get('chapter') or ''
                    difficulty = data.get('difficulty') or 'Medium'
                    suggestions = data.get('suggestions') or ''
                    prompt = f"""
        Create a professional question paper.

        Class: {cls}
        Subject: {subject}
        Chapter: {chapter}
        Difficulty: {difficulty}

        Structure into Sections A, B, C, D with appropriate marks and provide an answer key at the end.
        Extra instructions: {suggestions}
        """
Generate a professional question paper.

Class: {data.get("class")}
Subject: {data.get("subject")}
Board: {data.get("board")}
Marks: {data.get("marks")}
Difficulty: {data.get("difficulty")}

Format with Sections A, B, C, D.
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
                # If the request was a form POST, return a PDF for immediate download
                if request.form:
                    pdf_bytes = create_exam_pdf(text, subject or 'Paper', chapter or '')
                    resp = make_response(pdf_bytes)
                    resp.headers.set('Content-Type', 'application/pdf')
                    filename = f"{subject or 'paper'}_{chapter or 'full'}.pdf"
                    resp.headers.set('Content-Disposition', 'attachment', filename=filename)
                    return resp

            messages=[
                {"role": "system", "content": "You are a professional exam paper generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )

        text = response.choices[0].message.content
        def create_exam_pdf(text: str, subject: str, chapter: str) -> bytes:
            """Create a simple A4 PDF from the generated text. Falls back to Helvetica if DejaVu not available."""
            pdf = FPDF()
            pdf.add_page()

            # Try to load DejaVu Unicode font if present
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            font_path = os.path.join(base_dir, 'static', 'fonts', 'DejaVuSans.ttf')
            try:
                if os.path.isfile(font_path):
                    pdf.add_font('DejaVu', '', font_path, uni=True)
                    pdf.add_font('DejaVu', 'B', font_path, uni=True)
                    font_name = 'DejaVu'
                else:
                    font_name = 'Helvetica'
            except Exception:
                font_name = 'Helvetica'

            # Header
            pdf.set_font(font_name, 'B' if font_name != 'Helvetica' else '', 16)
            header = f"Class {subject} - {chapter}" if chapter else f"{subject}"
            pdf.cell(0, 10, header, ln=1, align='C')
            pdf.ln(4)

            # Body
            pdf.set_font(font_name, size=12)
            lines = text.split('\n')
            for line in lines:
                line = line.rstrip()
                if not line:
                    pdf.ln(4)
                    continue
                # Avoid extremely long unbroken lines
                pdf.multi_cell(0, 7, line)

            out = pdf.output(dest='S')
            # fpdf2 may return bytes or string depending on version
            if isinstance(out, str):
                return out.encode('latin-1', 'replace')
            return out
        paper, key = split_key(text)

        return jsonify({
            "success": True,
            "paper": text
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(port=3000)