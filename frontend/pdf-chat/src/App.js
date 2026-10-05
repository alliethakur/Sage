import { useState, useEffect } from "react";
import styles from "./constants/styles";
import { uploadPDF, askQuestion, summarizePDF } from "./services/api";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import ChatArea from "./components/ChatArea";
import InputBar from "./components/InputBar";

const STORAGE_KEY = "sage_threads";

// Chats are saved in the browser (localStorage) so they survive a page refresh.
// Each thread remembers its doc_id, so the backend knows which document to search.
function loadThreads() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function App() {
  const [threads, setThreads] = useState(loadThreads);
  const [activeId, setActiveId] = useState(null);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadError, setUploadError] = useState(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
    } catch {
      // storage full or blocked: chats still work, they just won't survive a refresh
    }
  }, [threads]);

  const active = threads.find((t) => t.id === activeId) || null;
  const activeIndex = active ? threads.indexOf(active) : null;

  const updateThread = (id, change) =>
    setThreads((prev) => prev.map((t) => (t.id === id ? { ...t, ...change(t) } : t)));

  const handleFileSelect = async (selectedFile) => {
    setUploadError(null);
    setActiveId(null);
    setLoading(true);
    const uploadResult = await uploadPDF(selectedFile);
    if (uploadResult.error) {
      setUploadError(uploadResult.error);
      setLoading(false);
      return;
    }

    const id = uploadResult.doc_id;
    const thread = {
      id,
      docId: id,
      name: selectedFile.name,
      pages: uploadResult.pages,
      date: new Date().toLocaleDateString(undefined, { day: "numeric", month: "short" }),
      summary: null,
      messages: [
        { role: "assistant", text: `"${selectedFile.name}" loaded. Ask me anything.`, sources: [] },
      ],
    };
    setThreads((prev) => [thread, ...prev]);
    setActiveId(id);
    setLoading(false);

    const data = await summarizePDF(id);
    updateThread(id, () => ({ summary: data.summary || "Summary unavailable." }));
  };

  const handleAsk = async () => {
    if (!question.trim() || !active) return;
    const id = active.id; // remember which chat this question belongs to
    const userMsg = { role: "user", text: question, sources: [] };
    updateThread(id, (t) => ({ messages: [...t.messages, userMsg] }));
    setQuestion("");
    setLoading(true);

    const data = await askQuestion(userMsg.text, active.docId);
    const assistantMsg = {
      role: "assistant",
      text: data.answer || data.error || "Something went wrong.",
      sources: data.sources || [],
    };
    updateThread(id, (t) => ({ messages: [...t.messages, assistantMsg] }));
    setLoading(false);
  };

  const handleNewChat = () => {
    setActiveId(null);
    setQuestion("");
    setUploadError(null);
  };

  return (
    <div style={styles.root}>
      <Sidebar
        activeRecent={activeIndex}
        setActiveRecent={(i) => setActiveId(i === null ? null : threads[i]?.id ?? null)}
        uploadError={uploadError}
        onFileSelect={handleFileSelect}
        onNewChat={handleNewChat}
        recents={threads}
      />
      <div style={styles.main}>
        <TopBar
          uploaded={!!active}
          fileName={active?.name}
          pages={active?.pages}
          summary={active?.summary}
          staleName={null}
        />
        <ChatArea messages={active?.messages || []} loading={loading} />
        {active && (
          <InputBar
            question={question}
            setQuestion={setQuestion}
            onSend={handleAsk}
            loading={loading}
          />
        )}
      </div>
    </div>
  );
}

export default App;
