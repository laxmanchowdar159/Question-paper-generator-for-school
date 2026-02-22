// ============================================================
// EXAMCRAFT - AI QUESTION PAPER GENERATOR
// Modern, Improved JavaScript with Enhanced Functionality
// ============================================================

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

// ==================== CHAPTER LOADING ====================
async function updateChaptersOnSubjectChange() {
  const subject = subjectSelect.value;
  const standard = standardSelect.value;
  const board = boardSelect.value;

  if (!subject || !standard) {
    chapterSelect.innerHTML = '<option value="" disabled selected>Select subject and class first</option>';
    chapterSelect.disabled = true;
    return;
  }

  try {
    chapterSelect.innerHTML = '<option value="" disabled selected>Loading chapters...</option>';
    chapterSelect.disabled = true;

    const response = await fetch('/get-chapters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class: standard, subject, board }),
    });

    const data = await response.json();

    if (data.success && data.chapters.length > 0) {
      chapterSelect.innerHTML = '<option value="" disabled selected>Select a chapter</option>';
      data.chapters.forEach(chapter => {
        const option = document.createElement('option');
        option.value = chapter;
        option.textContent = chapter;
        chapterSelect.appendChild(option);
      });
      chapterSelect.disabled = false;
    } else {
      chapterSelect.innerHTML = '<option value="" disabled selected>No chapters available</option>';
      chapterSelect.disabled = true;
    }
  } catch (error) {
    console.error('Failed to load chapters:', error);
    chapterSelect.innerHTML = '<option value="" disabled selected>Error loading chapters</option>';
    chapterSelect.disabled = true;
    showError('Failed to load chapters. Please try again.');
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
