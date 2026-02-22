# 📝 ExamCraft - AI Question Paper Generator

**Craft Perfect Exam Papers with AI in Minutes**

ExamCraft is a sophisticated AI-powered application that generates high-quality, customizable exam question papers instantly. Built with Google Gemini AI and optimized for Indian boards (Andhra Board, CBSE, ICSE, State Board, and IB).

## ✨ Features at a Glance

### 🤖 **AI-Powered Intelligence**
- Google Gemini 1.5 Flash model generates contextual, high-quality questions
- Board-specific optimizations (Andhra Board, CBSE, ICSE, etc.)
- Curriculum-aligned with educational standards

### 📋 **Flexible Customization**
- Multiple boards, classes (6-10), subjects, and chapters
- 4 difficulty levels: Easy, Medium, Hard, Mixed
- Marks options: 20, 40, 60, 80, 100
- Custom instructions for special requirements
- Dynamic chapter selector based on subject

### 🔑 **Answer Key Generation**
- Automatic answer key extraction and separation
- Appears on separate PDF page for easy grading
- Optional toggle for paper generation

### 📄 **Professional Output**
- A4 PDF format with proper margins and typography
- School/teacher name in header
- Automatic page breaks and text wrapping
- Base64 encoding for instant download

### 🌙 **Premium User Experience**
- Dark mode with full color scheme support
- Theme persistence across sessions
- Form state auto-saves to localStorage
- Fully responsive (desktop, tablet, mobile)
- Interactive feature showcase and guide

### 💾 **Smart Form Management**
- Auto-saves all inputs as you type
- Restores previous session on reload
- Special handling for difficulty levels
- No external data collection

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Generative AI (Gemini) API key (free tier available)

### Setup in 5 Minutes

```bash
# 1. Clone
git clone <your-repo>
cd Question-paper-generator-for-school

# 2. Install
pip install -r requirements.txt

# 3. Configure API key
set GEMINI_API_KEY=your-gemini-api-key-here        # Windows
export GEMINI_API_KEY=your-gemini-api-key-here     # Mac/Linux

# 4. Run
pip install -r requirements.txt

# Development (Flask CLI):
export FLASK_APP=app
flask run --host=0.0.0.0 --port=3000

# Production-like (Gunicorn):
gunicorn api.app:app --bind 0.0.0.0:8000

# 5. Open browser
# Navigate to http://localhost:3000 (Flask) or http://localhost:8000 (Gunicorn)
```

### Deploy to Render

1. Push to GitHub
2. Create a new Web Service on Render and connect your repo
3. Set `GEMINI_API_KEY` in the Render service Environment > Environment Variables
4. Set the Start Command to `gunicorn app:app --bind 0.0.0.0:$PORT` (or use the provided `render.yaml`)
5. Deploy!

---

## 📖 How to Use (7 Steps)

1. **Enter Details** → Your name, school name
2. **Select Board** → Andhra Board (or your region)
3. **Choose Class & Subject** → 10th, Mathematics
4. **Pick Chapter** → Dynamically loads from subject
5. **Set Marks & Difficulty** → 100 marks, Medium
6. **Add Instructions** → "Focus on word problems"
7. **Generate** → Auto-downloads PDF in 5-10 seconds

---

## 🏗️ Code Architecture (Detailed)

### Backend: `app.py`

**Role**: Google Gemini API integration, PDF generation, API endpoints

#### Core Functions

**1. `generate_question_paper(data: Dict) -> str`**
```python
"""Calls Google Gemini API to generate question paper"""
# Assembles prompt from form inputs
# Adds board-specific instructions  
# Returns generated paper text
```

**2. `create_pdf(text: str, data: Dict, key: str) -> str`**
```python
"""Generates professional A4 PDF"""
# Creates FPDF, sets margins
# Adds school name header
# Embeds question paper
# Inserts answer key on page 2
# Returns base64-encoded PDF
```

**3. `split_key(text: str) -> Tuple[str, str]`**
```python
"""Extracts answer key from paper text"""
# Regex split on "ANSWER KEY:"
# Returns (paper, key) tuple
```

#### Routes
- `GET /` → Serves HTML
- `POST /generate` → Returns paper + PDF
- `POST /download` → Delivers PDF file

