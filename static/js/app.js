// =====================================================================
// ExamCraft — Frontend Controller
// Fully compatible with new HTML structure (uses direct IDs, not .card)
// =====================================================================

// ── Global State ─────────────────────────────────────────────────────
let curriculumData  = {};
let currentPaper    = '';
let currentAnswerKey = '';

// ── Sidebar Values ────────────────────────────────────────────────────
function setSidebarValue(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value || '—';
}

function updateSidebar() {
    setSidebarValue('sb-class',      document.getElementById('class')?.value || '—');
    setSidebarValue('sb-subject',    document.getElementById('subject')?.value || '—');
    const scope = document.getElementById('scopeSelect')?.value;
    let chapterText = document.getElementById('chapter')?.value || '—';
    if (scope === 'all') chapterText = 'All Chapters';
    setSidebarValue('sb-chapter',    chapterText);
    setSidebarValue('sb-scope',      scope === 'all' ? 'Full syllabus' : scope === 'single' ? 'Single chapter' : '—');
    setSidebarValue('sb-difficulty', getDifficulty() || '—');
    setSidebarValue('sb-marks',      document.getElementById('totalMarks')?.value || '—');
    const examType = document.getElementById('examType')?.value;
    let boardText = '—';
    if (examType === 'state-board')  boardText = document.getElementById('stateSelect')?.value || '—';
    else if (examType === 'competitive') boardText = document.getElementById('competitiveExam')?.value || '—';
    setSidebarValue('sb-board', boardText);
    setSidebarValue('sb-key',   document.getElementById('includeKey')?.checked ? 'Yes' : 'No');
}

// ── Curriculum ───────────────────────────────────────────────────────
async function initCurriculum() {
    try {
        const res  = await fetch('/chapters');
        const json = await res.json();
        if (json.success && json.data) curriculumData = json.data;
    } catch {
        console.warn('Curriculum fetch failed, using cached data');
    }
    const cls = document.getElementById('class')?.value;
    if (cls) { await updateSubjects(); updateFormVisibility(); updateSidebar(); }
}

async function updateSubjects() {
    const cls           = document.getElementById('class').value;
    const subjectSelect = document.getElementById('subject');
    const chapterSelect = document.getElementById('chapter');

    subjectSelect.innerHTML = '<option value="">Loading…</option>';
    chapterSelect.innerHTML = '<option value="">Select chapter…</option>';

    if (!cls) { subjectSelect.innerHTML = '<option value="">Select subject…</option>'; return; }

    let subjects = null;
    try {
        const res  = await fetch(`/chapters?class=${cls}`);
        const json = await res.json();
        if (json.success && json.data) { subjects = Object.keys(json.data); curriculumData[cls] = json.data; }
    } catch {}

    if (!subjects && curriculumData[cls]) subjects = Object.keys(curriculumData[cls]);

    subjectSelect.innerHTML = '<option value="">Select subject…</option>';
    chapterSelect.innerHTML = '<option value="">Select chapter…</option>';

    if (subjects?.length) {
        subjects.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            subjectSelect.appendChild(opt);
        });
    }
}

function updateChapters() {
    const cls           = document.getElementById('class').value;
    const subject       = document.getElementById('subject').value;
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="">Select chapter…</option>';
    if (!cls || !subject) return;
    const chapters = curriculumData[cls]?.[subject] || [];
    chapters.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        chapterSelect.appendChild(opt);
    });
}

// ── Difficulty ───────────────────────────────────────────────────────
function getDifficulty() {
    const radio = document.querySelector('input[name="difficulty"]:checked');
    if (radio) return radio.value;
    return 'Medium';
}

