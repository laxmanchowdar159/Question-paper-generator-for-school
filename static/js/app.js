'use strict';

/* ══════════════════════════════════════════════════════
   HARDCODED CHAPTERS — instant, zero API delay
   Keyed as CHAPTERS[subject][class]
══════════════════════════════════════════════════════ */
const CHAPTERS = {
  Mathematics: {
    6:  ['Number System','Whole Numbers','Playing with Numbers','Basic Geometrical Ideas','Understanding Elementary Shapes','Integers','Fractions','Decimals','Data Handling','Mensuration','Algebra','Ratio and Proportion','Symmetry','Practical Geometry'],
    7:  ['Integers','Fractions and Decimals','Data Handling','Simple Equations','Lines and Angles','The Triangle and Its Properties','Congruence of Triangles','Comparing Quantities','Rational Numbers','Practical Geometry','Perimeter and Area','Algebraic Expressions','Exponents and Powers','Symmetry','Visualising Solid Shapes'],
    8:  ['Rational Numbers','Linear Equations in One Variable','Understanding Quadrilaterals','Practical Geometry','Data Handling','Squares and Square Roots','Cubes and Cube Roots','Comparing Quantities','Algebraic Expressions and Identities','Visualising Solid Shapes','Mensuration','Exponents and Powers','Direct and Inverse Proportions','Factorisation','Introduction to Graphs','Playing with Numbers'],
    9:  ['Number Systems','Polynomials','Coordinate Geometry','Linear Equations in Two Variables','Introduction to Euclid\'s Geometry','Lines and Angles','Triangles','Quadrilaterals','Areas of Parallelograms and Triangles','Circles','Constructions','Heron\'s Formula','Surface Areas and Volumes','Statistics','Probability'],
    10: ['Real Numbers','Polynomials','Pair of Linear Equations in Two Variables','Quadratic Equations','Arithmetic Progressions','Triangles','Coordinate Geometry','Introduction to Trigonometry','Some Applications of Trigonometry','Circles','Constructions','Areas Related to Circles','Surface Areas and Volumes','Statistics','Probability'],
  },
  Science: {
    6:  ['Food: Where Does It Come From','Components of Food','Fibre to Fabric','Sorting Materials Into Groups','Separation of Substances','Changes Around Us','Getting to Know Plants','Body Movements','The Living Organisms and Their Surroundings','Motion and Measurement of Distances','Light, Shadows and Reflections','Electricity and Circuits','Fun with Magnets','Water','Air Around Us','Garbage In, Garbage Out'],
    7:  ['Nutrition in Plants','Nutrition in Animals','Fibre to Fabric','Heat','Acids, Bases and Salts','Physical and Chemical Changes','Weather, Climate and Adaptations of Animals','Winds, Storms and Cyclones','Soil','Respiration in Organisms','Transportation in Animals and Plants','Reproduction in Plants','Motion and Time','Electric Current and Its Effects','Light','Water: A Precious Resource','Forests: Our Lifeline','Wastewater Story'],
    8:  ['Crop Production and Management','Microorganisms: Friend and Foe','Synthetic Fibres and Plastics','Materials: Metals and Non-Metals','Coal and Petroleum','Combustion and Flame','Conservation of Plants and Animals','Cell — Structure and Functions','Reproduction in Animals','Reaching the Age of Adolescence','Force and Pressure','Friction','Sound','Chemical Effects of Electric Current','Some Natural Phenomena','Light','Stars and the Solar System','Pollution of Air and Water'],
    9:  ['Matter in Our Surroundings','Is Matter Around Us Pure','Atoms and Molecules','Structure of the Atom','The Fundamental Unit of Life','Tissues','Diversity in Living Organisms','Motion','Force and Laws of Motion','Gravitation','Work and Energy','Sound','Why Do We Fall Ill','Natural Resources','Improvement in Food Resources'],
    10: ['Chemical Reactions and Equations','Acids, Bases and Salts','Metals and Non-metals','Carbon and Its Compounds','Periodic Classification of Elements','Life Processes','Control and Coordination','How Do Organisms Reproduce','Heredity and Evolution','Light — Reflection and Refraction','Human Eye and the Colourful World','Electricity','Magnetic Effects of Electric Current','Sources of Energy','Our Environment','Sustainable Management of Natural Resources'],
  },
  English: {
    6:  ['Who Did Patrick\'s Homework','How the Dog Found Himself a New Master','Taro\'s Reward','An Indian-American Woman in Space: Kalpana Chawla','A Different Kind of School','Who I Am','Fair Play','A Game of Chance','Desert Animals','The Banyan Tree'],
    7:  ['Three Questions','A Gift of Chappals','Gopal and the Hilsa Fish','The Ashes That Made Trees Bloom','Quality','Expert Detectives','The Invention of Vita-Wonk','Fire: Friend and Foe','A Bicycle in Good Repair','The Story of Cricket'],
    8:  ['The Best Christmas Present in the World','The Tsunami','Glimpses of the Past','Bepin Choudhury\'s Lapse of Memory','The Summit Within','This is Jody\'s Fawn','A Visit to Cambridge','A Short Monsoon Diary','The Great Stone Face'],
    9:  ['The Fun They Had','The Sound of Music','The Little Girl','A Truly Beautiful Mind','The Snake and the Mirror','My Childhood','Packing','Reach for the Top','The Bond of Love','Kathmandu','If I Were You'],
    10: ['A Letter to God','Nelson Mandela: Long Walk to Freedom','Two Stories about Flying','From the Diary of Anne Frank','The Hundred Dresses','The Hack Driver','Bholi','The Book That Saved the Earth'],
  },
  'Social Studies': {
    6:  ['What, Where, How and When','From Hunting-Gathering to Growing Food','In the Earliest Cities','What Books and Burials Tell Us','Kingdoms, Kings and an Early Republic','New Questions and Ideas','Ashoka, The Emperor Who Gave Up War','Vital Villages, Thriving Towns','Traders, Kings and Pilgrims','New Empires and Kingdoms','Buildings, Paintings and Books','The Earth in the Solar System','Globe: Latitudes and Longitudes','Motions of the Earth','Maps','Major Domains of the Earth','Major Landforms of the Earth','Our Country — India','India: Climate, Vegetation and Wildlife'],
    7:  ['Tracing Changes Through a Thousand Years','New Kings and Kingdoms','The Delhi Sultans','The Mughal Empire','Rulers and Buildings','Towns, Traders and Craftspersons','Tribes, Nomads and Settled Communities','Devotional Paths to the Divine','The Making of Regional Cultures','Eighteenth-Century Political Formations','Tropic and Temperate Grasslands','A Desert','A River Valley','The Polar Regions','Our Environment','Human Environment — Settlement, Transport and Communication','Human Environment Interaction: Tropical and Subtropical Region','Life in the Temperate Grasslands','Life in the Deserts'],
    8:  ['How, When and Where','From Trade to Territory','Ruling the Countryside','Tribals, Dikus and the Vision of a Golden Age','When People Rebel','Weavers, Iron Smelters and Factory Owners','Civilising the Native, Educating the Nation','Women, Caste and Reform','The Making of the National Movement','India After Independence','Resources','Land, Soil, Water, Natural Vegetation and Wildlife','Mineral and Power Resources','Agriculture','Industries','Human Resources'],
    9:  ['The French Revolution','Socialism in Europe and the Russian Revolution','Nazism and the Rise of Hitler','Forest Society and Colonialism','Pastoralists in the Modern World','India — Size and Location','Physical Features of India','Drainage','Climate','Natural Vegetation and Wildlife','Population','What is Democracy? Why Democracy?','Constitutional Design','Electoral Politics','Working of Institutions','Democratic Rights'],
    10: ['The Rise of Nationalism in Europe','Nationalism in India','The Making of a Global World','The Age of Industrialisation','Print Culture and the Modern World','Resources and Development','Forest and Wildlife Resources','Water Resources','Agriculture','Minerals and Energy Resources','Manufacturing Industries','Lifelines of National Economy','Power Sharing','Federalism','Democracy and Diversity','Gender, Religion and Caste','Popular Struggles and Movements','Political Parties','Outcomes of Democracy','Challenges to Democracy'],
  },
};

