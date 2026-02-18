let pdfData = null;

async function generatePaper(){

generateBtn.innerText="Generating...";
generateBtn.disabled=true;

const res = await fetch("/generate",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify({

class:standard.value,
board:board.value,
subject:subject.value,
difficulty:difficulty.value,
marks:marks.value,
instructions:instructions.value

})

});

const data=await res.json();

output.innerText=data.paper;

pdfData=data.pdf;

generateBtn.innerText="Generate Paper";
generateBtn.disabled=false;

}

function downloadPDF(){

fetch("/download",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify({pdf:pdfData})

})
.then(res=>res.blob())
.then(blob=>{

const url=window.URL.createObjectURL(blob);

const a=document.createElement("a");

a.href=url;

a.download="question_paper.pdf";

a.click();

});

}

function copyPaper(){

navigator.clipboard.writeText(output.innerText);

alert("Copied");

}
