// =====================================================================
// ExamCraft — Frontend Controller
// Features: history panel (localStorage), manual PDF download,
//           all existing form logic preserved
// =====================================================================

let curriculumData   = {};
let currentPaper     = '';
let currentAnswerKey = '';
let currentMeta      = {};

// ── History ──────────────────────────────────────────────────────────
const HISTORY_KEY = 'examcraft_history';
const HISTORY_MAX = 5;

function loadHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
    catch { return []; }
}
function saveHistory(history) {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}
function addToHistory(meta, paper, answerKey) {
    const history = loadHistory();
    const entry = {
        id:         Date.now(),
        timestamp:  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        date:       new Date().toLocaleDateString([], { day: 'numeric', month: 'short' }),
        board:      meta.board      || '',
        subject:    meta.subject    || 'Unknown',
        chapter:    meta.chapter    || 'Full Syllabus',
        marks:      meta.marks      || '100',
        difficulty: meta.difficulty || 'Medium',
        paper,
        answerKey,
    };
    history.unshift(entry);
    if (history.length > HISTORY_MAX) history.length = HISTORY_MAX;
    saveHistory(history);
    renderHistory();
}

function renderHistory() {
    const list    = document.getElementById('historyList');
    if (!list) return;
    const history = loadHistory();
    if (!history.length) {
        list.innerHTML = `<div class="history-empty">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".3">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
          </svg>
          <span>No papers yet</span>
        </div>`;
        return;
    }
    list.innerHTML = history.map((e, idx) => `
      <div class="history-item">
        <div class="history-item-top">
          <div class="history-item-name">${e.subject}${e.chapter !== 'Full Syllabus' ? ' · ' + e.chapter : ''}</div>
          <div class="history-item-time">${e.date}<br>${e.timestamp}</div>
        </div>
        <div class="history-item-meta">
          ${e.board ? `<span class="history-tag">${e.board.replace(' State Board','')}</span>` : ''}
          <span class="history-tag">${e.marks}M</span>
          <span class="history-tag">${e.difficulty}</span>
        </div>
        <div class="history-item-btns">
          <button class="history-dl-btn paper" onclick="downloadFromHistory(${idx}, false)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Paper PDF
          </button>
          ${e.answerKey ? `<button class="history-dl-btn key" onclick="downloadFromHistory(${idx}, true)">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
            + Key PDF
          </button>` : ''}
        </div>
      </div>`).join('');
}

window.clearHistory = function() {
    localStorage.removeItem(HISTORY_KEY);
    renderHistory();
    showToast('History cleared');
};

async function downloadFromHistory(idx, withKey) {
    const history = loadHistory();
    const e = history[idx];
    if (!e) return;
    await triggerPDFDownload({
        paper:      e.paper,
        answer_key: e.answerKey || '',
        subject:    e.subject,
        chapter:    e.chapter !== 'Full Syllabus' ? e.chapter : '',
        board:      e.board,
        includeKey: withKey,
    }, e.board, e.subject, e.chapter, withKey);
}

// ── Sidebar ───────────────────────────────────────────────────────────
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
    if (examType === 'state-board')      boardText = document.getElementById('stateSelect')?.value || '—';
    else if (examType === 'competitive') boardText = document.getElementById('competitiveExam')?.value || '—';
    setSidebarValue('sb-board', boardText);
    setSidebarValue('sb-key',   document.getElementById('includeKey')?.checked ? 'Yes' : 'No');
}

// ── Curriculum ────────────────────────────────────────────────────────
async function initCurriculum() {
    try {
        const res  = await fetch('/chapters');
        const json = await res.json();
        if (json.success && json.data) curriculumData = json.data;
    } catch { console.warn('Curriculum fetch failed'); }
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
    if (subjects?.length) subjects.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s; opt.textContent = s; subjectSelect.appendChild(opt);
    });
}
function updateChapters() {
    const cls           = document.getElementById('class').value;
    const subject       = document.getElementById('subject').value;
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="">Select chapter…</option>';
    if (!cls || !subject) return;
    (curriculumData[cls]?.[subject] || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c; chapterSelect.appendChild(opt);
    });
}

// ── Difficulty ────────────────────────────────────────────────────────
function getDifficulty() {
    const radio = document.querySelector('input[name="difficulty"]:checked');
    return radio ? radio.value : 'Medium';
}

