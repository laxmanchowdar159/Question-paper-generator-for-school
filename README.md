# Question-paper-generator-for-school

A simple Flask/Vercel application that uses OpenAI to generate school exam question papers and output them as PDF. The interface has been redesigned with a premium look‑and‑feel: responsive card layout, Google Fonts, animated feedback, and improved usability.

## Features

- Clean, responsive “premium” form with labeled fields and modern styling
- Default board pre‑selected to **Andhra Board** (refreshable)
- Optional fields for teacher/user name and school name (shown on PDF)
- Checkbox to include an answer key; in-browser preview will show paper and optionally display the key in a separate box. The PDF gets the key on its own page.
- PDF output uses A4 size, proper margins, DejaVu fonts and can embed a logo placed at `static/images/logo.png`
- LocalStorage remembers your last choices across visits
- Light/dark theme toggle for comfort
- Live paper preview with copy‑to‑clipboard and PDF download
- Dynamic chapter selector that updates when you pick a subject
- Difficulty level radios styled as selectable pills
- Suggestions/instructions field with helpful hints
- Loading modal and error box for smoother UX, plus contact/support info in footer
- Static assets served correctly on Vercel

## Local development

1. Install requirements:
   ```sh
   pip install -r requirements.txt
   ```
2. Set your `OPENAI_API_KEY` environment variable:
   ```sh
   set OPENAI_API_KEY=your_key_here          # Windows PowerShell
   export OPENAI_API_KEY=your_key_here       # macOS/Linux
   ```
3. Start the server:
   ```sh
   python api/index.py
   ```
   or with Flask CLI:
   ```sh
   set FLASK_APP=api/index.py
   flask run
   ```
4. Visit `http://localhost:3000` in your browser.

## Deployment

The `vercel.json` configuration ensures static files are served directly and the catch-all route points to the Python function. Simply push to your GitHub repo and deploy on Vercel – remember to configure the OpenAI key.

*UI enhancements include premium styling inspired by a working reference project, theming, persistent form state, dynamic fields, and helpful tooltips. The interface now has a modal loading indicator, error alerts, and radio‑style difficulty buttons. PDF output uses A4 layout with margins, DejaVu fonts, optional logo, automatic page breaks, and inserts an answer key if requested. Prompt construction and backend logic have been streamlined for efficiency.*