/* ══════════════════════════════════════════════════════
   DOM REFS  (all IDs must match index.html exactly)
══════════════════════════════════════════════════════ */
const $ = id => document.getElementById(id);

const paperForm      = $('paperForm');
const generateBtn    = $('generateBtn');
const downloadBtn    = $('downloadBtn');
const copyBtn        = $('copyBtn');
const copyKeyBtn     = $('copyKeyBtn');
const outputSection  = $('outputSection');
const paperPreview   = $('paperPreview');
const keyPreview     = $('keyPreview');
const keyCard        = $('keyCard');
const loadingOverlay = $('loadingOverlay');
const statusPill     = $('statusPill');
const statusText     = $('statusText');
const toastContainer = $('toastContainer');
const themeToggle    = $('themeToggle');
const themeLabel     = $('themeLabel');
const mobileMenuBtn  = $('mobileMenuBtn');
const sidebar        = document.querySelector('.sidebar');
const marksSlider    = $('marks');
const marksDisplay   = $('marksDisplay');
const chapterSel     = $('chapter');
const diffGroup      = $('difficultyGroup');
const diffHidden     = $('difficulty');

/* ── State ── */
let pdfData   = null;
let stepTimer = null;

/* ══════════════════════════════════════════════════════
   THEME
   icon-moon / icon-sun are CSS class names on SVGs inside
   the button — NOT element IDs. Use querySelector.
══════════════════════════════════════════════════════ */
const iconMoon = themeToggle.querySelector('.icon-moon');
const iconSun  = themeToggle.querySelector('.icon-sun');

