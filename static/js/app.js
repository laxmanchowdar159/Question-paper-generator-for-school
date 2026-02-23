
// Lightweight frontend controller for the multi-step UI
document.addEventListener('DOMContentLoaded', () => {
    initUI();
});

function initUI() {
    // Navigation
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            const step = el.dataset.step;
            goToStep(step);
        });
    });

    document.getElementById('themeToggle').addEventListener('click', toggleTheme);

    // Tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.addEventListener('click', (e) => {
        const target = e.target.textContent.includes('Answer') ? 'answerKey' : 'paper';
        switchTab(target);
    }));

    // simple defaults
    if (!localStorage.getItem('theme')) localStorage.setItem('theme', 'light');
    applyTheme();
}

function goToStep(step) {
    document.querySelectorAll('.step-section').forEach(s => s.classList.remove('active'));
    const map = {
        identity: 'identity-step',
        curriculum: 'curriculum-step',
        'paper-config': 'paper-config-step',
        output: 'output-step'
    };
    const id = map[step];
    if (id) document.getElementById(id).classList.add('active');
}

function switchTab(name) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    if (name === 'paper') {
        document.querySelector('.tab-btn').classList.add('active');
        document.getElementById('paper-tab').classList.add('active');
    } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('answerKey-tab').classList.add('active');
    }
}

function toggleTheme() {
    const current = localStorage.getItem('theme') || 'light';
    localStorage.setItem('theme', current === 'light' ? 'dark' : 'light');
    applyTheme();
}

