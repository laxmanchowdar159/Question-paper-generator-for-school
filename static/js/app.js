// =====================================================
// ExamCraft Frontend Controller (Final Dynamic Version)
// =====================================================

// Global state
let curriculumData = {};
let currentPaper = "";
let currentAnswerKey = "";
let generationAbortController = null;

// Initialize when DOM ready


function setSidebarValue(id, value) {

    const el = document.getElementById(id);

    if (el) el.textContent = value;

}


// =====================================================
// SIDEBAR HELPERS
// =====================================================

function updateSidebar() {
    setSidebarValue('sb-class', document.getElementById('class').value || '—');
    setSidebarValue('sb-subject', document.getElementById('subject').value || '—');
    const scope = document.getElementById('scopeSelect')?.value;
    let chapterText = document.getElementById('chapter').value || '—';
    if (scope === 'all') chapterText = 'All Chapters';
    setSidebarValue('sb-chapter', chapterText);
    const scopeVal = document.getElementById('scopeSelect')?.value;
    setSidebarValue('sb-scope', scopeVal === 'all' ? 'Full syllabus' : scopeVal === 'single' ? 'Single chapter' : '—');
    setSidebarValue('sb-difficulty', getDifficulty());
    setSidebarValue('sb-marks', document.getElementById('totalMarks').value || '—');
    const examType = document.getElementById('examType').value;
    setSidebarValue('sb-type', examType ? examType.replace('-', ' ') : '—');
    let boardText = '—';
    if (examType === 'state-board') {
        boardText = document.getElementById('stateSelect').value || '—';
    } else if (examType === 'competitive') {
        boardText = document.getElementById('competitiveExam').value || '—';
    }
    setSidebarValue('sb-board', boardText);

    // answer key indicator
    const includeKey = document.getElementById('includeKey')?.checked;
    setSidebarValue('sb-key', includeKey ? 'Yes' : 'No');
}

// =====================================================
// LOAD CURRICULUM
// =====================================================

async function initCurriculum() {
    try {
        const res = await fetch("/chapters");
        const json = await res.json();
        if (json.success && json.data) {
            curriculumData = json.data;
        }
    } catch {
        console.warn("Using fallback curriculum");
    }

    // if a class was already selected (unlikely on fresh load) refresh subjects
    const cls = document.getElementById("class")?.value;
    if (cls) {
        await updateSubjects();
        updateFormVisibility();
        updateSidebar();
    }
}


// =====================================================
// UPDATE SUBJECTS
// =====================================================

async function updateSubjects() {

    const cls = document.getElementById("class").value;
    const subjectSelect = document.getElementById("subject");
    const chapterSelect = document.getElementById("chapter");

    // show loading indicator
    subjectSelect.innerHTML = '<option value="">Loading...</option>';
    chapterSelect.innerHTML = '<option value="">Select Chapter</option>';

    if (!cls) {
        subjectSelect.innerHTML = '<option value="">Select Subject</option>';
        return;
    }

    let subjects = null;

    try {
        const res = await fetch(`/chapters?class=${cls}`);
        const json = await res.json();
        if (json.success && json.data) {
            subjects = Object.keys(json.data);
            curriculumData[cls] = json.data;
        }
    } catch {}

    if (!subjects && curriculumData[cls]) {
        subjects = Object.keys(curriculumData[cls]);
    }

    subjectSelect.innerHTML = '<option value="">Select Subject</option>';
    chapterSelect.innerHTML = '<option value="">Select Chapter</option>';

    if (!subjects || subjects.length === 0) {
        // nothing available
        return;
    }

    subjects.forEach(subject => {
        const opt = document.createElement("option");
        opt.value = subject;
        opt.textContent = subject;
        subjectSelect.appendChild(opt);
    });
}



// =====================================================
// UPDATE CHAPTERS
// =====================================================

function updateChapters() {

    const cls =
        document.getElementById("class").value;

    const subject =
        document.getElementById("subject").value;

    const chapterSelect =
        document.getElementById("chapter");

    chapterSelect.innerHTML =
        '<option value="">Select Chapter</option>';

    if (!cls || !subject) return;

    const chapters =
        curriculumData[cls]?.[subject] || [];

    chapters.forEach(chapter => {

        const opt =
            document.createElement("option");

        opt.value = chapter;

        opt.textContent = chapter;

        chapterSelect.appendChild(opt);

    });

}


