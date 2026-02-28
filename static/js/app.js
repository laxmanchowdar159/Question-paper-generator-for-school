// =====================================================
// ExamCraft Frontend Controller (Full Production Version)
// =====================================================

document.addEventListener("DOMContentLoaded", () => {

    initUI();

    initCurriculum();

    initSidebarSync();

});


// =====================================================
// GLOBAL STATE
// =====================================================

let curriculumData = {};

let currentPaper = "";

let currentAnswerKey = "";


// =====================================================
// INIT UI
// =====================================================

function initUI() {

    document.getElementById("class")
        ?.addEventListener("change", () => {

            updateSubjects();

            updateSidebar();

        });

    document.getElementById("subject")
        ?.addEventListener("change", () => {

            updateChapters();

            updateSidebar();

        });

    document.getElementById("chapter")
        ?.addEventListener("change", updateSidebar);

    document.getElementById("totalMarks")
        ?.addEventListener("change", updateSidebar);

    document.getElementById("suggestions")
        ?.addEventListener("input", updateSidebar);

    // Show/hide conditional fields based on paper type
    document.getElementById("examType")
        ?.addEventListener("change", (e) => {

            const val = e.target.value;

            const stateCard = document.getElementById("stateCard");
            const compCard = document.getElementById("competitiveCard");

            if (val === "state-board") {
                if (stateCard) stateCard.style.display = "block";
                if (compCard) compCard.style.display = "none";
            }
            else if (val === "competitive") {
                if (stateCard) stateCard.style.display = "none";
                if (compCard) compCard.style.display = "block";
            }
            else {
                if (stateCard) stateCard.style.display = "none";
                if (compCard) compCard.style.display = "none";
            }

            updateSidebar();

        });

    document.getElementById("stateSelect")
        ?.addEventListener("change", updateSidebar);

    document.getElementById("competitiveExam")
        ?.addEventListener("change", updateSidebar);

    // Prevent form default submit and use JS generation
    document.getElementById("paperForm")
        ?.addEventListener("submit", (e) => {
            e.preventDefault();
            generatePaper();
        });

}


// =====================================================
// SIDEBAR SYNC
// =====================================================

function initSidebarSync() {

    updateSidebar();

}


function updateSidebar() {

    const cls =
        document.getElementById("class")?.value || "—";

    const subject =
        document.getElementById("subject")?.value || "—";

    const chapter =
        document.getElementById("chapter")?.value || "—";

    const marks =
        document.getElementById("totalMarks")?.value || "—";

    // Get paper type, board/exam info
    const examType =
        document.getElementById("examType")?.value || "—";

    let boardExam = "—";
    if (examType === "state-board") {
        boardExam = document.getElementById("stateSelect")?.value || "State —";
    } else if (examType === "competitive") {
        boardExam = document.getElementById("competitiveExam")?.value || "Exam —";
    } else if (examType) {
        boardExam = examType;
    }

    setSidebarValue("sb-class", cls);

    setSidebarValue("sb-subject", subject);

    setSidebarValue("sb-chapter", chapter);

    setSidebarValue("sb-marks", marks);

    setSidebarValue("sb-type", examType === "state-board" ? "State Board" : (examType === "competitive" ? "Competitive" : "—"));

    setSidebarValue("sb-board", boardExam);

}


function setSidebarValue(id, value) {

    const el = document.getElementById(id);

    if (el) el.textContent = value;

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
// GENERATE PAPER
// =====================================================

async function generatePaper() {

    const payload = {

        class:
            document.getElementById("class").value,

        subject:
            document.getElementById("subject").value,

        chapter:
            document.getElementById("chapter").value,

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


    showLoading(true);


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


    showLoading(true);


    const res =
        await fetch("/generate", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                pdf_only: true,

                paper: currentPaper,

                subject:
                    document.getElementById("subject").value,

                chapter:
                    document.getElementById("chapter").value

            })

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