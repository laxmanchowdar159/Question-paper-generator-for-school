// ExamCraft - AI Question Paper Generator
// Client-side logic for form handling, API communication, and UI management

let pdfData = null;

// element refs
const messageEl = document.getElementById("message");
const outputEl = document.getElementById("output");
const keyEl = document.getElementById("keyOutput");
const keySection = document.getElementById("keySection");
const generateBtn = document.getElementById("generateBtn");
const copyBtn = document.getElementById("copyBtn");
const themeToggle = document.getElementById("themeToggle");
const modal = document.getElementById("loadingModal");
const errorBox = document.getElementById("errorMessage");

// chapters list used for dynamic selector
const chaptersBySubject = {
    "Mathematics": ["Real Numbers","Polynomials","Linear Equations","Quadratic Equations"],
    "Science": ["Chemical Reactions","Acids & Bases","Metals & Non-metals"],
    "English": ["A Letter to God","Nelson Mandela","Two Stories about Flying"],
    "Social Studies": ["Nationalism in India","The Making of a Global World"]
};

// persistence
const storageKeys = [
    'user_name','school_name','standard','board','subject','chapter','marks','instructions','include_key'
];
function saveForm() {
    storageKeys.forEach(k => {
        const el = document.getElementById(k);
        if (!el) return;
        const val = el.type === 'checkbox' ? el.checked : el.value;
        localStorage.setItem(k, val);
    });
    // save difficulty radio separately
    const diff = document.querySelector('input[name="difficulty"]:checked');
    if (diff) localStorage.setItem('difficulty', diff.value);
}
function loadForm() {
    storageKeys.forEach(k => {
        const el = document.getElementById(k);
        if (!el) return;
        const val = localStorage.getItem(k);
        if (val === null) return;
        if (el.type === 'checkbox') el.checked = (val === 'true');
        else el.value = val;
    });
    const savedDiff = localStorage.getItem('difficulty');
    if (savedDiff) {
        const radio = document.querySelector(`input[name="difficulty"][value="${savedDiff}"]`);
        if (radio) radio.checked = true;
    }
}

function toggleTheme() {
    document.body.classList.toggle('dark');
    const icon = document.body.classList.contains('dark') ? '☀️' : '🌙';
    themeToggle.textContent = icon;
    localStorage.setItem('theme', icon);
}

function setButtonsState(disabled) {
    copyBtn.disabled = disabled;
    if (disabled) {
        copyBtn.classList.add("disabled");
    } else {
        copyBtn.classList.remove("disabled");
    }
}

function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.classList.remove("error", "success", "show");
    if (text) {
        if (type) messageEl.classList.add(type);
        messageEl.classList.add("show");
    }
}

function prepareSubjectChapters() {
    const subj = document.getElementById('subject');
    const chap = document.getElementById('chapter');
    subj.addEventListener('change', () => {
        const list = chaptersBySubject[subj.value] || [];
        chap.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
        list.forEach(c => {
            const opt = document.createElement('option');
            opt.value = c;
            opt.textContent = c;
            chap.appendChild(opt);
        });
        chap.disabled = list.length === 0;
    });
}

async function generatePaper() {
    errorBox.style.display = 'none';
    showMessage('', '');
    setButtonsState(true);

    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="emoji">🚀</span> Generating...<span class="spinner"></span>';
    modal.classList.add('show');

    try {
        const formData = new FormData();
        ['user_name','school_name','standard','board','subject','chapter','marks','instructions','include_key']
            .forEach(id => {
                const el = document.getElementById(id);
                if (!el) return;
                if (el.type === 'checkbox') formData.append(id, el.checked);
                else formData.append(id, el.value);
            });
        // add difficulty radio
        const diff = document.querySelector('input[name="difficulty"]:checked');
        if (diff) formData.append('difficulty', diff.value);

        const json = {};
        formData.forEach((v,k)=>{ json[k]=v; });
        // rename standard -> class for backend compatibility
        if (json.standard !== undefined) {
            json.class = json.standard;
            delete json.standard;
        }

        const res = await fetch('/generate', {
            method:'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(json)
        });
        const data = await res.json();
        if (!res.ok || !data.success) throw new Error(data.error||'Failed');

        let text = data.paper;
        let hasKey = false;
        if (json.include_key === 'true' || json.include_key === true) {
            const parts = text.split(/answer key[:]?/i);
            text = parts[0];
            const keyPortion = parts[1] ? parts[1].trim() : null;
            if (keyPortion) {
                keyEl.textContent = keyPortion;
                keySection.classList.remove('hidden');
                hasKey = true;
            } else {
                keySection.classList.add('hidden');
            }
        } else {
            keySection.classList.add('hidden');
        }

        outputEl.innerText = text;
        pdfData = data.pdf;
        showMessage('📝 Paper generated successfully!', 'success');
        setButtonsState(false);
        
        // Auto-download PDF after short delay
        setTimeout(() => {
            downloadPDF();
        }, 1000);
    } catch (err) {
        errorBox.style.display = 'block';
        showMessage(err.message, 'error');
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<span class="emoji">🚀</span> Generate Paper';
        modal.classList.remove('show');
    }
}

function downloadPDF() {
    if (!pdfData) return;
    fetch("/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf: pdfData })
    })
        .then(res => res.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "question_paper.pdf";
            a.click();
        });
}

function copyPaper() {
    if (!outputEl.innerText) return;
    navigator.clipboard.writeText(outputEl.innerText);
    showMessage("Copied to clipboard!", "success");
}

// initialization
loadForm();
if (localStorage.getItem('theme') === '☀️') document.body.classList.add('dark');
if (themeToggle) themeToggle.addEventListener('click', () => { toggleTheme(); });
document.querySelectorAll('select,input,textarea').forEach(el => { el.addEventListener('change', saveForm); });
prepareSubjectChapters();

// Guide toggle
const toggleGuideBtn = document.getElementById('toggleGuide');
const guideContent = document.getElementById('guideContent');
if (toggleGuideBtn) {
    toggleGuideBtn.addEventListener('click', () => {
        guideContent.classList.toggle('hidden');
        toggleGuideBtn.textContent = guideContent.classList.contains('hidden') ? 'Show Tips ▼' : 'Hide Tips ▲';
    });
}