function applyTheme(dark) {
  document.body.classList.toggle('light', !dark);
  if (iconMoon) iconMoon.style.display = dark ? '' : 'none';
  if (iconSun)  iconSun.style.display  = dark ? 'none' : '';
  if (themeLabel) themeLabel.textContent = dark ? 'Dark Mode' : 'Light Mode';
  localStorage.setItem('ec_theme', dark ? 'dark' : 'light');
}
themeToggle.addEventListener('click', () =>
  applyTheme(document.body.classList.contains('light'))
);
applyTheme(localStorage.getItem('ec_theme') !== 'light');

/* ══════════════════════════════════════════════════════
   MOBILE SIDEBAR
══════════════════════════════════════════════════════ */
mobileMenuBtn.addEventListener('click', e => {
  e.stopPropagation();
  sidebar.classList.toggle('open');
});
document.addEventListener('click', e => {
  if (!sidebar.classList.contains('open')) return;
  if (!sidebar.contains(e.target) && !mobileMenuBtn.contains(e.target))
    sidebar.classList.remove('open');
});

/* ══════════════════════════════════════════════════════
   STEP NAV
══════════════════════════════════════════════════════ */
function setStep(n) {
  document.querySelectorAll('.step-item').forEach(el => {
    const s = parseInt(el.dataset.step, 10);
    el.classList.toggle('active', s === n);
    el.classList.toggle('done',   s <  n);
  });
}

/* ══════════════════════════════════════════════════════
   MARKS SLIDER
   Note: CSS uses --surface2 (no dash) — match exactly.
══════════════════════════════════════════════════════ */
function updateSlider(val) {
  if (marksDisplay) marksDisplay.textContent = val;
  const pct = ((Number(val) - 20) / 80) * 100;
  marksSlider.style.background =
    `linear-gradient(to right, var(--accent) ${pct}%, var(--surface2) ${pct}%)`;
}
marksSlider.addEventListener('input', () => updateSlider(marksSlider.value));
updateSlider(marksSlider.value);

/* ══════════════════════════════════════════════════════
   DIFFICULTY PILLS
══════════════════════════════════════════════════════ */
diffGroup.addEventListener('click', e => {
  const btn = e.target.closest('.diff-pill');
  if (!btn) return;
  diffGroup.querySelectorAll('.diff-pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  diffHidden.value = btn.dataset.value;
});

/* ══════════════════════════════════════════════════════
   INSTANT CHAPTER POPULATION
   Reads directly from the hardcoded CHAPTERS table above.
   Zero network calls, zero delay.
══════════════════════════════════════════════════════ */
function populateChapters() {
  const cls     = parseInt($('standard').value, 10);
  const subject = $('subject').value;

  // Always reset to the "All Chapters" default first
  chapterSel.innerHTML = '<option value="">— All Chapters (Full Syllabus) —</option>';

  const list = (CHAPTERS[subject] || {})[cls];
  if (!list || list.length === 0) return;

  list.forEach(ch => {
    const opt = document.createElement('option');
    opt.value = ch;
    opt.textContent = ch;
    chapterSel.appendChild(opt);
  });

  // Restore saved chapter if it's still in the list
  const saved = localStorage.getItem('ec_chapter');
  if (saved && [...chapterSel.options].some(o => o.value === saved))
    chapterSel.value = saved;
}

// Wire up the three fields that affect chapter list
['standard', 'subject'].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener('change', populateChapters);
});