// ── Form Visibility ───────────────────────────────────────────────────
// Uses direct element IDs (not .closest(".card")) to match new HTML
function updateFormVisibility() {
    const examType       = document.getElementById('examType').value;
    const stateCard      = document.getElementById('stateCard');
    const competitiveCard= document.getElementById('competitiveCard');
    const scopeCard      = document.getElementById('scopeCard');
    const subjectCard    = document.getElementById('subjectCard');
    const chapterCard    = document.getElementById('chapterCard');
    const marksCard      = document.getElementById('marksCard');
    const difficultyCard = document.getElementById('difficultyCard');

    // Helper: show / hide with animation class
    function show(el) { if (!el) return; el.style.display = ''; el.classList.remove('collapsed'); el.classList.add('expanded'); }
    function hide(el) { if (!el) return; el.style.display = 'none'; el.classList.remove('expanded'); el.classList.add('collapsed'); }

    // Reset secondaries
    hide(subjectCard);    document.getElementById('subject').value  = '';
    hide(chapterCard);    document.getElementById('chapter').value  = '';
    hide(marksCard);      document.getElementById('totalMarks').value = '100';
    // Keep difficulty visible always (after examType selected)

    if (examType === 'state-board') {
        show(stateCard);
        hide(competitiveCard);
        show(scopeCard);
        show(subjectCard);
        show(marksCard);
        show(difficultyCard);

        const scope = document.getElementById('scopeSelect')?.value;
        if (scope === 'all') {
            hide(chapterCard);
            document.getElementById('chapter').value = '';
        } else {
            show(chapterCard);
        }
    } else if (examType === 'competitive') {
        hide(stateCard);
        show(competitiveCard);
        show(scopeCard);
        show(difficultyCard);

        const scope = document.getElementById('scopeSelect')?.value;
        if (scope === 'all') {
            hide(subjectCard);
            document.getElementById('subject').value = '';
            hide(chapterCard);
            document.getElementById('chapter').value = '';
            hide(marksCard);
            document.getElementById('totalMarks').value = '100';
        } else {
            show(subjectCard);
            show(chapterCard);
            show(marksCard);
        }
    } else {
        // No type selected yet
        hide(stateCard);
        hide(competitiveCard);
        hide(scopeCard);
        hide(difficultyCard);
    }

    // Enforce global scope rule
    const globalScope = document.getElementById('scopeSelect')?.value;
    if (globalScope === 'all') {
        hide(subjectCard);  document.getElementById('subject').value = '';
        hide(chapterCard);  document.getElementById('chapter').value = '';
    }
}

// ── Type Card Selection (called from HTML onclick) ────────────────────
window.selectType = function(val) {
    document.querySelectorAll('.type-tile').forEach(t => t.classList.remove('active'));
    const tile = val === 'state-board'
        ? document.getElementById('tile-state')
        : document.getElementById('tile-comp');
    if (tile) tile.classList.add('active');

    const sel = document.getElementById('examType');
    sel.value = val;
    sel.dispatchEvent(new Event('change'));
};

// ── Scope Selection ───────────────────────────────────────────────────
window.selectScope = function(val) {
    document.querySelectorAll('.scope-btn').forEach(b => b.classList.remove('active'));
    const btn = val === 'single'
        ? document.getElementById('scope-single')
        : document.getElementById('scope-all');
    if (btn) btn.classList.add('active');

    const sel = document.getElementById('scopeSelect');
    sel.value = val;
    sel.dispatchEvent(new Event('change'));
};

// ── Mark Selection ────────────────────────────────────────────────────
window.selectMark = function(btn) {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('totalMarks').value = btn.dataset.val;
    updateSidebar();
};

// ── Difficulty Selection ──────────────────────────────────────────────
window.selectDiff = function(val, btn) {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    // sync hidden radio
    const radio = document.getElementById(
        val === 'Easy' ? 'r-easy' : val === 'Medium' ? 'r-med' : 'r-hard'
    );
    if (radio) radio.checked = true;
    updateSidebar();
};

// ── Loading Steps Animator ────────────────────────────────────────────
let _stepInterval = null;

function showLoading(show) {
    const modal = document.getElementById('loadingModal');
    if (!modal) return;
    modal.style.display = show ? 'flex' : 'none';
    clearInterval(_stepInterval);
    if (show) {
        const ids = ['ls1','ls2','ls3','ls4'];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.remove('active','done');
        });
        let i = 0;
        const el0 = document.getElementById(ids[0]);
        if (el0) el0.classList.add('active');
        _stepInterval = setInterval(() => {
            const cur = document.getElementById(ids[i]);
            if (cur) { cur.classList.remove('active'); cur.classList.add('done'); }
            i++;
            if (i < ids.length) {
                const nxt = document.getElementById(ids[i]);
                if (nxt) nxt.classList.add('active');
            } else {
                clearInterval(_stepInterval);
            }
        }, 7000);
    }
}

