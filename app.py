import os
from flask import Flask, render_template, request, jsonify, make_response
from openai import OpenAI
from fpdf import FPDF
from fpdf.enums import XPos, YPos

app = Flask(__name__)

# OpenAI client
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# ---------------------------
# Generate Question Paper
# ---------------------------

def generate_question_paper(data):

    prompt = f"""
You are a senior {data['board']} exam paper setter.

Create a professional question paper.

Class: {data['class']}
Board: {data['board']}
Subject: {data['subject']}
Difficulty: {data['difficulty']}
Marks: {data['marks']}

Instructions:
{data['instructions']}

Requirements:

• Professional exam format
• No answers
• No explanations
• Clear sections

Sections:

Section A — MCQ  
Section B — Short Answer  
Section C — Long Answer  
Section D — Case Study  

Total marks must equal {data['marks']}
"""

    response = client.chat.completions.create(

        model="gpt-4o-mini",

        messages=[
            {
                "role": "system",
                "content": "You generate high-quality school exam papers."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.7
    )

    return response.choices[0].message.content


# ---------------------------
# Create PDF
# ---------------------------

def create_pdf(text, data):

    pdf = FPDF()
    pdf.add_page()

    font_path = os.path.join("static", "fonts", "DejaVuSans.ttf")

    pdf.add_font("DejaVu", "", font_path)
    pdf.add_font("DejaVu", "B", font_path)

    pdf.set_font("DejaVu", "B", 16)

    pdf.cell(0, 10,
             f"{data['board']} Examination",
             new_x=XPos.LMARGIN,
             new_y=YPos.NEXT,
             align="C")

    pdf.set_font("DejaVu", "", 12)

    pdf.cell(0, 8, f"Class: {data['class']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Subject: {data['subject']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, f"Marks: {data['marks']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(10)

    pdf.multi_cell(0, 7, text)

    return bytes(pdf.output(dest="S"))


# ---------------------------
# Routes
# ---------------------------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():

    data = request.json

    paper = generate_question_paper(data)

    pdf_bytes = create_pdf(paper, data)

    return jsonify({
        "paper": paper,
        "pdf": pdf_bytes.decode("latin-1")
    })


@app.route("/download", methods=["POST"])
def download():

    pdf = request.json["pdf"].encode("latin-1")

    response = make_response(pdf)

    response.headers.set("Content-Type", "application/pdf")
    response.headers.set(
        "Content-Disposition",
        "attachment",
        filename="question_paper.pdf"
    )

    return response


# Production entry
if __name__ == "__main__":
    app.run(debug=True)
