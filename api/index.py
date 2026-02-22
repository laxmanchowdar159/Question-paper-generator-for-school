
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
        import os
        import re
        from flask import Flask, render_template, request, jsonify, make_response
        from openai import OpenAI
        from fpdf import FPDF

        app = Flask(
            __name__,
            template_folder=os.path.join(os.path.dirname(__file__), '..', 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), '..', 'static'),
            static_url_path='/static'
        )

        # OpenAI client
        api_key = os.environ.get('OPENAI_API_KEY')
        client = OpenAI(api_key=api_key) if api_key else None


        def split_key(text: str):
            parts = re.split(r'(?i)answer key[:]?
        \s*', text, maxsplit=1)
            if len(parts) > 1:
                return parts[0].strip(), parts[1].strip()
            return text.strip(), None


        def create_exam_pdf(text: str, subject: str, chapter: str) -> bytes:
            pdf = FPDF()
            pdf.add_page()

            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            font_path = os.path.join(base_dir, 'static', 'fonts', 'DejaVuSans.ttf')
            font_name = 'Helvetica'
            try:
                if os.path.isfile(font_path):
                    pdf.add_font('DejaVu', '', font_path, uni=True)
                    pdf.add_font('DejaVu', 'B', font_path, uni=True)
                    font_name = 'DejaVu'
            except Exception:
                font_name = 'Helvetica'

            pdf.set_font(font_name, 'B' if font_name != 'Helvetica' else '', 16)
            header = f"{subject} - {chapter}" if chapter else f"{subject}"
            pdf.cell(0, 10, header, ln=1, align='C')
            pdf.ln(4)

            pdf.set_font(font_name, size=12)
            for line in text.splitlines():
                line = line.rstrip()
                if not line:
                    pdf.ln(4)
                    continue
                pdf.multi_cell(0, 7, line)

            out = pdf.output(dest='S')
            if isinstance(out, str):
                return out.encode('latin-1', 'replace')
            return out


        @app.route('/')
        def index():
            return render_template('index.html')


        @app.route('/generate', methods=['POST'])
        def generate():
            try:
                if not client:
                    return jsonify({"success": False, "error": "API key not configured. Please set OPENAI_API_KEY environment variable."}), 500

                is_form = bool(request.form)
                if is_form:
                    src = request.form
                else:
                    src = request.get_json(force=True, silent=True) or {}

                cls = src.get('class') or src.get('grade') or ''
                subject = src.get('subject') or ''
                chapter = src.get('chapter') or ''
                board = src.get('board') or ''
                marks = src.get('marks') or ''
                difficulty = src.get('difficulty') or 'Medium'
                suggestions = src.get('suggestions') or ''

                prompt = f"""
        Create a professional question paper.

        Class: {cls}
        Subject: {subject}
        Chapter: {chapter}
        Board: {board}
        Marks: {marks}
        Difficulty: {difficulty}

        Structure into Sections A, B, C, D with appropriate marks and provide an answer key at the end.
        Extra instructions: {suggestions}
        """

                response = client.chat.completions.create(
                    model='gpt-4o-mini',
                    messages=[
                        {"role": "system", "content": "You are a professional exam paper generator."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=3000
                )

                # Extract text safely
                text = ''
                try:
                    text = response.choices[0].message.content
                except Exception:
                    try:
                        text = response.choices[0].text
                    except Exception:
                        text = str(response)

                paper, key = split_key(text)

                if is_form:
                    pdf_bytes = create_exam_pdf(text, subject or 'Paper', chapter or '')
                    resp = make_response(pdf_bytes)
                    resp.headers.set('Content-Type', 'application/pdf')
                    filename = f"{(subject or 'paper').replace(' ', '_')}_{(chapter or 'full').replace(' ', '_')}.pdf"
                    resp.headers.set('Content-Disposition', 'attachment', filename=filename)
                    return resp

                return jsonify({
                    'success': True,
                    'paper': paper,
                    'answer_key': key
                })

            except Exception as e:
                return jsonify({'success': False, 'error': str(e)}), 500


        @app.route('/health')
        def health():
            return {'status': 'ok'}


        if __name__ == '__main__':
            app.run(port=3000)