// =====================================================================
// ExamCraft — Frontend Controller
// Scope: AP/TS State Boards (Classes 6–10) + NTSE, NSO, IMO, IJSO
// =====================================================================

let curriculumData   = {};
let currentPaper     = '';
let currentAnswerKey = '';
let currentMeta      = {};

// ── Competitive exam info (shown after selection) ─────────────────────
const COMP_INFO = {
  NTSE: {
    papers: 'MAT (Mental Ability) + SAT (Science 40Q + Social 40Q + Maths 20Q)',
    marks:  '100 marks each paper',
    time:   '2 Hours per paper',
    marking:'Stage 1: +1 / no negative. Stage 2: +1 / −1/3.',
    tip:    'Select "MAT" as subject for the Mental Ability paper, or any subject for the SAT paper.',
  },
  NSO: {
    papers: 'Logical Reasoning (10Q) + Science (35Q) + Achiever\'s Section (5Q × 3M)',
    marks:  '60 marks total',
    time:   '1 Hour',
    marking:'No negative marking.',
    tip:    'Select the class and science chapter. The Achiever\'s Section auto-generates as harder HOT questions.',
  },
  IMO: {
    papers: 'Logical Reasoning (10Q) + Mathematical Reasoning (25Q) + Everyday Maths (10Q) + Achiever\'s (5Q × 3M)',
    marks:  '60 marks total',
    time:   '1 Hour',
    marking:'No negative marking.',
    tip:    'Select the class and maths chapter for a focused paper.',
  },
  IJSO: {
    papers: 'Integrated Science MCQ: Physics (27Q) + Chemistry (27Q) + Biology (26Q)',
    marks:  '80Q × +3/−1 = 240 max',
    time:   '2 Hours',
    marking:'+3 correct, −1 wrong.',
    tip:    'Select class and chapter (or leave as Full Syllabus for mixed paper).',
  },
};

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
    const list = document.getElementById('historyList');
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

    const examType = document.getElementById('examType')?.value;
    const compExam = document.getElementById('competitiveExam')?.value;

    // For competitive exams, use the competitive curriculum key
    let lookupKey = cls;
    if (examType === 'competitive' && compExam) {
        lookupKey = compExam;
    }

    let subjects = null;
    try {
        const res  = await fetch(`/chapters?class=${lookupKey}`);
        const json = await res.json();
        if (json.success && json.data) {
            subjects = Object.keys(json.data);
            curriculumData[lookupKey] = json.data;
        }
    } catch {}

    if (!subjects && curriculumData[lookupKey]) subjects = Object.keys(curriculumData[lookupKey]);
    subjectSelect.innerHTML = '<option value="">Select subject…</option>';
    chapterSelect.innerHTML = '<option value="">Select chapter…</option>';

    if (subjects) {
        subjects.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s; opt.textContent = s;
            subjectSelect.appendChild(opt);
        });
    }
    updateSidebar();
}

function updateChapters() {
    const cls      = document.getElementById('class').value;
    const subj     = document.getElementById('subject').value;
    const chapSel  = document.getElementById('chapter');
    const examType = document.getElementById('examType')?.value;
    const compExam = document.getElementById('competitiveExam')?.value;

    let lookupKey = cls;
    if (examType === 'competitive' && compExam) lookupKey = compExam;

    chapSel.innerHTML = '<option value="">Select chapter…</option>';
    if (!subj || !curriculumData[lookupKey]) return;
    const chapters = curriculumData[lookupKey][subj] || [];
    chapters.forEach(ch => {
        const opt = document.createElement('option');
        opt.value = ch; opt.textContent = ch;
        chapSel.appendChild(opt);
    });
    updateSidebar();
}

