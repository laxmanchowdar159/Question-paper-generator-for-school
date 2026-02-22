// ============================================================
// EXAMCRAFT - AI QUESTION PAPER GENERATOR
// Modern JavaScript with Full Functionality
// ============================================================

'use strict';

// ==================== STATE MANAGEMENT ====================
let pdfData = null;
let currentPaper = null;
let currentKey = null;

// ==================== DOM ELEMENTS ====================
const form = document.getElementById('paperForm');
const generateBtn = document.getElementById('generateBtn');
const copyBtn = document.getElementById('copyBtn');
const downloadBtn = document.getElementById('downloadBtn');
const themeToggle = document.getElementById('themeToggle');
const loadingModal = document.getElementById('loadingModal');
const messageBox = document.getElementById('messageBox');
const errorBox = document.getElementById('errorBox');
const outputSection = document.getElementById('outputSection');
const keySection = document.getElementById('keySection');
const outputEl = document.getElementById('output');
const keyEl = document.getElementById('keyOutput');

// Form fields
const userNameInput = document.getElementById('user_name');
const schoolNameInput = document.getElementById('school_name');
const standardSelect = document.getElementById('standard');
const boardSelect = document.getElementById('board');
const subjectSelect = document.getElementById('subject');
const chapterSelect = document.getElementById('chapter');
const marksSelect = document.getElementById('marks');
const difficultyRadios = document.querySelectorAll('input[name="difficulty"]');
const instructionsInput = document.getElementById('instructions');
const includeKeyCheckbox = document.getElementById('include_key');

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
  initializeTheme();
  loadFormData();
  attachEventListeners();
  updateChaptersOnSubjectChange();
});

// ==================== THEME MANAGEMENT ====================
function initializeTheme() {
  const savedTheme = localStorage.getItem('examcraft-theme');
  if (savedTheme === 'dark') {
    document.body.classList.add('dark');
    themeToggle.textContent = '☀️';
  } else {
    document.body.classList.remove('dark');
    themeToggle.textContent = '🌙';
  }
}

themeToggle.addEventListener('click', () => {
  document.body.classList.toggle('dark');
  const isDark = document.body.classList.contains('dark');
  themeToggle.textContent = isDark ? '☀️' : '🌙';
  localStorage.setItem('examcraft-theme', isDark ? 'dark' : 'light');
});

// ==================== FORM PERSISTENCE ====================
function saveFormData() {
  const formState = {
    user_name: userNameInput.value,
    school_name: schoolNameInput.value,
    standard: standardSelect.value,
    board: boardSelect.value,
    subject: subjectSelect.value,
    chapter: chapterSelect.value,
    marks: marksSelect.value,
    difficulty: Array.from(difficultyRadios).find(r => r.checked)?.value || 'Medium',
    instructions: instructionsInput.value,
    include_key: includeKeyCheckbox.checked,
  };
  localStorage.setItem('examcraft-form', JSON.stringify(formState));
}

function loadFormData() {
  const saved = localStorage.getItem('examcraft-form');
  if (!saved) return;

  try {
    const state = JSON.parse(saved);
    if (state.user_name) userNameInput.value = state.user_name;
    if (state.school_name) schoolNameInput.value = state.school_name;
    if (state.standard) standardSelect.value = state.standard;
    if (state.board) boardSelect.value = state.board;
    if (state.subject) subjectSelect.value = state.subject;
    if (state.marks) marksSelect.value = state.marks;
    if (state.instructions) instructionsInput.value = state.instructions;
    if (state.include_key) includeKeyCheckbox.checked = state.include_key;
    if (state.difficulty) {
      const radio = Array.from(difficultyRadios).find(r => r.value === state.difficulty);
      if (radio) radio.checked = true;
    }
  } catch (error) {
    console.error('Failed to load form data:', error);
  }
}

// ==================== EVENT LISTENERS ====================
function attachEventListeners() {
  // Form fields auto-save
  [userNameInput, schoolNameInput, standardSelect, boardSelect, subjectSelect, 
   chapterSelect, marksSelect, instructionsInput, includeKeyCheckbox, ...difficultyRadios]
    .forEach(el => el?.addEventListener('change', saveFormData));

  // Form submission
  form.addEventListener('submit', handleGeneratePaper);

  // Output buttons
  copyBtn.addEventListener('click', copyPaperToClipboard);
  downloadBtn.addEventListener('click', downloadPDF);

  // Subject change triggers chapter loading
  subjectSelect.addEventListener('change', updateChaptersOnSubjectChange);
  standardSelect.addEventListener('change', updateChaptersOnSubjectChange);
  boardSelect.addEventListener('change', updateChaptersOnSubjectChange);
}

