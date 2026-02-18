function getSubjects(){
return [...document.querySelectorAll('input[type=checkbox]:checked')].map(x => x.value);
}

async function generate(){

output.innerText = "Generating...";

const res = await fetch("/api/generate-paper", {

method: "POST",

headers: {"Content-Type": "application/json"},

body: JSON.stringify({
subjects: getSubjects(),
class: document.getElementById("class").value,
board: document.getElementById("board").value,
marks: document.getElementById("marks").value,
difficulty: document.getElementById("difficulty").value,
instructions: document.getElementById("instructions").value
})

});

const data = await res.json();

output.innerText = data.paper;

loadHistory();
}

function downloadPDF(){
window.location = "/api/download-pdf";
}

function downloadWord(){
window.location = "/api/download-word";
}

async function loadHistory(){

const res = await fetch("/api/history");
const history = await res.json();

let html = "";

history.forEach(item => {
html += `<div>${item.class} - ${item.subjects.join(", ")}</div>`;
});

document.getElementById("history").innerHTML = html;
}

loadHistory();
