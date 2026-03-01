# 📝 ExamCraft — AI Question Paper Generator

> Generate professional, curriculum-aligned exam papers in seconds using Google Gemini AI.

---

## What It Does

ExamCraft is a Flask web app for school teachers that generates printable question papers as PDFs. You pick the board, class, subject, chapter, difficulty, and marks — the AI does the rest. If no API key is available, a local fallback generator kicks in automatically.

---

## Features

- **AI-generated questions** via Google Gemini (auto-selects best available model: Gemini 2.0 Flash → 1.5 Flash → Pro)
- **Supports Indian boards**: CBSE, ICSE, Andhra Board, State Board, IB
- **Classes 6–10**, multiple subjects and chapters per subject
- **Difficulty levels**: Easy, Medium, Hard, Mixed
- **Marks options**: 20, 40, 60, 80, 100
- **Answer key** generated on a separate PDF page
- **Professional A4 PDF** output with school/teacher name in the header
- **Fallback mode**: Works without an API key using a built-in local generator

---

## Project Structure

```
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── Procfile                # For deployment (Gunicorn)
├── render.yaml             # Render.com deployment config
├── data/
│   ├── boards.json         # Board definitions
│   └── curriculum.json     # Subjects and chapters per board/class
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── fonts/DejaVuSans.ttf  # Font used in PDF generation
└── templates/
    ├── index.html
    └── solutions.html
```

---

## Getting Started

### 1. Clone the repo

```bash
git clone https://github.com/your-username/question-paper-generator.git
cd question-paper-generator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set your Gemini API key (optional but recommended)

```bash
export GEMINI_API_KEY=your_api_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com). Without a key, the app uses the built-in fallback generator.

### 4. Run the app

```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

---

## Deployment

The app is ready to deploy on [Render](https://render.com) using the included `render.yaml` and `Procfile`.

1. Push to GitHub
2. Connect your repo on Render
3. Add `GEMINI_API_KEY` as an environment variable
4. Deploy

---

## Requirements

- Python 3.9+
- See `requirements.txt` for all packages (Flask, fpdf2, google-generativeai, etc.)

---

## License

MIT — free to use, modify, and distribute.