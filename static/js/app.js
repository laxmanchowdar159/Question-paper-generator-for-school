
async function generate() {

    const data = {
        class: document.getElementById("class").value,
        subject: document.getElementById("subject").value,
        board: document.getElementById("board").value,
        marks: document.getElementById("marks").value,
        difficulty: document.getElementById("difficulty").value
    }

    const res = await fetch("/generate", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(data)
    })

    const result = await res.json()

    if(result.success)
        document.getElementById("output").value = result.paper
    else
        alert(result.error)
}
