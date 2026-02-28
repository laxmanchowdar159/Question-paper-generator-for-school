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

    }
    catch {

        console.warn("Using fallback curriculum");

    }

}


// =====================================================
// UPDATE SUBJECTS
// =====================================================

async function updateSubjects() {

    const cls = document.getElementById("class").value;

    const subjectSelect =
        document.getElementById("subject");

    const chapterSelect =
        document.getElementById("chapter");

    subjectSelect.innerHTML =
        '<option value="">Select Subject</option>';

    chapterSelect.innerHTML =
        '<option value="">Select Chapter</option>';

    if (!cls) return;

    let subjects = null;

    try {

        const res =
            await fetch(`/chapters?class=${cls}`);

        const json = await res.json();

        if (json.success && json.data) {

            subjects =
                Object.keys(json.data);

            curriculumData[cls] =
                json.data;

        }

    }
    catch {}

    if (!subjects && curriculumData[cls]) {

        subjects =
            Object.keys(curriculumData[cls]);

    }

    if (!subjects) return;

    subjects.forEach(subject => {

        const opt =
            document.createElement("option");

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

    const selected =
        document.querySelector(
            'input[name="difficulty"]:checked'
        );

    return selected?.value || "Medium";

}


// =====================================================
// DYNAMIC FORM VISIBILITY
// =====================================================

function updateFormVisibility() {
    const examType = document.getElementById("examType").value;
    const stateCard = document.getElementById("stateCard");
    const competitiveCard = document.getElementById("competitiveCard");
    const scopeCard = document.getElementById("scopeCard");
    const chapterCard = document.getElementById("chapter")?.closest(".card");

    // toggle cards based on examType
    if (examType === "state-board") {
        stateCard.style.display = "block";
        competitiveCard.style.display = "none";
        scopeCard && (scopeCard.style.display = "none");
    } else if (examType === "competitive") {
        stateCard.style.display = "none";
        competitiveCard.style.display = "block";
        scopeCard && (scopeCard.style.display = "block");
    } else {
        stateCard.style.display = "none";
        competitiveCard.style.display = "none";
        scopeCard && (scopeCard.style.display = "none");
    }

    // adjust chapter selector when "all chapters" scope is chosen
    const scope = document.getElementById("scopeSelect")?.value;
    if (scope === "all") {
        chapterCard && (chapterCard.style.display = "none");
    } else {
        chapterCard && (chapterCard.style.display = "block");
    }
}


// =====================================================
// GENERATE PAPER
// =====================================================

async function generatePaper() {

    // determine scope: single chapter or all chapters
    const scope = document.getElementById("scopeSelect")?.value || "single";

    const payload = {

        class:
            document.getElementById("class").value,

        subject:
            document.getElementById("subject").value,

        // if user requested all chapters we send blank so backend treats as full syllabus
        chapter:
            scope === "all" ? "" : document.getElementById("chapter").value,

        marks:
            document.getElementById("totalMarks")?.value || "100",

        difficulty:
            getDifficulty(),

        suggestions:
            document.getElementById("suggestions")?.value || ""

    };
    
    // Include paper type info
    payload.examType = document.getElementById("examType")?.value || "";

    // If state board selected include state
    const state = document.getElementById("stateSelect")?.value;
    if (state) payload.state = state;

    // If competitive selected include exam
    const comp = document.getElementById("competitiveExam")?.value;
    if (comp) payload.competitiveExam = comp;

    // include scope for clarity (not needed by backend but useful in logging)
    if (scope === "all") payload.all_chapters = true;


    try {

        const res = await fetch("/generate", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(payload)

        });


        const result =
            await res.json();


        showLoading(false);


        if (!result.success) {

            showToast("Generation failed");

            return;

        }


        currentPaper =
            result.paper || "";

        currentAnswerKey =
            result.answer_key || "";


        showToast("Paper generated");

    }
    catch {

        showLoading(false);

        showToast("Server error");

    }

}


// =====================================================
// DOWNLOAD PDF
// =====================================================

async function downloadPDF() {

    if (!currentPaper) {

        showToast("Generate paper first");

        return;

    }
    // safeguard: sometimes paper is just whitespace
    if (!currentPaper.trim()) {
        showToast("📄 Paper text is empty, generate again");
        return;
    }

    // check scope for chapter
    const scope = document.getElementById("scopeSelect")?.value || "single";

    showLoading(true);

    const payload = {
        pdf_only: true,
        class: document.getElementById("class").value,
        subject: document.getElementById("subject").value,
        chapter: scope === "all" ? "" : document.getElementById("chapter").value,
        marks: document.getElementById("totalMarks")?.value || "100",
        difficulty: getDifficulty(),
        suggestions: document.getElementById("suggestions")?.value || "",
        examType: document.getElementById("examType")?.value || "",
        state: document.getElementById("stateSelect")?.value || "",
        competitiveExam: document.getElementById("competitiveExam")?.value || "",
        includeKey: document.getElementById("includeKey")?.checked || false,
        answer_key: currentAnswerKey
    };

    const res = await fetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    // Also include exam type and conditional fields by sending them as query metadata
    const meta = {
        examType: document.getElementById("examType")?.value || "",
        state: document.getElementById("stateSelect")?.value || "",
        competitiveExam: document.getElementById("competitiveExam")?.value || ""
    };

    // If server needs these for logging/filename etc. we can send a quick notify (optional)
    // Currently PDF generation prefers the supplied `paper` text so metadata is informational.


    const blob =
        await res.blob();


    const url =
        URL.createObjectURL(blob);


    const a =
        document.createElement("a");


    a.href = url;

    a.download = "ExamPaper.pdf";

    document.body.appendChild(a);

    a.click();

    a.remove();

    showLoading(false);

    showToast("PDF downloaded");

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
    document.getElementById("subject").addEventListener("change", () => {
        updateChapters();
        updateSidebar();
    });
    document.getElementById("chapter").addEventListener("change", updateSidebar);
    document.getElementById("totalMarks").addEventListener("change", updateSidebar);
    document.getElementById("examType").addEventListener("change", () => {
        updateFormVisibility();
        updateSidebar();
    });
    document.getElementById("stateSelect").addEventListener("change", updateSidebar);
    document.getElementById("competitiveExam").addEventListener("change", updateSidebar);
    document.getElementById("scopeSelect")?.addEventListener("change", () => {
        updateFormVisibility();
        updateSidebar();
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

    // initial updates
    updateFormVisibility();
    updateSidebar();
});