function applyTheme() {
    const theme = localStorage.getItem('theme') || 'light';
    if (theme === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
}

// Comprehensive Curriculum database (CBSE/AP Board aligned)
// Classes 6-10 with extensive subject options
const curriculum = {
    "10": {
        "Maths": [
            "Real Numbers",
            "Polynomials",
            "Pair of Linear Equations in Two Variables",
            "Quadratic Equations",
            "Arithmetic Progressions",
            "Triangles",
            "Coordinate Geometry",
            "Introduction to Trigonometry",
            "Some Applications of Trigonometry",
            "Circles",
            "Constructions",
            "Areas Related to Circles",
            "Surface Areas and Volumes",
            "Statistics",
            "Probability"
        ],
        "Science": [
            "Chemical Reactions and Equations",
            "Acids, Bases, and Salts",
            "Metals and Non-Metals",
            "Carbon and Its Compounds",
            "Periodic Classification of Elements",
            "Life Processes",
            "Control and Coordination",
            "How do Organisms Reproduce?",
            "Heredity and Evolution",
            "Light – Reflection and Refraction",
            "The Human Eye and the Colourful World",
            "Electricity",
            "Magnetic Effects of Electric Current",
            "Sources of Energy"
        ],
        "Social": [
            "Nationalism in India",
            "The Making of a Global World",
            "The Age of Industrialization",
            "Print Culture and the Modern World",
            "Resources and Development",
            "Forest and Wildlife Resources",
            "Water Resources",
            "Agriculture",
            "Minerals and Energy Resources",
            "Manufacturing Industries",
            "Lifelines of National Economy",
            "Power Sharing",
            "Federalism",
            "Democracy and Diversity",
            "Gender, Religion and Caste",
            "Popular Struggles and Movements",
            "Political Parties",
            "Outcomes of Democracy",
            "Challenges to Democracy"
        ],
        "English": [
            "A Letter to God",
            "Nelson Mandela: Long Walk to Freedom",
            "Two Stories about Flying",
            "From the Diary of Anne Frank",
            "Glimpses of India",
            "Mijbil the Otter",
            "Madam Rides the Bus",
            "The Hundred Dresses",
            "The Hundred Dresses – II",
            "A Baker from Goa",
            "Amanda",
            "Animals",
            "The Trees",
            "Fog",
            "The Tale of Custard the Dragon",
            "The Ball Poem",
            "The Invisible Man",
            "The Treasure within",
            "Footprints without Feet",
            "The Magic Drum and Other Favourite Stories",
            "The Necklace",
            "The Hack Driver",
            "Bholi",
            "The Book that Saved the Earth"
        ]
    },
    "9": {
        "Maths": [
            "Number Systems",
            "Polynomials",
            "Coordinate Geometry",
            "Linear Equations in Two Variables",
            "Introduction to Euclid's Geometry",
            "Lines and Angles",
            "Triangles",
            "Quadrilaterals",
            "Areas of Parallelograms and Triangles",
            "Circles",
            "Constructions",
            "Surface Areas and Volumes",
            "Statistics",
            "Probability"
        ],
        "Science": [
            "Matter - Its Nature and Behaviour",
            "Is Matter Around Us Pure?",
            "Atoms and Molecules",
            "Structure of the Atom",
            "The Fundamental Unit of Life",
            "Tissues",
            "Diversity in Living Organisms",
            "Motion",
            "Force and Laws of Motion",
            "Gravitation",
            "Work and Energy",
            "Sound",
            "Why do we Fall Ill?"
        ],
        "Social": [
            "The French Revolution",
            "Socialism in Europe and the Russian Revolution",
            "Nationalism in India",
            "India and the Contemporary World",
            "The British Raj",
            "Colonialism and the Countryside",
            "India – Size and Location",
            "Physical Features of India",
            "Drainage",
            "Climate",
            "Natural Vegetation",
            "Population",
            "What is Democracy?",
            "Electoral Politics",
            "Working of Institutions",
            "People as Resource",
            "Poverty as a Challenge",
            "Food Security"
        ],
        "English": [
            "The Fun They Had",
            "The Sound of Music",
            "Iswaran the Storyteller",
            "In the Kingdom of Fools",
            "The Happy Prince",
            "Reach for the Top",
            "The Bond of Love",
            "Kathmandu",
            "If I Were You",
            "The Snake and the Mirror",
            "My Childhood",
            "The Little Girl"
        ]
    },
    "8": {
        "Maths": [
            "Rational Numbers",
            "Powers",
            "Exponents and Radicals",
            "Algebraic Expressions and Identities",
            "Factorisation",
            "Division of Algebraic Expressions",
            "Linear Equations in One Variable",
            "Understanding Quadrilaterals",
            "Practical Geometry",
            "Visualizing Solid Shapes",
            "Mensuration",
            "Data Handling",
            "Graphs"
        ],
        "Science": [
            "Crop Production and Management",
            "Microorganisms",
            "Synthetic Fibres and Plastics",
            "Materials: Metals and Non-Metals",
            "Coal and Petroleum",
            "Combustion and Flame",
            "Conservation of Plants and Animals",
            "Cell – Structure and Functions",
            "Reproduction in Animals",
            "Force and Pressure",
            "Friction",
            "Sound",
            "Chemical Effects of Electric Current",
            "Light",
            "Stars and the Solar System"
        ],
        "Social": [
            "How, When and Where",
            "From Trade to Territory",
            "Ruling the Countryside",
            "Tribals, Dikus and the Vision of a United India",
            "When People Rebel",
            "Colonialism and the City",
            "India – Size and Location",
            "Resources",
            "Mineral and Power Resources",
            "Industries",
            "Human Resources",
            "The Constitution",
            "Understanding Secularism",
            "Why do we need a Parliament?",
            "Understanding Laws",
            "Markets Around Us"
        ],
        "English": [
            "The Best Christmas Present in the World",
            "The Tsunami",
            "Glimpses of India",
            "How the Camel got his Hump",
            "Children at Work",
            "The Selfish Giant",
            "The Value of Discipline",
            "Macavity: The Mystery Cat",
            "The Rebel",
            "A Slap in the Face"
        ]
    },
    "7": {
        "Maths": [
            "Integers",
            "Fractions and Decimals",
            "Data Handling",
            "Simple Equations",
            "Lines and Angles",
            "Triangle and its Properties",
            "Congruence of Triangles",
            "Comparing Quantities",
            "Rational Numbers",
            "Practical Geometry",
            "Perimeter and Area",
            "Algebraic Expressions"
        ],
        "Science": [
            "All Living Things",
            "Nutrition in Animals",
            "Nutrition in Plants",
            "Respiration in Organisms",
            "Transportation of Animals and Plants",
            "Reproduction in Plants",
            "Getting to Know Plants",
            "Body Movements",
            "The Nervous System",
            "Health and Hygiene",
            "Acid Bases and Salts",
            "Physical and Chemical Changes",
            "Weather, Climate and Adaptations",
            "Heat",
            "Light",
            "Electricity and Its Effects",
            "Wind, Storms and Cyclones"
        ],
        "Social": [
            "Tracing Changes Through a Thousand Years",
            "New Kings and Kingdoms",
            "The Delhi Sultans",
            "The Mughal Empire",
            "Rulers and Buildings",
            "Towns, Traders and Craftsmen",
            "Tribes, Nomads and Settled Communities",
            "Devotional Paths to the Divine",
            "The Making of Regional Cultures",
            "Eighteenth-Century Political Formations",
            "Environment",
            "Inside Our Earth",
            "Our Changing Earth",
            "Air",
            "Water",
            "Natural Vegetation and Wildlife",
            "Human Environment - Settlement, Transport and Communication",
            "On Equality",
            "The Role of Government in Health"
        ],
        "English": [
            "The Ants and the Grasshopper",
            "The Tale of Custard the Dragon",
            "The Three Little Pigs",
            "The Giving Tree",
            "The Lamplighter",
            "An Alien Hand",
            "The Open Road",
            "The Squirrel",
            "The Cats and Kittens",
            "A Little Girl's Prayer"
        ]
    },
    "6": {
        "Maths": [
            "Knowing Our Numbers",
            "Whole Numbers",
            "Playing with Numbers",
            "Basic Geometrical Ideas",
            "Understanding Elementary Shapes",
            "Integers",
            "Fractions",
            "Decimals",
            "Data Handling",
            "Mensuration",
            "Algebra",
            "Ratio and Proportion"
        ],
        "Science": [
            "Food: Where Does It Come From?",
            "Components of Food",
            "Fibre to Fabric",
            "Sorting Materials into Groups",
            "Separation of Substances",
            "Changes Around Us",
            "Getting to Know Plants",
            "Plant Parts and Their Functions",
            "Getting to Know Animals",
            "Habitats of Animals",
            "The Living Organisms and their Surroundings",
            "Body Movements",
            "Health and Hygiene",
            "Electricity and Circuits"
        ],
        "Social": [
            "What, Where, How and When?",
            "On the Trail of the Earliest People",
            "From Gathering to Growing Food",
            "In the Earliest Cities",
            "What Books and Burials Tell Us",
            "The Kingdoms, Kings and an Early Republic",
            "New Questions and Ideas",
            "The Earth: Our Habitat",
            "Globe: Latitudes and Longitudes",
            "Motions of the Earth",
            "Maps",
            "Major Domains of the Earth",
            "Major Landforms of the Earth",
            "Our Country – India",
            "Understanding Diversity",
            "On Equality",
            "The Basic Structure of the Constitution"
        ],
        "English": [
            "A Tale of Two Birds",
            "The Lion and the Mouse",
            "Three Little Pigs",
            "From a Railway Carriage",
            "The Quarrel",
            "Beauty",
            "Where Do All the Teachers Go?",
            "The Rebel",
            "Where the Wild Things Are",
            "The Tiny Teacher",
            "Sunita in the Sky",
            "The Wonder Called Sleep"
        ]
    }
};

function updateSubjectsForClass() {
    const classSel = document.getElementById('class').value;
    const subjectSelect = document.getElementById('subject');
    subjectSelect.innerHTML = '<option value="" disabled selected>Select a subject</option>';
    // try server-side chapters first, then fall back to local curriculum
    fetchChaptersFromServer(classSel).then(serverData => {
        const subjects = serverData ? Object.keys(serverData) : (curriculum[classSel] ? Object.keys(curriculum[classSel]) : []);
        subjects.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            subjectSelect.appendChild(opt);
        });
        // reset chapter
        const chapterSelect = document.getElementById('chapter');
        chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
        chapterSelect.disabled = true;
        // enable subject selector only when subjects are available
        subjectSelect.disabled = subjects.length === 0;
    }).catch(() => {
        const subjects = curriculum[classSel] ? Object.keys(curriculum[classSel]) : [];
        subjects.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s;
            opt.textContent = s;
            subjectSelect.appendChild(opt);
        });
        const chapterSelect = document.getElementById('chapter');
        chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
        chapterSelect.disabled = true;
        subjectSelect.disabled = subjects.length === 0;
    });
}