/* ══════════════════════════════════════════════════════
   STATUS PILL
══════════════════════════════════════════════════════ */
function setStatus(type, text) {
  // type: '' | 'loading' | 'error' | 'success'
  statusPill.className = ['status-pill', type].filter(Boolean).join(' ');
  if (statusText) statusText.textContent = text;
}

/* ══════════════════════════════════════════════════════
   TOAST
══════════════════════════════════════════════════════ */
function toast(msg, type = 'info', ms = 3500) {
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${msg}</span>`;
  toastContainer.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(16px)';
    el.style.transition = 'all .28s ease';
    setTimeout(() => el.remove(), 300);
  }, ms);
}

/* ══════════════════════════════════════════════════════
   LOADING STEPS ANIMATOR
══════════════════════════════════════════════════════ */
const STEP_IDS = ['ls1', 'ls2', 'ls3', 'ls4'];

function startLoadingSteps() {
  STEP_IDS.forEach(id => { const el=$(id); if(el) el.className='ls-step'; });
  const first = $(STEP_IDS[0]);
  if (first) first.classList.add('active');
  let idx = 0;
  stepTimer = setInterval(() => {
    const cur = $(STEP_IDS[idx]);
    if (cur) cur.className = 'ls-step done';
    idx++;
    if (idx < STEP_IDS.length) {
      const next = $(STEP_IDS[idx]);
      if (next) next.classList.add('active');
    } else {
      clearInterval(stepTimer);
      stepTimer = null;
    }
  }, 1600);
}

function stopLoadingSteps() {
  if (stepTimer) { clearInterval(stepTimer); stepTimer = null; }
  STEP_IDS.forEach(id => { const el=$(id); if(el) el.className='ls-step done'; });
}

/* ══════════════════════════════════════════════════════
   BUTTON STATE HELPER
   CSS: .btn-spinner { display:none }  .btn-spinner.show { display:flex }
   Must use 'show' class — not 'hidden'.
══════════════════════════════════════════════════════ */
function setBtnState(loading) {
  generateBtn.disabled = loading;
  const icon = generateBtn.querySelector('.btn-icon');
  const text = generateBtn.querySelector('.btn-text');
  const spin = generateBtn.querySelector('.btn-spinner');
  if (loading) {
    if (icon) icon.style.display = 'none';
    if (text) text.textContent   = 'Generating…';
    if (spin) spin.classList.add('show');      // 'show' matches CSS
  } else {
    if (icon) icon.style.display = '';
    if (text) text.textContent   = 'Generate Question Paper';
    if (spin) spin.classList.remove('show');   // 'show' matches CSS
  }
}

/* ══════════════════════════════════════════════════════
   ANSWER KEY SPLITTER
   Uses proper JS regex flags (im) — not Python (?i).
══════════════════════════════════════════════════════ */
function splitAnswerKey(fullText) {
  const re    = /^answer\s+key\s*:?\s*$/im;
  const match = re.exec(fullText);
  if (!match) return { paper: fullText.trim(), key: null };
  return {
    paper: fullText.slice(0, match.index).trim(),
    key:   fullText.slice(match.index + match[0].length).trim() || null,
  };
}

/* ══════════════════════════════════════════════════════
   FORM PERSISTENCE
══════════════════════════════════════════════════════ */
const PERSIST = ['user_name','school_name','standard','board','subject','marks','instructions'];

function saveForm() {
  PERSIST.forEach(k => { const el=$(k); if(el) localStorage.setItem('ec_'+k, el.value); });
  localStorage.setItem('ec_diff', diffHidden.value);
  localStorage.setItem('ec_key',  String($('include_key').checked));
  if (chapterSel.value) localStorage.setItem('ec_chapter', chapterSel.value);
}

function loadForm() {
  PERSIST.forEach(k => {
    const el = $(k);
    if (!el) return;
    const v = localStorage.getItem('ec_'+k);
    if (v !== null) el.value = v;
  });
  updateSlider(marksSlider.value);

  const diff = localStorage.getItem('ec_diff');
  if (diff) {
    diffHidden.value = diff;
    diffGroup.querySelectorAll('.diff-pill').forEach(b =>
      b.classList.toggle('active', b.dataset.value === diff)
    );
  }

  const ik = localStorage.getItem('ec_key');
  if (ik !== null) $('include_key').checked = (ik === 'true');

  // Populate chapters based on restored selections
  populateChapters();
}

paperForm.addEventListener('change', saveForm);

/* ══════════════════════════════════════════════════════
   GENERATE
══════════════════════════════════════════════════════ */
paperForm.addEventListener('submit', async e => {
  e.preventDefault();

  const sections = [...document.querySelectorAll('input[name="sections"]:checked')]
    .map(c => c.value);

  const payload = {
    user_name:    $('user_name').value.trim(),
    school_name:  $('school_name').value.trim(),
    class:        $('standard').value,
    board:        $('board').value,
    subject:      $('subject').value,
    chapter:      chapterSel.value || '',
    marks:        parseInt(marksSlider.value, 10),
    difficulty:   diffHidden.value,
    include_key:  $('include_key').checked,
    instructions: $('instructions').value.trim(),
    sections:     sections.join(', '),
  };

  if (!payload.class || !payload.subject || !payload.difficulty || !payload.marks) {
    toast('Please fill in all required fields.', 'error');
    return;
  }

  setBtnState(true);
  loadingOverlay.style.display = 'flex';
  startLoadingSteps();
  setStatus('loading', 'AI is generating your paper…');
  setStep(4);
  pdfData = null;
  downloadBtn.disabled = true;
  copyBtn.disabled     = true;

  try {
    const res  = await fetch('/generate', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok || !data.success) throw new Error(data.error || 'Generation failed');

    stopLoadingSteps();

    let paperText = data.paper;
    let keyText   = null;
    if (payload.include_key) {
      const split = splitAnswerKey(data.paper);
      paperText   = split.paper;
      keyText     = split.key;
    }

    paperPreview.innerHTML   = '';
    paperPreview.textContent = paperText;
    outputSection.style.display = 'flex';
    setTimeout(() => outputSection.scrollIntoView({ behavior:'smooth', block:'start' }), 80);

    if (keyText) { keyPreview.textContent = keyText; keyCard.style.display = 'block'; }
    else         { keyCard.style.display = 'none'; }

    pdfData = data.pdf;
    downloadBtn.disabled = false;
    copyBtn.disabled     = false;

    setStatus('success', 'Paper generated!');
    toast('Question paper ready! Downloading PDF…', 'success');
    setTimeout(downloadPDF, 800);

  } catch (err) {
    stopLoadingSteps();
    setStatus('error', 'Generation failed');
    toast(err.message || 'Something went wrong. Please try again.', 'error');
    setStep(3);
  } finally {
    loadingOverlay.style.display = 'none';
    setBtnState(false);
  }
});

/* ══════════════════════════════════════════════════════
   DOWNLOAD PDF
══════════════════════════════════════════════════════ */
function downloadPDF() {
  if (!pdfData) { toast('Generate a paper first.', 'error'); return; }
  fetch('/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pdf: pdfData }),
  })
  .then(r => { if (!r.ok) throw new Error('Download failed'); return r.blob(); })
  .then(blob => {
    const url = URL.createObjectURL(blob);
    const a   = Object.assign(document.createElement('a'), { href:url, download:'ExamCraft_QuestionPaper.pdf' });
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast('PDF downloaded!', 'success');
  })
  .catch(err => toast(err.message || 'PDF download failed', 'error'));
}
downloadBtn.addEventListener('click', downloadPDF);

/* ══════════════════════════════════════════════════════
   COPY
══════════════════════════════════════════════════════ */
copyBtn.addEventListener('click', () => {
  const t = paperPreview.textContent.trim();
  if (!t) return;
  navigator.clipboard.writeText(t)
    .then(() => toast('Copied to clipboard!', 'success'))
    .catch(()  => toast('Copy failed', 'error'));
});
copyKeyBtn.addEventListener('click', () => {
  const t = keyPreview.textContent.trim();
  if (!t) return;
  navigator.clipboard.writeText(t)
    .then(() => toast('Answer key copied!', 'success'))
    .catch(()  => toast('Copy failed', 'error'));
});

/* ══════════════════════════════════════════════════════
   INIT
══════════════════════════════════════════════════════ */
loadForm();   // restores saved values and calls populateChapters()
