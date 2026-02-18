let pdfData = null;

// UI element references
const messageEl = document.getElementById("message");
const outputEl = document.getElementById("output");
const generateBtn = document.getElementById("generateBtn");
const downloadBtn = document.getElementById("downloadBtn");
const copyBtn = document.getElementById("copyBtn");
const themeToggle = document.getElementById("themeToggle");

// save/load form fields between sessions
const storageKeys = [
    'user_name','school_name','standard','board','subject','difficulty','marks','instructions','include_key'
];
function saveForm() {
    storageKeys.forEach(k => {
        const el = document.getElementById(k);
        if (!el) return;
        const val = el.type === 'checkbox' ? el.checked : el.value;
        localStorage.setItem(k, val);
    });
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
}

function toggleTheme() {
    document.body.classList.toggle('dark');
    const icon = document.body.classList.contains('dark') ? '☀️' : '🌙';
    themeToggle.textContent = icon;
    localStorage.setItem('theme', icon);
}

// initialize
loadForm();
if (localStorage.getItem('theme') === '☀️') document.body.classList.add('dark');
if (themeToggle) themeToggle.addEventListener('click', () => { toggleTheme(); });

document.querySelectorAll('select,input,textarea').forEach(el => {
    el.addEventListener('change', saveForm);
});

async function generatePaper() {
    // clear previous state
    messageEl.textContent = "";
    outputEl.textContent = "";
    pdfData = null;
    setButtonsState(true);

    generateBtn.disabled = true;
    generateBtn.innerHTML = "Generating... <span class=\"spinner\"></span>";

    try {
        const res = await fetch("/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                user_name: document.getElementById('user_name').value,
                school_name: document.getElementById('school_name').value,
                class: standard.value,
                board: board.value,
                subject: subject.value,
                difficulty: difficulty.value,
                marks: marks.value,
                instructions: instructions.value,
                include_key: document.getElementById('include_key').checked
            })
        });

        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.error || "Failed to generate paper");
        }

        // if key was requested, split so the preview only shows the paper
        let text = data.paper;
        const wantKey = document.getElementById('include_key').checked;
        let keyPortion = null;
        if (wantKey) {
            const parts = text.split(/answer key[:]?/i);
            text = parts[0];
            keyPortion = parts[1] ? parts[1].trim() : null;
            const keyEl = document.getElementById('keyOutput');
            if (keyEl) {
                if (keyPortion) {
                    keyEl.textContent = keyPortion;
                    keyEl.classList.remove('hidden');
                } else {
                    keyEl.textContent = '';
                    keyEl.classList.add('hidden');
                }
            }
        } else {
            const keyEl = document.getElementById('keyOutput');
            if (keyEl) keyEl.classList.add('hidden');
        }
        outputEl.innerText = text;
        pdfData = data.pdf;
        showMessage("📝 Paper generated successfully!", "success");
        setButtonsState(false);
    } catch (err) {
        showMessage(err.message, "error");
    } finally {
        generateBtn.disabled = false;
        generateBtn.innerText = "Generate Paper";
    }
}

function setButtonsState(disabled) {
    downloadBtn.disabled = disabled;
    copyBtn.disabled = disabled;
    if (disabled) {
        downloadBtn.classList.add("disabled");
        copyBtn.classList.add("disabled");
    } else {
        downloadBtn.classList.remove("disabled");
        copyBtn.classList.remove("disabled");
    }
}

function showMessage(text, type) {
    messageEl.textContent = text;
    messageEl.classList.remove("error", "success");
    if (type) {
        messageEl.classList.add(type);
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