function updateChapters() {
    const classVal = document.getElementById('class').value;
    const subject = document.getElementById('subject').value;
    const chapterSelect = document.getElementById('chapter');
    chapterSelect.innerHTML = '<option value="" disabled selected>Choose a chapter...</option>';
    // try server data first
    fetchChaptersFromServer(classVal).then(serverData => {
        const list = serverData && serverData[subject] ? serverData[subject] : (curriculum[classVal] && curriculum[classVal][subject] ? curriculum[classVal][subject] : []);
        if (list && list.length) {
            list.forEach(chap => {
                const option = document.createElement('option');
                option.value = chap;
                option.textContent = chap;
                chapterSelect.appendChild(option);
            });
            chapterSelect.disabled = false;
            chapterSelect.focus();
        } else {
            chapterSelect.disabled = true;
        }
    }).catch(() => {
        const list = curriculum[classVal] && curriculum[classVal][subject] ? curriculum[classVal][subject] : [];
        if (list && list.length) {
            list.forEach(chap => {
                const option = document.createElement('option');
                option.value = chap;
                option.textContent = chap;
                chapterSelect.appendChild(option);
            });
            chapterSelect.disabled = false;
            chapterSelect.focus();
        } else {
            chapterSelect.disabled = true;
        }
    });
}