// ── Form Visibility ───────────────────────────────────────────────────
function updateFormVisibility() {
    const examType        = document.getElementById('examType').value;
    const stateCard       = document.getElementById('stateCard');
    const competitiveCard = document.getElementById('competitiveCard');
    const scopeCard       = document.getElementById('scopeCard');
    const subjectCard     = document.getElementById('subjectCard');
    const chapterCard     = document.getElementById('chapterCard');
    const marksCard       = document.getElementById('marksCard');
    const difficultyCard  = document.getElementById('difficultyCard');

    function show(el) { if (!el) return; el.style.display = ''; el.classList.remove('collapsed'); el.classList.add('expanded'); }
    function hide(el) { if (!el) return; el.style.display = 'none'; el.classList.remove('expanded'); el.classList.add('collapsed'); }

    hide(subjectCard); document.getElementById('subject').value = '';
    hide(chapterCard); document.getElementById('chapter').value = '';
    hide(marksCard);   document.getElementById('totalMarks').value = '100';

    if (examType === 'state-board') {
        show(stateCard); hide(competitiveCard);
        show(scopeCard); show(subjectCard); show(marksCard); show(difficultyCard);
        const scope = document.getElementById('scopeSelect')?.value;
        if (scope === 'all') { hide(chapterCard); document.getElementById('chapter').value = ''; }
        else show(chapterCard);
    } else if (examType === 'competitive') {
        hide(stateCard); show(competitiveCard);
        show(scopeCard); show(difficultyCard);
        const scope = document.getElementById('scopeSelect')?.value;
        if (scope === 'all') {
            hide(subjectCard); document.getElementById('subject').value = '';
            hide(chapterCard); document.getElementById('chapter').value = '';
            hide(marksCard);   document.getElementById('totalMarks').value = '100';
        } else { show(subjectCard); show(chapterCard); show(marksCard); }
    } else {
        hide(stateCard); hide(competitiveCard); hide(scopeCard); hide(difficultyCard);
    }
    const globalScope = document.getElementById('scopeSelect')?.value;
    if (globalScope === 'all') {
        hide(subjectCard); document.getElementById('subject').value = '';
        hide(chapterCard); document.getElementById('chapter').value = '';
    }
}

// ── Selection handlers ────────────────────────────────────────────────
window.selectType = function(val) {
    document.querySelectorAll('.type-tile').forEach(t => t.classList.remove('active'));
    const tile = val === 'state-board' ? document.getElementById('tile-state') : document.getElementById('tile-comp');
    if (tile) tile.classList.add('active');
    const sel = document.getElementById('examType');
    sel.value = val; sel.dispatchEvent(new Event('change'));
};
window.selectScope = function(val) {
    document.querySelectorAll('.scope-btn').forEach(b => b.classList.remove('active'));
    const btn = val === 'single' ? document.getElementById('scope-single') : document.getElementById('scope-all');
    if (btn) btn.classList.add('active');
    const sel = document.getElementById('scopeSelect');
    sel.value = val; sel.dispatchEvent(new Event('change'));
};
window.selectMark = function(btn) {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('totalMarks').value = btn.dataset.val;
    updateSidebar();
};
window.selectDiff = function(val, btn) {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const radio = document.getElementById(val === 'Easy' ? 'r-easy' : val === 'Medium' ? 'r-med' : 'r-hard');
    if (radio) radio.checked = true;
    updateSidebar();
};

