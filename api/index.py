
import os
import re
from flask import Flask, render_template, request, jsonify, make_response
from openai import OpenAI

app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
    static_url_path="/static"
)

# OpenAI client
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    raise Exception("OPENAI_API_KEY not set")

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
        data = request.json
        
        prompt = f"""
Generate a professional question paper.

Class: {data.get("class")}
Subject: {data.get("subject")}
Board: {data.get("board")}
Marks: {data.get("marks")}
Difficulty: {data.get("difficulty")}

Format with Sections A, B, C, D.
"""

        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a professional exam paper generator."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=3000
        )

        text = response.choices[0].message.content
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