#### Environment
- `GEMINI_API_KEY` (required) → Your Google Generative AI API key

### Frontend: `templates/index.html`

**Structure**: Header → Features → Guide → Form → Output

#### Key Sections
1. Header (Logo, title, theme toggle)
2. Feature Showcase (4 cards with icons)
3. How-to Guide (Collapsible 7-step walkthrough)
4. Form Grid (8 input cards + options)
5. Output Preview (Question paper + answer key)
6. Footer (Support info)

### Styling: `static/css/style.css`

**CSS Variables** (auto light/dark switching):
```css
--primary: #3b82f6
--bg-light: #f4f6f8
--text-dark: #1e293b
```

**Components**: Grid layout, cards, feature cards, guide steps, styled buttons

**Responsive**: 2-column desktop → 1 column mobile (768px breakpoint)

**Animations**: Slide-in entrance, spinner rotation, smooth transitions

### JavaScript: `static/js/app.js`

**Main Functions**:
1. `generatePaper()` - API call + PDF generation
2. `downloadPDF()` - Trigger file download
3. `saveForm() / loadForm()` - LocalStorage persistence
4. `toggleTheme()` - Dark mode toggle
5. `prepareSubjectChapters()` - Dynamic chapter loading

**Data Management**:
- `chaptersBySubject` - Chapter lists per subject
- `localStorage` - Form state persistence
- `pdfData` - Base64 PDF storage

---

## 🔌 Google Gemini Integration Details

### Model: `gemini-1.5-flash`
- **Speed**: 5-10 seconds per paper
- **Cost**: Free tier available, very economical at scale
- **Quality**: Excellent educational content

### Prompt Engineering
- Role: Expert exam setter
- Context: Class, subject, chapter
- Structure: MCQ + Short Answer + Long Answer
- Constraints: Difficulty, marks, format

### Error Handling
- Missing key → Startup failure
- Invalid key → 401 error
- Rate limit → 429 retry
- Network → User feedback

---

## 🎨 UI/UX Highlights

### Design System
- **Colors**: Blue primary, green accents
- **Typography**: Poppins font
- **Spacing**: Consistent rem units
- **Shadows**: Subtle elevation
- **Animations**: Smooth transitions

### Interactive Elements
- Card hover effects (lift, shadow)
- Input focus states (blue outline)
- Loading spinner (rotating animation)
- Success messages (green with emoji)
- Collapsible guide (toggle expand/collapse)

### Accessibility
- Semantic HTML
- ARIA labels
- Focus management
- Color contrast (WCAG AA)
- Touch-friendly (44px minimum)

---

## 🔧 Customization Guide

**Add Subject**:
1. Update HTML select options
2. Add to `chaptersBySubject` in JavaScript

**Add Board**:
1. Update board dropdown
2. Add prompt logic in Python backend

**Change Colors**:
Edit CSS variables in `:root`

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| Page Load | <1 second |
| Generation | 5-15 seconds |
| PDF Size | 50-150 KB |
| Storage | ~5 KB |
| Cost/Paper | $0.01-0.015 |

---

## 🔐 Security & Privacy

✅ No server-side storage
✅ Direct OpenAI integration
✅ Client-side state only
✅ HTTPS/TLS encryption
✅ No data logging

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| API key error | Set `GEMINI_API_KEY` environment variable |
| Static 404 | Check `render.yaml` routing or static folder configuration |
| No auto-download | Disable popup blocker |
| Form lost | Enable localStorage |
| Generation fails | Verify API key + connection |

---

## 📱 Browser Support

Chrome 90+ | Firefox 88+ | Safari 14+ | Edge 90+ | Mobile browsers ✅

---

## 🚀 Future Features

- User accounts with history
- Batch generation
- Paper templates
- Multi-language support
- Teacher dashboard
- LMS integration
- Mobile app

---

**ExamCraft** - Made with ❤️ for educators worldwide | February 2026

---

## 📌 About This Project

**ExamCraft** (formerly Question Paper Generator) empowers educators to create professional, AI-generated exam papers in minutes instead of hours. Perfect for schools, coaching centers, and individual tutors.

**Project Repository**: https://github.com/laxmanchowdar159/ExamCraft

**Live Demo**: Deploy to Render for instant access