// ==================== HARDCODED CHAPTERS ====================
const chaptersDB = {
  'Mathematics': {
    '6': [
      'Knowing Our Numbers',
      'Whole Numbers',
      'Playing with Numbers',
      'Basic Geometrical Ideas',
      'Understanding Elementary Shapes',
      'Integers',
      'Fractions',
      'Decimals',
      'Data Handling',
      'Mensuration',
      'Algebra',
      'Ratio and Proportion'
    ],
    '7': [
      'Integers',
      'Fractions and Decimals',
      'Data Handling',
      'Simple Equations',
      'Lines and Angles',
      'The Triangle and Its Properties',
      'Congruence of Triangles',
      'Comparing Quantities',
      'Rational Numbers',
      'Practical Geometry',
      'Perimeter and Area',
      'Algebraic Expressions',
      'Exponents and Powers',
      'Symmetry',
      'Visualising Solid Shapes'
    ],
    '8': [
      'Rational Numbers',
      'Linear Equations in One Variable',
      'Understanding Quadrilaterals',
      'Practical Geometry',
      'Data Handling',
      'Squares and Square Roots',
      'Cubes and Cube Roots',
      'Comparing Quantities',
      'Algebraic Expressions and Identities',
      'Visualising Solid Shapes',
      'Mensuration',
      'Exponents and Powers',
      'Direct and Inverse Proportions',
      'Factorisation',
      'Introduction to Graphs'
    ],
    '9': [
      'Number Systems',
      'Polynomials',
      'Coordinate Geometry',
      'Linear Equations in Two Variables',
      'Introduction to Euclid Geometry',
      'Lines and Angles',
      'Triangles',
      'Quadrilaterals',
      'Areas of Parallelograms and Triangles',
      'Circles',
      'Constructions',
      'Heron\'s Formula',
      'Surface Areas and Volumes',
      'Statistics',
      'Probability'
    ],
    '10': [
      'Real Numbers',
      'Polynomials',
      'Pair of Linear Equations in Two Variables',
      'Quadratic Equations',
      'Arithmetic Progressions',
      'Triangles',
      'Coordinate Geometry',
      'Introduction to Trigonometry',
      'Some Applications of Trigonometry',
      'Circles',
      'Constructions',
      'Areas Related to Circles',
      'Surface Areas and Volumes',
      'Statistics',
      'Probability'
    ]
  },
  'Science': {
    '6': [
      'Food: Where Does It Come From?',
      'Components of Food',
      'Fiber to Fabric',
      'Sorting Materials into Groups',
      'Separation of Substances',
      'Changes Around Us',
      'Living Organisms and Their Surroundings',
      'Motion and Measurement of Distances',
      'Light, Shadows and Reflections',
      'Electricity and Circuits',
      'Fun with Magnets',
      'Water'
    ],
    '7': [
      'Nutrition in Plants',
      'Nutrition in Animals',
      'Fibre to Fabric',
      'Heat',
      'Acids, Bases and Salts',
      'Physical and Chemical Changes',
      'Weather, Climate and Adaptations of Animals',
      'Winds, Storms and Cyclones',
      'Soil',
      'Respiration in Organisms',
      'Transportation in Animals and Plants',
      'Reproduction in Plants',
      'Motion and Time',
      'Electric Currents and Its Effects',
      'Light'
    ],
    '8': [
      'Crop Production and Management',
      'Microorganisms: Friend and Foe',
      'Synthetic Fibres and Plastics',
      'Materials: Metals and Non-metals',
      'Coal and Petroleum',
      'Combustion and Flame',
      'Conservation of Plants and Animals',
      'Cell: Structure and Functions',
      'Reproduction in Animals',
      'Reaching the Age of Adolescence',
      'Force and Pressure',
      'Friction',
      'Sound',
      'Chemical Effects of Electric Current',
      'Some Natural Phenomena',
      'Light',
      'Stars and The Solar System',
      'Pollution of Air and Water'
    ],
    '9': [
      'Matter in Our Surroundings',
      'Is Matter Around Us Pure',
      'Atoms and Molecules',
      'Structure of the Atom',
      'The Fundamental Unit of Life',
      'Tissues',
      'Diversity in Living Organisms',
      'Motion',
      'Force and Laws of Motion',
      'Gravitation',
      'Work and Energy',
      'Sound',
      'Why Do We Fall Ill',
      'Natural Resources',
      'Improvement in Food Resources'
    ],
    '10': [
      'Chemical Reactions and Equations',
      'Acids, Bases and Salts',
      'Metals and Non-metals',
      'Carbon and Its Compounds',
      'Periodic Classification of Elements',
      'Life Processes',
      'Control and Coordination',
      'How do Organisms Reproduce?',
      'Heredity and Evolution',
      'Light - Reflection and Refraction',
      'The Human Eye and the Colourful World',
      'Electricity',
      'Magnetic Effects of Electric Current',
      'Sources of Energy',
      'Our Environment',
      'Management of Natural Resources'
    ]
  },
  'English': {
    '6': ['First Flight', 'A Pact with the Sun'],
    '7': ['Honeycomb', 'An Alien Hand'],
    '8': ['Honeydew', 'It So Happened'],
    '9': ['Beehive', 'Moments'],
    '10': ['First Flight', 'Footprints Without Feet']
  },
  'Social Studies': {
    '6': [
      'The Earth in the Solar System',
      'Globe: Latitudes and Longitudes',
      'Motions of the Earth',
      'Maps',
      'Major Domains of the Earth',
      'Major Landforms of the Earth',
      'Our Country - India',
      'India: Climate, Vegetation and Wildlife',
      'Life in the Deserts',
      'Life in the Forests',
      'Life in the Grasslands',
      'Rocks and Soil',
      'Weather and Climate',
      'Water',
      'Air',
      'Human Environment Settlement, Transport and Communication',
      'Human Environment Interactions The Tropical and the Subtropical Region',
      'Life in the Temperate Grasslands',
      'Pollution',
      'Natural Disasters and Man-made Disasters'
    ],
    '7': [
      'Tracing Changes Through a Thousand Years',
      'New Kings and Kingdoms',
      'The Delhi Sultanate',
      'The Mughal Empire',
      'Rulers and Buildings',
      'Town, Traders and Craftsmen',
      'Tribal, Nomadic and Settled Communities',
      'Devotional Paths to the Divine',
      'The Making of Regional Cultures',
      'Eighteenth-Century Political Formations',
      'Environment',
      'Inside Our Earth',
      'Our Changing Earth',
      'Air',
      'Water',
      'Natural Vegetation and Wildlife',
      'Human Environment Settlement, Transport and Communication',
      'Human-Environment Interactions The Tropical and the Subtropical Region',
      'Life in the Temperate Grasslands',
      'Life in the Deserts'
    ],
    '8': [
      'How, When and Where',
      'From Trade to Territory',
      'Ruling the Countryside',
      'Tribal Societies',
      'Pastoralists in the Medieval World',
      'Bhakti and Sufi Traditions',
      'Changing Cultural Traditions',
      'The Markets are Buzzing',
      'The World of the Textiles',
      'Livelihood, Economies and Societies',
      'Resources',
      'Land, Soil, Water, Natural Vegetation and Wildlife Resources',
      'Mineral and Power Resources',
      'Industries',
      'Human Resources'
    ],
    '9': [
      'The French Revolution',
      'Socialism in Europe and the Russian Revolution',
      'Nazism and the Rise of Hitler',
      'Forest Society and Colonialism',
      'Pastoralists in the Modern World',
      'Peasants and Farmers',
      'History and Sport: The Story of Cricket',
      'Clothes: A Social History',
      'India and the Contemporary World I',
      'Geography: India - Size and Location',
      'Physical Features of India',
      'Drainage',
      'Climate',
      'Natural Vegetation and Wildlife',
      'Population'
    ],
    '10': [
      'The Rise of Nationalism in Europe',
      'The Nationalist Movement in Indo-China',
      'Nationalism in India',
      'Global Concern during the Cold War Period',
      'Towards Globalisation',
      'Resources and Development',
      'Forest and Wildlife Resources',
      'Water Resources',
      'Agriculture',
      'Minerals and Energy Resources',
      'Manufacturing Industries',
      'Lifelines of National Economy'
    ]
  }
};

