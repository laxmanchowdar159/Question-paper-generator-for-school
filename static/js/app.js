
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

// Curriculum mapping by class -> subject -> chapters (AP board trimmed examples)
// AP Board curriculum mapping (Classes 6-10) - trimmed to common chapters
const curriculum = {
    "10": {
        "Mathematics": [
            "Real Numbers",
            "Polynomials",
            "Pair of Linear Equations in Two Variables",
            "Quadratic Equations",
            "Arithmetic Progressions",
            "Triangles",
            "Coordinate Geometry",
            "Trigonometry"
        ],
        "Science": [
            "Chemical Reactions and Equations",
            "Acids, Bases and Salts",
            "Metals and Non-metals",
            "Carbon and its Compounds",
            "Periodic Classification of Elements",
            "Light – Reflection and Refraction",
            "Human Eye and Colourful World",
            "Electricity"
        ],
        "Social": [
            "Nationalism in India",
            "The Making of a Global World",
            "Resources and Development",
            "Water Resources",
            "Forest and Wildlife Resources"
        ],
        "English": [
            "First Flight - Chapters",
            "Footprints Without Feet - Stories",
            "Supplementary Reading"
        ]
    },
    "9": {
        "Mathematics": [
            "Number Systems",
            "Polynomials",
            "Coordinate Geometry",
            "Linear Equations",
            "Triangles"
        ],
        "Science": [
            "Matter - Its Nature and Behaviour",
            "Atoms and Molecules",
            "Structure of the Atom",
            "Motion",
            "Force and Laws of Motion",
            "Gravitation"
        ],
        "Social": [
            "The French Revolution",
            "Social Changes",
            "The Making of the Constitution"
        ],
        "English": [
            "The Sound of Music",
            "The Bond of Love",
            "Notions of Prose and Poetry"
        ]
    },
    "8": {
        "Mathematics": [
            "Rational Numbers",
            "Linear Equations",
            "Understanding Quadrilaterals",
            "Data Handling"
        ],
        "Science": [
            "Crop Production and Management",
            "Microorganisms",
            "Synthetic Fibres and Plastics",
            "Conservation of Plants and Animals"
        ],
        "Social": [
            "Resources and Development",
            "Human Environment: Settlement, Transport and Communication"
        ],
        "English": [
            "The Happy Prince",
            "Gulliver's Travels",
            "A Face in the Dark"
        ]
    },
    "7": {
        "Mathematics": [
            "Integers",
            "Fractions and Decimals",
            "Algebraic Expressions",
            "Lines and Angles"
        ],
        "Science": [
            "Nutrition in Animals",
            "Acids, Bases and Salts",
            "Physical and Chemical Changes"
        ],
        "Social": [
            "Environment and Resources",
            "Weather, Climate and Adaptations of Animals"
        ],
        "English": [
            "Three Questions",
            "The Selfish Giant",
            "The Treasure Within"
        ]
    },
    "6": {
        "Mathematics": [
            "Knowing Our Numbers",
            "Whole Numbers",
            "Playing with Numbers",
            "Basic Geometrical Concepts"
        ],
        "Science": [
            "Food: Where Does It Come From?",
            "Components of Food",
            "Sorting Materials into Groups"
        ],
        "Social": [
            "What, Where, How and When?",
            "The Earth: Our Habitat",
            "Maps and Mapping"
        ],
        "English": [
            "The Fun They Had",
            "The Sound of Music (short stories)",
            "Poems and Short Tales"
        ]
    }
};

function updateSubjectsForClass() {
    const classSel = document.getElementById('class').value;
    const subjectSelect = document.getElementById('subject');
    subjectSelect.innerHTML = '<option value="" disabled selected>Select a subject</option>';
    const subjects = curriculum[classSel] ? Object.keys(curriculum[classSel]) : [];
    subjects.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.textContent = s;
        subjectSelect.appendChild(opt);
    });
    // reset chapter
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
    chapterSelect.disabled = true;
    // enable subject selector only when subjects are available
    subjectSelect.disabled = subjects.length === 0;
}