// ── Toast ─────────────────────────────────────────────────────────────
function showToast(msg) {
    const toast = document.getElementById('notificationToast');
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3500);
}

// ── Theme Toggle ──────────────────────────────────────────────────────
function toggleTheme() {
    const html  = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}

// ── Hint Bar ──────────────────────────────────────────────────────────
function setHint(text) {
    const el = document.getElementById('hintText') || document.getElementById('fieldHint');
    if (el && el.id === 'hintText') el.textContent = text;
    else if (el) el.textContent = text;
}

// ── Preview Tab Switch ────────────────────────────────────────────────
window.switchPreviewTab = function(tab, btn) {
    document.querySelectorAll('.p-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-paper').style.display = tab === 'paper' ? 'block' : 'none';
    document.getElementById('tab-key').style.display   = tab === 'key'   ? 'block' : 'none';
};

// ── Generate Paper ────────────────────────────────────────────────────
async function generatePaper() {
    const scope    = document.getElementById('scopeSelect')?.value || 'single';
    const examType = document.getElementById('examType').value;

    // Build payload
    const payload = {
        class:       document.getElementById('class').value,
        subject:     document.getElementById('subject').value,
        chapter:     scope === 'all' ? '' : document.getElementById('chapter').value,
        marks:       document.getElementById('totalMarks')?.value || '100',
        difficulty:  getDifficulty(),
        suggestions: document.getElementById('suggestions')?.value || '',
        includeKey:  document.getElementById('includeKey')?.checked || false,
        examType:    examType,
    };

    // Validate
    if (!examType) { showToast('Please select a paper type first'); return; }
    if (examType === 'state-board') {
        payload.state = document.getElementById('stateSelect')?.value || '';
        if (scope === 'single') {
            if (!payload.subject) { showToast('Please select a subject'); return; }
            if (!payload.chapter) { showToast('Please select a chapter'); return; }
        }
    }
    if (examType === 'competitive') {
        payload.competitiveExam = document.getElementById('competitiveExam')?.value || '';
        if (scope === 'single') {
            if (!payload.subject) { showToast('Please select a subject'); return; }
            if (!payload.chapter) { showToast('Please select a chapter'); return; }
        }
    }
    if (scope === 'all') payload.all_chapters = true;

    showLoading(true);
    setHint('Generating your paper — this usually takes 15–30 seconds…');

    try {
        const res    = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });
        const result = await res.json();
        showLoading(false);

        if (!result.success) {
            showToast(result.error || 'Generation failed — please try again');
            setHint('Something went wrong. Check your selections and try again.');
            console.error('Generation error:', result);
            return;
        }

        currentPaper     = result.paper      || '';
        currentAnswerKey = result.answer_key  || '';

        // Populate preview
        const paperOut = document.getElementById('paperOutput');
        const keyOut   = document.getElementById('answerKeyOutput');
        if (paperOut) paperOut.value = currentPaper;
        if (keyOut)   keyOut.value   = currentAnswerKey;

        // Show key tab if key present
        const keyTab = document.getElementById('ptab-key');
        if (keyTab) keyTab.style.display = currentAnswerKey ? 'inline-flex' : 'none';

        // Show results panel
        const panel = document.getElementById('resultsPanel');
        if (panel) {
            panel.style.display = 'block';
            setTimeout(() => panel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
        }

        setHint('Paper generated! Download the PDF below or copy the text.');
        showToast('Paper generated successfully!');

        // Auto-download
        const includeKey = document.getElementById('includeKey')?.checked || false;
        await downloadPDF(includeKey);

    } catch (err) {
        showLoading(false);
        showToast('Server error: ' + err.message);
        console.error('generatePaper error:', err);
    }
}