// ── Loading ───────────────────────────────────────────────────────────
let _stepInterval = null;
function showLoading(show, titleText) {
    const modal = document.getElementById('loadingModal');
    if (!modal) return;
    modal.style.display = show ? 'flex' : 'none';
    if (titleText) { const t = document.getElementById('loaderTitle'); if (t) t.textContent = titleText; }
    clearInterval(_stepInterval);
    if (show) {
        const ids = ['ls1','ls2','ls3','ls4'];
        ids.forEach(id => { const el = document.getElementById(id); if (el) el.classList.remove('active','done'); });
        let i = 0;
        const el0 = document.getElementById(ids[0]); if (el0) el0.classList.add('active');
        _stepInterval = setInterval(() => {
            const cur = document.getElementById(ids[i]);
            if (cur) { cur.classList.remove('active'); cur.classList.add('done'); }
            i++;
            if (i < ids.length) { const nxt = document.getElementById(ids[i]); if (nxt) nxt.classList.add('active'); }
            else clearInterval(_stepInterval);
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

// ── Theme ─────────────────────────────────────────────────────────────
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}

// ── Hint ──────────────────────────────────────────────────────────────
function setHint(text) {
    const el = document.getElementById('hintText'); if (el) el.textContent = text;
}

// ── Preview Tab ───────────────────────────────────────────────────────
window.switchPreviewTab = function(tab, btn) {
    document.querySelectorAll('.p-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-paper').style.display = tab === 'paper' ? 'block' : 'none';
    document.getElementById('tab-key').style.display   = tab === 'key'   ? 'block' : 'none';
};

// ── Generate ─────────────────────────────────────────────────────────
async function generatePaper() {
    const scope    = document.getElementById('scopeSelect')?.value || 'single';
    const examType = document.getElementById('examType').value;

    const payload = {
        class:       document.getElementById('class').value,
        subject:     document.getElementById('subject').value,
        chapter:     scope === 'all' ? '' : document.getElementById('chapter').value,
        marks:       document.getElementById('totalMarks')?.value || '100',
        difficulty:  getDifficulty(),
        suggestions: document.getElementById('suggestions')?.value || '',
        includeKey:  document.getElementById('includeKey')?.checked || false,
        examType,
    };

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

    showLoading(true, 'Crafting your paper…');
    setHint('Generating — usually 15–30 seconds…');

    try {
        const res    = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
        });
        const result = await res.json();
        showLoading(false);

        if (!result.success) {
            showToast(result.error || 'Generation failed — please try again');
            setHint('Something went wrong. Check your selections and try again.');
            return;
        }

        currentPaper     = result.paper     || '';
        currentAnswerKey = result.answer_key || '';

        const boardText = result.board || payload.state || payload.competitiveExam || '';
        currentMeta = {
            board:      boardText,
            subject:    payload.subject || result.subject || '',
            chapter:    payload.chapter || result.chapter || 'Full Syllabus',
            marks:      payload.marks,
            difficulty: payload.difficulty,
        };

        const paperOut = document.getElementById('paperOutput');
        const keyOut   = document.getElementById('answerKeyOutput');
        if (paperOut) paperOut.value = currentPaper;
        if (keyOut)   keyOut.value   = currentAnswerKey;

        const keyTab = document.getElementById('ptab-key');
        if (keyTab) keyTab.style.display = currentAnswerKey ? 'inline-flex' : 'none';

        const panel = document.getElementById('resultsPanel');
        if (panel) {
            panel.style.display = 'block';
            setTimeout(() => panel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 120);
        }

        // NO auto-download — user reviews first, then clicks download
        setHint('Paper ready! Review below, then click Download PDF.');
        showToast('Paper generated! Review and download below.');

        // Add to history
        addToHistory(currentMeta, currentPaper, currentAnswerKey);

    } catch (err) {
        showLoading(false);
        showToast('Server error: ' + err.message);
    }
}

// ── Core PDF downloader ───────────────────────────────────────────────
async function triggerPDFDownload(payload, board, subject, chapter, withKey) {
    showLoading(true, 'Rendering PDF…');
    try {
        const res = await fetch('/download-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload),
        });
        if (!res.ok) {
            let errMsg = `Server error ${res.status}`;
            try { const j = await res.json(); errMsg = j.error || errMsg; } catch {}
            showToast('PDF error: ' + errMsg);
            showLoading(false); return;
        }
        const blob = await res.blob();
        if (blob.size === 0) { showToast('PDF was empty — try regenerating'); showLoading(false); return; }
        const url  = URL.createObjectURL(blob);
        const a    = document.createElement('a');
        const parts = [board, subject, chapter || 'Paper'].filter(Boolean);
        const safe  = parts.join('_').replace(/\s+/g, '_').replace(/[\/\\:*?"<>|]/g, '-');
        a.href     = url;
        a.download = safe + (withKey ? '_with_key' : '') + '.pdf';
        document.body.appendChild(a); a.click(); a.remove();
        URL.revokeObjectURL(url);
        showLoading(false);
        showToast('PDF downloaded ✓');
    } catch (err) {
        showLoading(false);
        showToast('Download failed: ' + err.message);
    }
}

window.downloadPDF = async function(withKey) {
    if (!currentPaper?.trim()) { showToast('Generate a paper first'); return; }
    const includeKey = withKey === true  ? true
                     : withKey === false ? false
                     : (document.getElementById('includeKey')?.checked || false);
    await triggerPDFDownload({
        paper:      currentPaper,
        answer_key: currentAnswerKey || '',
        subject:    currentMeta.subject,
        chapter:    currentMeta.chapter !== 'Full Syllabus' ? currentMeta.chapter : '',
        board:      currentMeta.board,
        includeKey,
    }, currentMeta.board, currentMeta.subject, currentMeta.chapter, includeKey);
};

function copyPaper() {
    if (!currentPaper) { showToast('Nothing to copy'); return; }
    navigator.clipboard.writeText(currentPaper)
        .then(() => showToast('Copied to clipboard ✓'))
        .catch(() => showToast('Copy failed'));
}

// ── Init ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    renderHistory();
    initCurriculum();

    document.getElementById('class')?.addEventListener('change', async () => {
        await updateSubjects(); updateFormVisibility(); updateSidebar();
    });
    document.getElementById('subject')?.addEventListener('change', () => { updateChapters(); updateSidebar(); });
    document.getElementById('chapter')?.addEventListener('change', updateSidebar);
    document.getElementById('totalMarks')?.addEventListener('change', updateSidebar);
    document.getElementById('stateSelect')?.addEventListener('change', updateSidebar);
    document.getElementById('competitiveExam')?.addEventListener('change', updateSidebar);
    document.getElementById('includeKey')?.addEventListener('change', updateSidebar);

    document.getElementById('examType')?.addEventListener('change', () => {
        updateFormVisibility(); updateSidebar();
        const val = document.getElementById('examType').value;
        if (val === 'state-board')      setHint('Select your state board and choose paper scope below.');
        else if (val === 'competitive') setHint('Select the competitive exam and scope.');
        else setHint('Begin by selecting a paper type above.');
    });
    document.getElementById('scopeSelect')?.addEventListener('change', () => {
        updateFormVisibility(); updateSidebar();
        const val = document.getElementById('scopeSelect').value;
        setHint(val === 'all' ? 'Full syllabus — class selection is sufficient.'
                              : 'Single chapter — please choose subject and chapter.');
    });
    document.getElementById('paperForm')?.addEventListener('submit', e => {
        e.preventDefault(); generatePaper();
    });

    updateFormVisibility();
    updateSidebar();
});