// ── Form Visibility ───────────────────────────────────────────────────
function updateFormVisibility() {
    const examType = document.getElementById('examType').value;
    const scope    = document.getElementById('scopeSelect').value;
    const stateC   = document.getElementById('stateCard');
    const compC    = document.getElementById('competitiveCard');
    const scopeC   = document.getElementById('scopeCard');
    const chapCard = document.getElementById('chapterCard');
    const subjCard = document.getElementById('subjectCard');

    // Show/hide board selector
    stateC.classList.toggle('collapsed', examType !== 'state-board');
    compC.classList.toggle('collapsed', examType !== 'competitive');

    // Show scope selector only after board is chosen
    if (examType) {
        scopeC.classList.remove('collapsed');
    } else {
        scopeC.classList.add('collapsed');
    }

    // Show chapter only for single-chapter scope
    const showChap = scope === 'single';
    if (chapCard) chapCard.style.display = showChap ? '' : 'none';
    if (subjCard) subjCard.style.display = '';  // always show subject
}

// ── Paper type tiles ──────────────────────────────────────────────────
window.selectType = function(val) {
    document.querySelectorAll('.type-tile').forEach(t => t.classList.remove('active'));
    const tile = document.getElementById(val === 'state-board' ? 'tile-state' : 'tile-comp');
    if (tile) tile.classList.add('active');
    document.getElementById('examType').value = val;
    updateFormVisibility();
    updateSidebar();
    // Reset curriculum when switching type
    updateSubjects();

    if (val === 'state-board') {
        setHint('Select Andhra Pradesh or Telangana, then choose paper scope.');
    } else {
        setHint('Select the competitive exam. Each has its own paper pattern.');
    }
};

// ── Scope ─────────────────────────────────────────────────────────────
window.selectScope = function(val) {
    document.querySelectorAll('.scope-btn').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById(`scope-${val}`);
    if (btn) btn.classList.add('active');
    document.getElementById('scopeSelect').value = val;
    updateFormVisibility();
    applySmartMarkDefault(val);
    updateSidebar();
    setHint(val === 'all'
        ? 'Full syllabus — class selection is sufficient.'
        : 'Single chapter — please choose subject and chapter.');
};

// ── Competitive exam info box ─────────────────────────────────────────
function updateCompInfo() {
    const exam    = document.getElementById('competitiveExam')?.value;
    const infoBox = document.getElementById('compInfoBox');
    const infoTxt = document.getElementById('compInfoText');
    if (!infoBox || !infoTxt) return;
    if (!exam || !COMP_INFO[exam]) {
        infoBox.style.display = 'none';
        return;
    }
    const info = COMP_INFO[exam];
    infoTxt.innerHTML = `
      <b>${exam}</b>: ${info.papers}<br>
      <span style="opacity:.8">Marks: ${info.marks} · Time: ${info.time} · ${info.marking}</span><br>
      <span style="color:var(--accent-2)">💡 ${info.tip}</span>`;
    infoBox.style.display = 'block';
    // Also update curriculum for this exam
    updateSubjects().then(updateChapters);
}

// ── Difficulty ───────────────────────────────────────────────────────
function getDifficulty() {
    const el = document.querySelector('input[name="difficulty"]:checked');
    return el ? el.value : 'Medium';
}
window.selectDiff = function(val, btn) {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const radio = document.getElementById(val === 'Easy' ? 'r-easy' : val === 'Medium' ? 'r-med' : 'r-hard');
    if (radio) radio.checked = true;
    updateSidebar();
};

// ── Marks chips ───────────────────────────────────────────────────────
window.selectMark = function(btn) {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const customWrap = document.getElementById('customMarkWrap');
    if (customWrap) customWrap.style.display = 'none';
    const hint = document.getElementById('marksAutoHint');
    if (hint) hint.textContent = '';
    document.getElementById('totalMarks').value = btn.dataset.val;
    updateSidebar();
};
window.toggleCustomMark = function(btn) {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    const hint = document.getElementById('marksAutoHint');
    if (hint) hint.textContent = '';
    const customWrap = document.getElementById('customMarkWrap');
    const customInput = document.getElementById('customMarkInput');
    if (customWrap) {
        customWrap.style.display = 'flex';
        if (customInput) customInput.focus();
    }
};
window.applyCustomMark = function(val) {
    const num = parseInt(val, 10);
    if (num > 0) {
        document.getElementById('totalMarks').value = num;
        updateSidebar();
    }
};

