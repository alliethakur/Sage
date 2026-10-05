// Backend address. Set REACT_APP_API_URL when deploying; defaults to the local Flask server.
const BASE = process.env.REACT_APP_API_URL || "http://127.0.0.1:5000";

// Turn network failures into a normal { error } result instead of crashing the app
async function request(path, options) {
  try {
    const res = await fetch(`${BASE}${path}`, options);
    return await res.json();
  } catch {
    return { error: "Can't reach the Sage backend. Is it running?" };
  }
}

export async function uploadPDF(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/upload", { method: "POST", body: formData }); // { doc_id, pages } or { error }
}

export async function askQuestion(question, docId) {
  return request("/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, doc_id: docId }),
  }); // { answer, sources } or { error }
}

export async function summarizePDF(docId) {
  return request("/summarize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ doc_id: docId }),
  }); // { summary } or { error }
}