// ── Download PDF ──────────────────────────────────────────────────────
async function downloadPDF(withKey) {
    if (!currentPaper?.trim()) {
        showToast('Generate a paper first');
        return;
    }

    const scope      = document.getElementById('scopeSelect')?.value || 'single';
    const subject    = document.getElementById('subject').value || 'Question Paper';
    const chapter    = scope === 'all' ? '' : (document.getElementById('chapter').value || '');
    const includeKey = withKey === true ? true
                     : withKey === false ? false
                     : (document.getElementById('includeKey')?.checked || false);

    // Build board name for filename
    const examType = document.getElementById('examType')?.value || '';
    let boardName = '';
    if (examType === 'state-board') boardName = document.getElementById('stateSelect')?.value || '';
    else if (examType === 'competitive') boardName = document.getElementById('competitiveExam')?.value || '';

    const payload = {
        paper:      currentPaper,
        answer_key: currentAnswerKey || '',
        subject,
        chapter,
        board:      boardName,
        includeKey
    };

    showLoading(true);

    try {
        const res = await fetch('/download-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });

        if (!res.ok) {
            let errMsg = `Server error ${res.status}`;
            try { const j = await res.json(); errMsg = j.error || errMsg; } catch {}
            showToast('PDF error: ' + errMsg);
            showLoading(false);
            return;
        }

        const blob = await res.blob();
        if (blob.size === 0) {
            showToast('PDF was empty — please try generating again');
            showLoading(false);
            return;
        }

        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        const parts = [boardName, subject, chapter || 'Paper'].filter(Boolean);
        const safe = parts.join('_').replace(/\s+/g, '_').replace(/[\/\\:*?"<>|]/g, '-');
        a.href     = url;
        a.download = safe + '.pdf';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);

        showLoading(false);
        showToast('PDF downloaded ✓');

    } catch (err) {
        showLoading(false);
        showToast('Download failed: ' + err.message);
        console.error('downloadPDF error:', err);
    }
}

// ── Copy Paper ────────────────────────────────────────────────────────
function copyPaper() {
    if (!currentPaper) { showToast('Nothing to copy'); return; }
    navigator.clipboard.writeText(currentPaper)
        .then(() => showToast('Copied to clipboard ✓'))
        .catch(() => showToast('Copy failed — please select and copy manually'));
}

// ══════════════════════════════════════════════════════════════════════
// INIT
// ══════════════════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {

    // ── Restore theme ──
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    // ── Sidebar toggle ──
    document.getElementById('toggleSidebar')?.addEventListener('click', () => {
        const sb = document.querySelector('.sidebar');
        if (sb) {
            if (window.innerWidth <= 900) sb.classList.toggle('mobile-open');
            else sb.classList.toggle('collapsed');
        }
    });

    // ── Curriculum ──
    initCurriculum();

    // ── Form listeners ──
    document.getElementById('class')?.addEventListener('change', async () => {
        await updateSubjects();
        updateFormVisibility();
        updateSidebar();
    });
    document.getElementById('subject')?.addEventListener('change', () => {
        updateChapters();
        updateSidebar();
    });
    document.getElementById('chapter')?.addEventListener('change', updateSidebar);
    document.getElementById('totalMarks')?.addEventListener('change', updateSidebar);
    document.getElementById('stateSelect')?.addEventListener('change', updateSidebar);
    document.getElementById('competitiveExam')?.addEventListener('change', updateSidebar);
    document.getElementById('includeKey')?.addEventListener('change', updateSidebar);

    // examType hidden select (driven by tile clicks)
    document.getElementById('examType')?.addEventListener('change', () => {
        updateFormVisibility();
        updateSidebar();
        const val = document.getElementById('examType').value;
        if (val === 'state-board')  setHint('Select your state board and choose paper scope below.');
        else if (val === 'competitive') setHint('Select the competitive exam and scope.');
        else setHint('Begin by selecting a paper type above.');
    });

    // scopeSelect hidden select (driven by scope-btn clicks)
    document.getElementById('scopeSelect')?.addEventListener('change', () => {
        updateFormVisibility();
        updateSidebar();
        const val = document.getElementById('scopeSelect').value;
        setHint(val === 'all'
            ? 'Full syllabus selected — class selection is sufficient.'
            : 'Single chapter selected — please choose subject and chapter.'
        );
    });

    // ── Form submit ──
    document.getElementById('paperForm')?.addEventListener('submit', e => {
        e.preventDefault();
        generatePaper();
    });

    // ── Initial state ──
    updateFormVisibility();
    updateSidebar();
});