// Global cache for preview paper/key so PDF gen can reuse without second API hit
let previewCache = null;
let currentExamType = null;

// Wire subject -> chapter updates and form submission
document.addEventListener('DOMContentLoaded', () => {
    const examTypeSelect = document.getElementById('examType');
    const subjectSelect = document.getElementById('subject');
    const classSelect = document.getElementById('class');
    const marksSelect = document.getElementById('totalMarks');
    const marksCustom = document.getElementById('totalMarksCustom');
    const includeSolutionsCheckbox = document.getElementById('includeSolutions');
    
    // Handle exam type selection
    if (examTypeSelect) {
        examTypeSelect.addEventListener('change', (e) => {
            currentExamType = e.target.value;
            const subjectCard = document.getElementById('subjectCard');
            const chapterCard = document.getElementById('chapterCard');
            const subjectField = document.getElementById('subject');
            const chapterField = document.getElementById('chapter');
            
            if (currentExamType === 'state-board') {
                // Show subject and chapter for State Board
                subjectCard.style.display = '';
                chapterCard.style.display = '';
                subjectField.setAttribute('required', 'required');
                chapterField.setAttribute('required', 'required');
                examTypeSelect.classList.remove('disabled-field');
            } else if (currentExamType === 'competitive') {
                // Hide subject and chapter for Competitive Exams
                subjectCard.style.display = 'none';
                chapterCard.style.display = 'none';
                subjectField.removeAttribute('required');
                chapterField.removeAttribute('required');
                subjectField.value = '';
                chapterField.value = '';
                examTypeSelect.classList.add('disabled-field');
            }
            
            previewCache = null;
            clearFieldErrors();
        });
    }
    
    if (subjectSelect) subjectSelect.addEventListener('change', updateChapters);
    
    // Handle primary class selection
    if (classSelect) {
        // If no class selected, default to first available class so users immediately see subjects
        if (!classSelect.value) {
            const firstOpt = classSelect.querySelector('option:not([disabled])');
            if (firstOpt) classSelect.value = firstOpt.value;
        }

        classSelect.addEventListener('change', () => {
            updateSubjectsForClass();
            previewCache = null;
            setTimeout(() => document.getElementById('subject')?.focus(), 50);
        });
        // populate subjects for initial class
        updateSubjectsForClass();
    }

    // Marks preset/select handler: show custom input when 'other' selected
    if (marksSelect) {
        marksSelect.addEventListener('change', (e) => {
            if (e.target.value === 'other') {
                marksCustom.style.display = '';
                marksCustom.focus();
            } else {
                marksCustom.style.display = 'none';
                marksCustom.value = '';
            }
        });
    }

    const form = document.getElementById('paperForm');
    const button = document.getElementById('generateBtn');
    const modal = document.getElementById('loadingModal');
    const errorBox = document.getElementById('errorMessage');

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            errorBox.style.display = 'none';
            clearFieldErrors();
            if (!validateForm()) {
                showToast('Please fill in all required fields');
                return;
            }

            // if preview cache exists (user clicked preview first), reuse it
            if (previewCache) {
                try {
                    if (modal) { modal.setAttribute('aria-hidden', 'false'); modal.style.display = 'flex'; }
                    if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }

                    const subject = document.getElementById('subject').value;
                    const chapter = document.getElementById('chapter').value;
                    const paperText = previewCache.paper + '\n\n' + (previewCache.answer_key || '');

                    // Create PDF server-side by sending full text
                    const pdfRes = await fetch('/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            paper: paperText,
                            subject: subject,
                            chapter: chapter,
                            pdf_only: true
                        })
                    });

                    if (pdfRes.ok) {
                        const contentType = pdfRes.headers.get('Content-Type') || '';
                        if (contentType.includes('application/pdf')) {
                            const blob = await pdfRes.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            const disposition = pdfRes.headers.get('Content-Disposition') || '';
                            let filename = 'model_paper.pdf';
                            const m = disposition.match(/filename *= *"?([^";]+)"?/);
                            if (m) filename = m[1].replace(/['"]/g, '');
                            a.href = url;
                            a.download = filename;
                            document.body.appendChild(a);
                            a.click();
                            a.remove();
                            window.URL.revokeObjectURL(url);
                            showToast('📥 PDF downloaded from cache!');
                        }
                    }
                } catch (err) {
                    showToast('Error downloading cached PDF, generating fresh...');
                    previewCache = null;  // fallback to full generation
                } finally {
                    if (modal) { modal.setAttribute('aria-hidden', 'true'); modal.style.display = 'none'; }
                    if (button) { button.disabled = false; button.setAttribute('aria-busy', 'false'); }
                }
                return;
            }

            // No cache: full generation
            if (modal) { modal.setAttribute('aria-hidden', 'false'); modal.style.display = 'flex'; }
            if (button) { button.disabled = true; button.setAttribute('aria-busy', 'true'); }

            try {
                const formData = new FormData(form);
                const response = await fetch('/generate', { method: 'POST', body: formData });

                const contentType = response.headers.get('Content-Type') || '';
                if (contentType.includes('application/pdf')) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    const disposition = response.headers.get('Content-Disposition') || '';
                    let filename = 'model_paper.pdf';
                    const m = disposition.match(/filename *= *"?([^";]+)"?/);
                    if (m) filename = m[1].replace(/['"]/g, '');
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                    showToast('✨ PDF downloaded!');
                } else {
                    const text = await response.text();
                    try {
                        const json = JSON.parse(text);
                        if (json.success && json.paper) {
                            showToast('Paper generated — check the preview section');
                        } else {
                            errorBox.textContent = json.error || 'Generation failed';
                            errorBox.style.display = 'block';
                        }
                    } catch (err) {
                        errorBox.textContent = 'Unexpected response format';
                        errorBox.style.display = 'block';
                    }
                }
            } catch (err) {
                errorBox.textContent = err.message || 'Network error';
                errorBox.style.display = 'block';
            } finally {
                if (modal) { modal.setAttribute('aria-hidden', 'true'); modal.style.display = 'none'; }
                if (button) { button.disabled = false; button.setAttribute('aria-busy', 'false'); }
            }
        });
    }

    // Preview button -> use JSON API to get paper text and show in preview pane, cache for PDF gen
    const previewBtn = document.getElementById('previewBtn');
    if (previewBtn) previewBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        clearFieldErrors();
        const valid = validateForm();
        if (!valid) return showToast('Please fix highlighted fields first');
        // collect payload
        const selectedMarks = marksSelect?.value || document.getElementById('totalMarks')?.value || '100';
        const marksValue = selectedMarks === 'other' ? (marksCustom?.value || '100') : selectedMarks;
        const payload = {
            class: document.getElementById('class').value,
            subject: document.getElementById('subject').value,
            chapter: document.getElementById('chapter').value,
            difficulty: Array.from(document.getElementsByName('difficulty')).find(r => r.checked)?.value || 'Medium',
            suggestions: document.getElementById('suggestions').value || '',
            marks: marksValue,
            includeSolutions: includeSolutionsCheckbox?.checked ? '1' : ''
        };
        const previewPane = document.getElementById('previewPane');
        previewPane.textContent = 'Generating preview...';
        try {
            const res = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const json = await res.json();
            if (!json.success) {
                previewPane.innerHTML = `<div class="error-inline">${escapeHtml(json.error || 'Generation failed')}</div>`;
                showToast('There was a hiccup generating the preview — see note above.');
                previewCache = null;
                return;
            }
            // Cache the paper and answer key for PDF generation
            previewCache = {
                paper: json.paper || '',
                answer_key: json.answer_key || ''
            };
            const paperText = json.paper || '';
            // render formatted preview (basic)
            previewPane.innerHTML = `<pre class="preview-text">${escapeHtml(paperText)}</pre>`;
                    // If user requested solutions, show a View Solutions button that stores the content server-side
                    const existingBtn = document.getElementById('viewSolutionsBtn');
                    if (existingBtn) existingBtn.remove();
                    if (includeSolutionsCheckbox && includeSolutionsCheckbox.checked) {
                        const btn = document.createElement('button');
                        btn.id = 'viewSolutionsBtn';
                        btn.className = 'btn btn-action';
                        btn.textContent = '🔍 View Solutions';
                        btn.style.marginTop = '12px';
                        btn.addEventListener('click', async () => {
                            try {
                                const res = await fetch('/store_solution', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ paper: previewCache.paper, answer_key: previewCache.answer_key })
                                });
                                const json = await res.json();
                                if (json.success && json.url) {
                                    window.open(json.url, '_blank');
                                } else {
                                    showToast('Could not store solutions server-side');
                                }
                            } catch (err) {
                                showToast('Network error storing solutions');
                            }
                        });
                        previewPane.appendChild(btn);
                    }
            showToast('✅ Preview ready! Click "Generate & Download" to create PDF.');
        } catch (err) {
            previewPane.innerHTML = `<div class="error-inline">${escapeHtml(err.message || 'Network error')}</div>`;
            previewCache = null;
        }
    });
});

