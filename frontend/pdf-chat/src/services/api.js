const BASE = "http://127.0.0.1:5000";

export async function uploadPDF(file) {
  const formData = new FormData();
  formData.append("file", file);
  await fetch(`${BASE}/upload`, {
    method: "POST",
    body: formData,
  });
}

export async function askQuestion(question) {
  const res = await fetch(`${BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  return res.json(); // { answer, sources }
}