// =====================================================
// GET DIFFICULTY
// =====================================================

function getDifficulty() {
    // support radio group as well as legacy select
    const radio = document.querySelector('input[name="difficulty"]:checked');
    if (radio) return radio.value;
    const sel = document.querySelector('select[name="difficulty"]');
    return sel?.value || "Medium";
}


// =====================================================
// DYNAMIC FORM VISIBILITY
// =====================================================

function updateFormVisibility() {
    const examType = document.getElementById("examType").value;
    const stateCard = document.getElementById("stateCard");
    const competitiveCard = document.getElementById("competitiveCard");
    const scopeCard = document.getElementById("scopeCard");
    const classCard = document.getElementById("class")?.closest(".card");
    const subjectCard = document.getElementById("subject")?.closest(".card");
    const chapterCard = document.getElementById("chapter")?.closest(".card");
    const marksCard = document.getElementById("totalMarks")?.closest(".card");
    const difficultyCard = document.querySelector('select[name="difficulty"]')?.closest(".card");

    // always show class selection
    if (classCard) classCard.style.display = "block";

    // hide everything else by default and clear
    if (subjectCard) {
        subjectCard.style.display = "none";
        document.getElementById("subject").value = "";
    }
    if (chapterCard) {
        chapterCard.style.display = "none";
        document.getElementById("chapter").value = "";
    }
    if (marksCard) {
        marksCard.style.display = "none";
        document.getElementById("totalMarks").value = "100";
    }
    if (difficultyCard) {
        difficultyCard.style.display = "none";
        const diffInputs = document.querySelectorAll('input[name="difficulty"]');
        diffInputs.forEach(i => i.checked = false);
    }

    // toggle cards based on examType
    if (examType === "state-board") {
        if (stateCard) stateCard.style.display = "block";
        if (competitiveCard) competitiveCard.style.display = "none";
        if (scopeCard) scopeCard.style.display = "block"; // show scope selector for state as well

        // for state board we always ask for subject/marks, chapter may depend on scope
        if (subjectCard) subjectCard.style.display = "block";
        if (marksCard) marksCard.style.display = "block";
        if (difficultyCard) difficultyCard.style.display = "block";

        const scope = document.getElementById("scopeSelect")?.value;
        if (scope === "all") {
            if (chapterCard) {
                chapterCard.style.display = "none";
                const sel = document.getElementById("chapter");
                if (sel) sel.value = "";
            }
        } else {
            if (chapterCard) chapterCard.style.display = "block";
        }
    } else if (examType === "competitive") {
        if (stateCard) stateCard.style.display = "none";
        if (competitiveCard) competitiveCard.style.display = "block";
        if (scopeCard) scopeCard.style.display = "block";

        // always show difficulty for competitive papers
        if (difficultyCard) difficultyCard.style.display = "block";

        const scope = document.getElementById("scopeSelect")?.value;
        if (scope === "all") {
            // full competitive paper: only class and difficulty needed
            if (subjectCard) {
            subjectCard.style.display = "none";
            const sel = document.getElementById("subject");
            if (sel) sel.value = "";
        }
        if (chapterCard) {
            chapterCard.style.display = "none";
            const sel = document.getElementById("chapter");
            if (sel) sel.value = "";
        }
        if (marksCard) {
            marksCard.style.display = "none";
            const sel = document.getElementById("totalMarks");
            if (sel) sel.value = "100";
        }
        } else {
            // chapter-wise competitive paper: subject/chapter/marks required
            if (subjectCard) subjectCard.style.display = "block";
            if (chapterCard) chapterCard.style.display = "block";
            if (marksCard) marksCard.style.display = "block";
        }
    } else {
        // no exam type selected; hide the rest
        if (stateCard) stateCard.style.display = "none";
        if (competitiveCard) competitiveCard.style.display = "none";
        if (scopeCard) scopeCard.style.display = "none";
    }

    // global: if full syllabus is selected, hide subject and chapter selectors
    const globalScope = document.getElementById("scopeSelect")?.value;
    if (globalScope === "all") {
        if (subjectCard) {
            subjectCard.style.display = "none";
            const sel = document.getElementById("subject");
            if (sel) sel.value = "";
        }
        if (chapterCard) {
            chapterCard.style.display = "none";
            const sel2 = document.getElementById("chapter");
            if (sel2) sel2.value = "";
        }
    }

    // set required attributes based on visibility
    const adjustRequired = (card, selector) => {
        if (!card) return;
        const input = card.querySelector(selector);
        if (input) input.required = card.style.display !== "none";
    };

}