// Smart mark defaults
function applySmartMarkDefault(scope) {
    const customChip = document.getElementById('chipCustom');
    const isCustom   = customChip && customChip.classList.contains('active');
    if (!isCustom) {
        const target = scope === 'all' ? '100' : '50';
        document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
        const hint = document.getElementById('marksAutoHint');
        document.getElementById('customMarkWrap').style.display = 'none';
        const targetChip = document.querySelector(`.chip[data-val="${target}"]`);
        if (targetChip) {
            targetChip.classList.add('active');
            if (hint) hint.textContent = scope === 'all' ? '(full syllabus default)' : '(chapter default)';
        }
        document.getElementById('totalMarks').value = target;
        updateSidebar();
    }
}

// ── Loading ───────────────────────────────────────────────────────────
let _stepInterval = null;
function showLoading(show, titleText) {
    const modal = document.getElementById('loadingModal');
    if (!modal) return;
    modal.style.display = show ? 'flex' : 'none';
    if (titleText) { const t = document.getElementById('loaderTitle'); if (t) t.textContent = titleText; }
    clearInterval(_stepInterval);
    if (show) {
        const ids = ['ls1','ls2','ls3','ls4','ls5'];
        const delays = [0, 5000, 11000, 17000, 26000];
        ids.forEach(id => { const el = document.getElementById(id); if (el) el.classList.remove('active','done'); });
        const el0 = document.getElementById(ids[0]); if (el0) el0.classList.add('active');
        ids.slice(1).forEach((id, idx) => {
            setTimeout(() => {
                const prev = document.getElementById(ids[idx]);
                if (prev) { prev.classList.remove('active'); prev.classList.add('done'); }
                const cur = document.getElementById(id);
                if (cur) cur.classList.add('active');
            }, delays[idx + 1]);
        });
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

    if (!examType) { showToast('Please select a paper type first'); return; }

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

    if (examType === 'state-board') {
        payload.state = document.getElementById('stateSelect')?.value || '';
        if (!payload.state) { showToast('Please select a state board'); return; }
        if (scope === 'single') {
            if (!payload.subject) { showToast('Please select a subject'); return; }
            if (!payload.chapter) { showToast('Please select a chapter'); return; }
        }
    }
    if (examType === 'competitive') {
        payload.competitiveExam = document.getElementById('competitiveExam')?.value || '';
        if (!payload.competitiveExam) { showToast('Please select a competitive exam'); return; }
        if (scope === 'single' && !payload.subject) {
            showToast('Please select a subject/paper type');
            return;
        }
    }
    if (scope === 'all') payload.all_chapters = true;

    showLoading(true, 'Crafting your paper…');
    setHint('Generating — usually 20–45 seconds…');

    try {
        const res    = await fetch('/generate', {
            method:  'POST',
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

        setHint('Paper ready! Review below, then click Download PDF.');
        showToast('Paper generated! Review and download below.');
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
            method:  'POST',
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
    document.getElementById('subject')?.addEventListener('change', () => {
        updateChapters(); updateSidebar();
    });
    document.getElementById('chapter')?.addEventListener('change', updateSidebar);
    document.getElementById('totalMarks')?.addEventListener('change', updateSidebar);
    document.getElementById('stateSelect')?.addEventListener('change', updateSidebar);
    document.getElementById('competitiveExam')?.addEventListener('change', () => {
        updateCompInfo();
        updateSidebar();
    });
    document.getElementById('includeKey')?.addEventListener('change', updateSidebar);

    document.getElementById('examType')?.addEventListener('change', () => {
        updateFormVisibility(); updateSidebar();
    });
    document.getElementById('scopeSelect')?.addEventListener('change', () => {
        updateFormVisibility(); updateSidebar();
    });
    document.getElementById('paperForm')?.addEventListener('submit', e => {
        e.preventDefault(); generatePaper();
    });

    updateFormVisibility();
    updateSidebar();
    applySmartMarkDefault('single');
});