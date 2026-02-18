import os
from flask import Flask, request, jsonify, render_template
from openai import OpenAI

app = Flask(__name__, template_folder="../templates", static_folder="../static")

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/generate-paper", methods=["POST"])
def generate_paper():

    data = request.json

    subject = data.get("subject")
    class_level = data.get("class")
    board = data.get("board")
    marks = data.get("marks")

    prompt = f"""
Generate a {marks}-mark question paper for:

Class: {class_level}
Board: {board}
Subject: {subject}

Include:

Section A: MCQs  
Section B: Short Answer  
Section C: Long Answer  

Follow {board} exam pattern.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert school exam paper generator."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    paper = response.choices[0].message.content

    return jsonify({"paper": paper})


app = app