async function generatePaper() {
    const payload = {
        class: document.getElementById('class').value,
        subject: document.getElementById('subject').value,
        board: document.getElementById('board').value || document.getElementById('board')?.value,
        marks: document.getElementById('totalMarks').value,
        difficulty: document.getElementById('difficulty').value
    };

    document.getElementById('loadingSpinner').classList.remove('hidden');

    try {
        const res = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        document.getElementById('loadingSpinner').classList.add('hidden');
        if (!result.success) return showToast(result.error || 'Generation failed');

        const paperText = result.paper || '';
        // try split answer key if present
        const splitIndex = paperText.toLowerCase().indexOf('answer key');
        if (splitIndex !== -1) {
            document.getElementById('paperOutput').textContent = paperText.slice(0, splitIndex);
            document.getElementById('answerKeyOutput').textContent = paperText.slice(splitIndex);
        } else {
            document.getElementById('paperOutput').textContent = paperText;
            document.getElementById('answerKeyOutput').textContent = '';
        }

        goToStep('output');
    } catch (err) {
        document.getElementById('loadingSpinner').classList.add('hidden');
        showToast(err.message || 'Network error');
    }
}

function showToast(msg) {
    const t = document.getElementById('notificationToast');
    // small friendly variations
    const variants = ['Nice!', 'All set!', 'Heads up!', 'Ta-da!'];
    const prefix = variants[Math.floor(Math.random() * variants.length)];
    t.textContent = `${prefix} — ${msg}`;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 4200);
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Open a new window and render the paper + solutions in a printable format
function openSolutionsWindow(cache) {
        const paper = cache?.paper || '';
        const answers = cache?.answer_key || '';
        const win = window.open('', '_blank');
        if (!win) return showToast('Popup blocked: allow popups for this site to view solutions');
        const html = `
            <!doctype html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Solutions — ExamCraft</title>
                <meta name="viewport" content="width=device-width,initial-scale=1">
                <style>
                    body{font-family:Inter, Sora, Arial, sans-serif;padding:28px;color:#1f2937}
                    h1{background:linear-gradient(90deg,#6366f1,#ec4899);-webkit-background-clip:text;color:transparent}
                    pre{white-space:pre-wrap;font-family:inherit;font-size:15px;line-height:1.6;background:#f8fafc;padding:18px;border-radius:10px;border:1px solid #e6eef9}
                    .answers{margin-top:20px;padding:18px;background:#fff9f2;border-radius:10px;border:1px solid #fde3bf}
                </style>
            </head>
            <body>
                <h1>ExamCraft — Paper & Solutions</h1>
                <section>
                    <h2>Paper</h2>
                    <pre>${escapeHtml(paper)}</pre>
                </section>
                <section class="answers">
                    <h2>Solutions & Explanations</h2>
                    <pre>${escapeHtml(answers || 'No solutions were returned with this preview.')}</pre>
                </section>
                <p style="margin-top:18px;color:#6b7280">Tip: Print this page or save as PDF from your browser.</p>
            </body>
            </html>
        `;
        win.document.open();
        win.document.write(html);
        win.document.close();
}

