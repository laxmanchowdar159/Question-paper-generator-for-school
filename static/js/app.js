
// Lightweight frontend controller for the multi-step UI
document.addEventListener('DOMContentLoaded', () => {
    initUI();
});

function initUI() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const step = el.dataset.step;
            goToStep(step);
        });
    });

    document.getElementById('themeToggle').addEventListener('click', toggleTheme);

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', (e) => {
        const target = e.target.textContent.includes('Answer') ? 'answerKey' : 'paper';
        switchTab(target);
    }));

    // simple defaults
    if (!localStorage.getItem('theme')) localStorage.setItem('theme', 'light');
    applyTheme();
}

function goToStep(step) {
    document.querySelectorAll('.step-section').forEach(s => s.classList.remove('active'));
    const map = {
        identity: 'identity-step',
        curriculum: 'curriculum-step',
        'paper-config': 'paper-config-step',
        output: 'output-step'
    };
    const id = map[step];
    if (id) document.getElementById(id).classList.add('active');
}

function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    if (name === 'paper') {
        document.querySelector('.tab-btn').classList.add('active');
        document.getElementById('paper-tab').classList.add('active');
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('answerKey-tab').classList.add('active');
    }
}

function toggleTheme() {
    const current = localStorage.getItem('theme') || 'light';
    localStorage.setItem('theme', current === 'light' ? 'dark' : 'light');
    applyTheme();
}

function applyTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
}

// chapters list modeled after Perplexity project (trimmed)
const chaptersBySubject = {
    "Mathematics": [
        "Real Numbers", "Polynomials", "Pair of Linear Equations in Two Variables", "Quadratic Equations",
        "Arithmetic Progressions", "Triangles", "Coordinate Geometry", "Introduction to Trigonometry"
    ],
    "Science": [
        "Chemical Reactions and Equations", "Acids, Bases, and Salts", "Metals and Non-Metals", "Light – Reflection and Refraction",
        "Electricity", "Magnetic Effects of Electric Current"
    ],
    "Social": [
        "Nationalism in India", "The Making of a Global World", "Resources and Development", "Water Resources"
    ],
    "English": [
        "A Letter to God", "Nelson Mandela: Long Walk to Freedom", "Glimpses of India", "Fog"
    ]
};

function updateChapters() {
    const subject = document.getElementById('subject').value;
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
    if (chaptersBySubject[subject]) {
        chaptersBySubject[subject].forEach(chap => {
            const option = document.createElement('option');
            option.value = chap;
            option.textContent = chap;
            chapterSelect.appendChild(option);
        });
        chapterSelect.disabled = false;
    } else {
        chapterSelect.disabled = true;
    }
}

// Wire subject -> chapter updates and form submission
document.addEventListener('DOMContentLoaded', () => {
    const subjectSelect = document.getElementById('subject');
    if (subjectSelect) subjectSelect.addEventListener('change', updateChapters);

    const form = document.getElementById('paperForm');
    const button = document.getElementById('generateBtn');
    const modal = document.getElementById('loadingModal');
    const errorBox = document.getElementById('errorMessage');

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorBox.style.display = 'none';
            if (modal) { modal.setAttribute('aria-hidden', 'false'); modal.style.display = 'flex'; }
            if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }

            try {
                const formData = new FormData(form);
                // send to /generate — server may return PDF or JSON
                const response = await fetch('/generate', { method: 'POST', body: formData });

                const contentType = response.headers.get('Content-Type') || '';
                if (contentType.includes('application/pdf')) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    const disposition = response.headers.get('Content-Disposition') || '';
                    let filename = 'model_paper.pdf';
                    const m = disposition.match(/filename *= *"?([^";]+)"?/);
                    if (m) filename = m[1].replace(/['"]/g, '');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                } else {
                    // fallback to JSON/text response
                    const text = await response.text();
                    // try parse JSON
                    try {
                        const json = JSON.parse(text);
                        if (json.success && json.paper) {
                            // show paper in a simple modal or toast
                            showToast('Paper generated — check the preview section');
                            console.log(json.paper);
                        } else {
                            throw new Error(json.error || 'Generation failed');
                        }
                    } catch (err) {
                        errorBox.style.display = 'block';
                    }
                }
            } catch (err) {
                errorBox.style.display = 'block';
            } finally {
                if (modal) { modal.setAttribute('aria-hidden', 'true'); modal.style.display = 'none'; }
                if (button) { button.disabled = false; button.setAttribute('aria-busy', 'false'); }
            }
        });
    }
});

async function generatePaper() {
    const payload = {
        class: document.getElementById('class').value,
        subject: document.getElementById('subject').value,
        board: document.getElementById('board').value || document.getElementById('board')?.value,
        marks: document.getElementById('totalMarks').value,
        difficulty: document.getElementById('difficulty').value
    };

    document.getElementById('loadingSpinner').classList.remove('hidden');

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        document.getElementById('loadingSpinner').classList.add('hidden');
        if (!result.success) return showToast(result.error || 'Generation failed');

        const paperText = result.paper || '';
        // try split answer key if present
        const splitIndex = paperText.toLowerCase().indexOf('answer key');
        if (splitIndex !== -1) {
            document.getElementById('paperOutput').textContent = paperText.slice(0, splitIndex);
            document.getElementById('answerKeyOutput').textContent = paperText.slice(splitIndex);
        } else {
            document.getElementById('paperOutput').textContent = paperText;
            document.getElementById('answerKeyOutput').textContent = '';
        }

        goToStep('output');
    } catch (err) {
        document.getElementById('loadingSpinner').classList.add('hidden');
        showToast(err.message || 'Network error');
    }
}

function showToast(msg) {
    const t = document.getElementById('notificationToast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 4000);
}

function copyToClipboard() {
    const text = document.getElementById('paperOutput').textContent;
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard'));
}

function downloadPDF() {
    // For now just download plain text as .txt — PDF generation handled server-side.
    const text = document.getElementById('paperOutput').textContent || '';
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'question-paper.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}