// =====================================================
// REQUEST GENERATION
// =====================================================

async function generatePaper() {
    // determine scope: single chapter or all chapters
    const scope = document.getElementById("scopeSelect")?.value || "single";

    // build payload
    const payload = {
        class: document.getElementById("class").value,
        subject: document.getElementById("subject").value,
        chapter: scope === "all" ? "" : document.getElementById("chapter").value,
        marks: document.getElementById("totalMarks")?.value || "100",
        difficulty: getDifficulty(),
        suggestions: document.getElementById("suggestions")?.value || "",
        includeKey: document.getElementById("includeKey")?.checked || false
    };

    // client validation
    const examType = document.getElementById("examType").value;
    if (!examType) { showToast("Please select paper type"); return; }
    if (examType === "state-board") {
        // when full syllabus (scope === 'all') is chosen, subject and chapter are not required
        if (scope === "single") {
            if (!payload.subject) { showToast("Select subject"); return; }
            if (!payload.chapter) { showToast("Select chapter"); return; }
        }
        payload.state = document.getElementById("stateSelect")?.value || "";
    }
    if (examType === "competitive") {
        const comp = document.getElementById("competitiveExam")?.value;
        if (comp) payload.competitiveExam = comp;
        if (scope === "single") {
            if (!payload.subject) { showToast("Select subject"); return; }
            if (!payload.chapter) { showToast("Select chapter"); return; }
        }
    }
    if (scope === "all") payload.all_chapters = true;
    payload.examType = examType;

    showLoading(true);

    try {
        const res = await fetch("/generate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const result = await res.json();
        showLoading(false);

        if (!result.success) {
            const msg = result.error || "Generation failed";
            showToast(msg);
            console.error("Generation error:", result.api_error || result.error);
            return;
        }

        currentPaper     = result.paper      || "";
        currentAnswerKey = result.answer_key  || "";

        // Render into output areas if they exist
        const outputEl = document.getElementById("paperOutput");
        if (outputEl) { outputEl.value = currentPaper; outputEl.style.display = "block"; }
        const keyEl = document.getElementById("answerKeyOutput");
        if (keyEl && currentAnswerKey) { keyEl.value = currentAnswerKey; }

        showToast("Paper generated successfully!");

    } catch (err) {
        showLoading(false);
        showToast("Server error: " + err.message);
        console.error("generatePaper error:", err);
    }
}


// =====================================================
// DOWNLOAD PDF
// =====================================================

async function downloadPDF() {

    if (!currentPaper || !currentPaper.trim()) {
        showToast("Generate a paper first before downloading");
        return;
    }

    const scope = document.getElementById("scopeSelect")?.value || "single";
    const subject = document.getElementById("subject").value || "Question Paper";
    const chapter = scope === "all" ? "" : (document.getElementById("chapter").value || "");
    const includeKey = document.getElementById("includeKey")?.checked || false;

    // Build payload — send the already-generated text directly.
    // This calls /download-pdf, NOT /generate, so no Gemini quota is used.
    const payload = {
        paper:       currentPaper,
        answer_key:  currentAnswerKey || "",
        subject:     subject,
        chapter:     chapter,
        includeKey:  includeKey
    };

    showLoading(true);

    try {
        const res = await fetch("/download-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            // Try to read error JSON
            let errMsg = `Server error ${res.status}`;
            try {
                const errJson = await res.json();
                errMsg = errJson.error || errMsg;
            } catch (_) {}
            showToast("PDF error: " + errMsg);
            showLoading(false);
            return;
        }

        const blob = await res.blob();

        if (blob.size === 0) {
            showToast("PDF was empty — try generating again");
            showLoading(false);
            return;
        }

        // Trigger browser download
        const url = URL.createObjectURL(blob);
        const a   = document.createElement("a");
        const safeName = (subject + "_" + (chapter || "Paper")).replace(/\s+/g, "_").replace(/[\/\\]/g, "-");
        a.href     = url;
        a.download = safeName + "_Question_Paper.pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);

        showLoading(false);
        showToast("PDF downloaded successfully");

    } catch (err) {
        showLoading(false);
        showToast("Download failed: " + err.message);
        console.error("downloadPDF error:", err);
    }
}


// =====================================================
// COPY PAPER
// =====================================================

function copyPaper() {

    if (!currentPaper) {

        showToast("Nothing to copy");

        return;

    }

    navigator.clipboard.writeText(currentPaper);

    showToast("Copied");

}


// =====================================================
// LOADING
// =====================================================

function showLoading(show) {

    const modal =
        document.getElementById("loadingModal");

    if (!modal) return;

    modal.style.display =
        show ? "flex" : "none";

}


// =====================================================
// TOAST
// =====================================================

function showToast(msg) {

    const toast =
        document.getElementById("notificationToast");

    if (!toast) return;

    toast.textContent = msg;

    toast.classList.add("show");

    setTimeout(() => {

        toast.classList.remove("show");

    }, 3000);

}


// =====================================================
// THEME TOGGLE
// =====================================================

function toggleTheme() {

    const html = document.documentElement;
    const isDark = html.getAttribute("data-theme") === "dark";
    
    if (isDark) {
        html.removeAttribute("data-theme");
        localStorage.setItem("theme", "light");
    } else {
        html.setAttribute("data-theme", "dark");
        localStorage.setItem("theme", "dark");
    }

}

// =====================================================
// INITIALIZATION
// =====================================================

document.addEventListener("DOMContentLoaded", () => {
    initCurriculum();

    // hookup listeners
    document.getElementById("class").addEventListener("change", () => {
        updateSubjects();
        updateFormVisibility();
        updateSidebar();
    });



    // difficulty radios (if present)
    document.querySelectorAll('input[name="difficulty"]').forEach(r => {
        r.addEventListener('change', updateSidebar);
    });
    document.getElementById("subject").addEventListener("change", () => {
        updateChapters();
        updateSidebar();
    });
    document.getElementById("chapter").addEventListener("change", updateSidebar);
    document.getElementById("totalMarks").addEventListener("change", updateSidebar);
    const examTypeEl = document.getElementById("examType");
    examTypeEl.addEventListener("change", () => {
        updateFormVisibility();
        updateSidebar();
        // provide guidance when type changes
        const val = examTypeEl.value;
        if (val === "state-board") {
            showHint("Pick your state board and specify scope, then choose class/subject.");
        } else if (val === "competitive") {
            showHint("Select competitive exam and paper scope (chapter or full syllabus).");
        } else {
            showHint("Start by selecting the paper type above.");
        }
    });
    document.getElementById("stateSelect").addEventListener("change", updateSidebar);
    document.getElementById("competitiveExam").addEventListener("change", updateSidebar);
    document.getElementById("scopeSelect")?.addEventListener("change", () => {
        updateFormVisibility();
        updateSidebar();
        const val = document.getElementById("scopeSelect").value;
        if (val === "all") {
            showHint("Full syllabus chosen – chapter selection is disabled.");
        } else {
            showHint("Chapter-specific paper; please choose a chapter.");
        }
    });

    // answer key toggle (no custom override textarea in current UI)
    document.getElementById("includeKey")?.addEventListener("change", e => {
        updateSidebar();
        // when checked we only include the generated key in PDF; no manual textarea
    });

    // field hint and focus helpers
    const hintEl = document.getElementById("fieldHint");
    function showHint(text) {
        if (hintEl) hintEl.textContent = text || "";
    }
    document.querySelectorAll("select, input, textarea").forEach(el => {
        const hint = el.dataset.hint;
        el.addEventListener("focus", () => {
            showHint(hint);
            const card = el.closest(".card");
            if (card) card.classList.add("focused");
        });
        el.addEventListener("blur", () => {
            const card = el.closest(".card");
            if (card) card.classList.remove("focused");
        });
    });

    document.getElementById("paperForm").addEventListener("submit", e => {
        e.preventDefault();
        generatePaper();
    });

    // set theme if saved
    const theme = localStorage.getItem("theme");
    if (theme === "dark") {
        document.documentElement.setAttribute("data-theme", "dark");
    }

    // sidebar collapse toggle
    const sidebar = document.querySelector('.sidebar');
    document.getElementById('toggleSidebar').addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // initial updates
    updateFormVisibility();
    updateSidebar();
});