function updateChapters() {
    const classVal = document.getElementById('class').value;
    const subject = document.getElementById('subject').value;
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
    if (curriculum[classVal] && curriculum[classVal][subject]) {
        curriculum[classVal][subject].forEach(chap => {
            const option = document.createElement('option');
            option.value = chap;
            option.textContent = chap;
            chapterSelect.appendChild(option);
        });
        chapterSelect.disabled = false;
        // focus chapter for faster workflow
        chapterSelect.focus();
    } else {
        chapterSelect.disabled = true;
    }
}

// Wire subject -> chapter updates and form submission
document.addEventListener('DOMContentLoaded', () => {
    const subjectSelect = document.getElementById('subject');
    if (subjectSelect) subjectSelect.addEventListener('change', updateChapters);
    const classSelect = document.getElementById('class');
    if (classSelect) {
        // If no class selected, default to first available class so users immediately see subjects
        if (!classSelect.value) {
            const firstOpt = classSelect.querySelector('option:not([disabled])');
            if (firstOpt) classSelect.value = firstOpt.value;
        }

        classSelect.addEventListener('change', () => {
            updateSubjectsForClass();
            // after populating subjects, focus the subject select for quick selection
            setTimeout(() => document.getElementById('subject')?.focus(), 50);
        });
        // populate subjects for initial class
        updateSubjectsForClass();
    }

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

    // Preview button -> use JSON API to get paper text and show in preview pane
    const previewBtn = document.getElementById('previewBtn');
    if (previewBtn) previewBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        clearFieldErrors();
        const valid = validateForm();
        if (!valid) return showToast('Please fix highlighted fields first');
        // collect payload
        const payload = {
            class: document.getElementById('class').value,
            subject: document.getElementById('subject').value,
            chapter: document.getElementById('chapter').value,
            difficulty: Array.from(document.getElementsByName('difficulty')).find(r => r.checked)?.value || 'Medium',
            suggestions: document.getElementById('suggestions').value || ''
        };
        const previewPane = document.getElementById('previewPane');
        previewPane.textContent = 'Generating preview...';
        try {
            const res = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (!json.success) {
                previewPane.innerHTML = `<div class="error-inline">${escapeHtml(json.error || 'Generation failed')}</div>`;
                showToast('There was a hiccup generating the preview — see note above.');
                return;
            }
            const paperText = json.paper || '';
            // render formatted preview (basic)
            previewPane.innerHTML = `<pre class="preview-text">${escapeHtml(paperText)}</pre>`;
            showToast('Preview generated — looks good? 😄');
        } catch (err) {
            previewPane.innerHTML = `<div class="error-inline">${escapeHtml(err.message || 'Network error')}</div>`;
        }
    });
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
    // small friendly variations
    const variants = ['Nice!', 'All set!', 'Heads up!', 'Ta-da!'];
    const prefix = variants[Math.floor(Math.random() * variants.length)];
    t.textContent = `${prefix} — ${msg}`;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 4200);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// --- Validation helpers ---
function showFieldError(fieldId, msg) {
    const el = document.getElementById(fieldId + 'Error');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
}

function clearFieldErrors() {
    document.querySelectorAll('.error-inline').forEach(e => { e.textContent = ''; e.style.display = 'none'; });
}

function validateForm() {
    clearFieldErrors();
    let ok = true;
    const cls = document.getElementById('class').value;
    const subj = document.getElementById('subject').value;
    const chap = document.getElementById('chapter').value;
    if (!cls) { showFieldError('class', 'Please select a class'); ok = false; }
    if (!subj) { showFieldError('subject', 'Please select a subject'); ok = false; }
    if (!chap) { showFieldError('chapter', 'Please select a chapter'); ok = false; }
    return ok;
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