// Try to fetch chapters from server endpoint and fall back to local curriculum
async function fetchChaptersFromServer(classVal) {
    try {
        const res = await fetch(`/chapters?class=${encodeURIComponent(classVal)}`);
        const json = await res.json();
        if (json && json.success && json.data) return json.data;
    } catch (err) {
        // ignore
    }
    return null;
}

// --- Validation helpers ---
function showFieldError(fieldId, msg) {
    const el = document.getElementById(fieldId + 'Error');
    if (el) { el.textContent = msg; el.style.display = 'block'; }
    const field = document.getElementById(fieldId);
    if (field) field.classList.add('field-error');
}

function clearFieldErrors() {
    document.querySelectorAll('.error-inline').forEach(e => { e.textContent = ''; e.style.display = 'none'; });
    document.querySelectorAll('select, input').forEach(e => e.classList.remove('field-error'));
}

function validateForm() {
    clearFieldErrors();
    let ok = true;
    
    const examType = document.getElementById('examType').value;
    const cls = document.getElementById('class').value;
    
    if (!examType) { showFieldError('examType', 'Please select a paper type'); ok = false; }
    if (!cls) { showFieldError('class', 'Please select a class'); ok = false; }
    
    // Only validate subject/chapter for state board
    if (examType === 'state-board') {
        const subj = document.getElementById('subject').value;
        const chap = document.getElementById('chapter').value;
        if (!subj) { showFieldError('subject', 'Please select a subject'); ok = false; }
        if (!chap) { showFieldError('chapter', 'Please select a chapter'); ok = false; }
    }
    
    return ok;
}

function copyToClipboard() {
    const text = document.getElementById('paperOutput').textContent;
    navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard'));
}

function downloadPDF() {
    // For now just download plain text as .txt — PDF generation handled server-side.
    const text = document.getElementById('paperOutput').textContent || '';
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'question-paper.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}