// ==================== INSTANT CHAPTER LOADING ====================
function updateChaptersOnSubjectChange() {
  const subject = subjectSelect.value;
  const standard = standardSelect.value;

  if (!subject || !standard) {
    chapterSelect.innerHTML = '<option value="">Select subject and class first</option>';
    chapterSelect.disabled = true;
    return;
  }

  const chapters = chaptersDB[subject]?.[standard] || [];
  
  chapterSelect.innerHTML = '<option value="">All Chapters (Full Syllabus)</option>';
  
  if (chapters.length > 0) {
    chapters.forEach(chapter => {
      const option = document.createElement('option');
      option.value = chapter;
      option.textContent = chapter;
      chapterSelect.appendChild(option);
    });
    chapterSelect.disabled = false;
  } else {
    chapterSelect.innerHTML += '<option value="" disabled>No chapters available</option>';
    chapterSelect.disabled = true;
  }
}

// ==================== PAPER GENERATION ====================
async function handleGeneratePaper(e) {
  e.preventDefault();

  // Validate form
  const subject = subjectSelect.value;
  if (!subject) {
    showError('Please select a subject');
    return;
  }

  try {
    // Show loading state
    setLoadingState(true);
    hideMessages();

    // Collect form data
    const formData = {
      class: standardSelect.value,
      board: boardSelect.value,
      subject: subject,
      chapter: chapterSelect.value || undefined,
      marks: parseInt(marksSelect.value),
      difficulty: Array.from(difficultyRadios).find(r => r.checked)?.value || 'Medium',
      instructions: instructionsInput.value || undefined,
      user_name: userNameInput.value || undefined,
      school_name: schoolNameInput.value || undefined,
      include_key: includeKeyCheckbox.checked,
    };

    // Send request to API
    const response = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });

    const responseData = await response.json();

    if (!response.ok || !responseData.success) {
      throw new Error(responseData.error || 'Failed to generate paper');
    }

    // Process the response
    handleGenerationSuccess(responseData);
  } catch (error) {
    console.error('Generation error:', error);
    showError(error.message || 'Failed to generate the exam paper. Please try again.');
  } finally {
    setLoadingState(false);
  }
}

function handleGenerationSuccess(data) {
  let paperText = data.paper;
  let keyText = null;

  // Split answer key if it exists
  if (includeKeyCheckbox.checked) {
    const parts = paperText.split(/\nanswer\s+key[\s:]*/i);
    if (parts.length > 1) {
      paperText = parts[0].trim();
      keyText = parts[1].trim();
    }
  }

  // Store data
  currentPaper = paperText;
  currentKey = keyText;
  pdfData = data.pdf;

  // Display output
  outputEl.textContent = paperText;
  if (keyText) {
    keyEl.textContent = keyText;
    keySection.classList.remove('hidden');
  } else {
    keySection.classList.add('hidden');
  }

  // Show output sections
  outputSection.classList.remove('hidden');

  // Enable action buttons
  copyBtn.disabled = false;
  downloadBtn.disabled = false;

  // Show success message
  showSuccess('✅ Exam paper generated successfully!');

  // Auto-download PDF
  setTimeout(() => {
    downloadPDF();
  }, 800);
}

// ==================== CLIPBOARD ====================
function copyPaperToClipboard() {
  if (!currentPaper) return;

  navigator.clipboard.writeText(currentPaper)
    .then(() => {
      showSuccess('✅ Paper copied to clipboard!');
    })
    .catch(() => {
      showError('Failed to copy to clipboard');
    });
}

// ==================== PDF DOWNLOAD ====================
function downloadPDF() {
  if (!pdfData) {
    showError('No PDF available to download');
    return;
  }

  try {
    // Convert base64 to blob
    const binaryString = atob(pdfData);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    const blob = new Blob([bytes], { type: 'application/pdf' });

    // Create download link
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `exam_paper_${new Date().toISOString().slice(0, 10)}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

    showSuccess('✅ PDF downloaded successfully!');
  } catch (error) {
    console.error('Download error:', error);
    showError('Failed to download PDF. Please try again.');
  }
}

// ==================== UI HELPERS ====================
function setLoadingState(isLoading) {
  if (isLoading) {
    generateBtn.disabled = true;
    generateBtn.innerHTML = '<span class="btn-spinner spinner active"></span><span class="btn-text">Generating...</span>';
    loadingModal.classList.remove('hidden');
  } else {
    generateBtn.disabled = false;
    generateBtn.innerHTML = '<span class="btn-icon">🚀</span><span class="btn-text">Generate Paper</span>';
    loadingModal.classList.add('hidden');
  }
}

function showMessage(message, type) {
  hideMessages();

  if (!message) return;

  const box = type === 'error' ? errorBox : messageBox;
  box.textContent = message;
  box.classList.remove('hidden');

  // Auto-hide success messages after 5 seconds
  if (type === 'success') {
    setTimeout(hideMessages, 5000);
  }
}

function showSuccess(message) {
  showMessage(message, 'success');
}

function showError(message) {
  showMessage(message, 'error');
}

function hideMessages() {
  messageBox.classList.add('hidden');
  errorBox.classList.add('hidden');
}

// ==================== EXPORT FUNCTIONS ====================
window.copyPaperToClipboard = copyPaperToClipboard;
window.downloadPDF = downloadPDF;
