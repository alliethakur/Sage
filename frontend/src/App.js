import { useState, useEffect, useRef } from "react";
import "./sage.css";
import { uploadPDF, askQuestion, summarizePDF, wakeBackend } from "./services/api";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import ChatArea from "./components/ChatArea";
import InputBar from "./components/InputBar";
import Welcome from "./components/Welcome";
import EvidencePanel from "./components/EvidencePanel";

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
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  // Which answer the Evidence panel shows, and which citation is highlighted
  const [selectedMsg, setSelectedMsg] = useState(null);
  const [activeCite, setActiveCite] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    wakeBackend(); // free hosting sleeps when idle; start waking it as soon as the page opens
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(threads));
    } catch {
      // storage full or blocked: chats still work, they just won't survive a refresh
    }
  }, [threads]);

  const active = threads.find((t) => t.id === activeId) || null;

  const updateThread = (id, change) =>
    setThreads((prev) => prev.map((t) => (t.id === id ? { ...t, ...change(t) } : t)));

  // Evidence panel follows the selected answer, or the latest answer by default
  const messages = active?.messages || [];
  const lastBotIndex = messages.map((m) => m.role).lastIndexOf("assistant");
  const shownIndex = selectedMsg ?? lastBotIndex;
  const shownMsg = shownIndex >= 0 ? messages[shownIndex] : null;

  const openChat = (id) => {
    setActiveId(id);
    setSelectedMsg(null);
    setActiveCite(null);
    setQuestion("");
  };

  const openFilePicker = () => fileInputRef.current?.click();

  const handleFile = async (file) => {
    if (!file) return;
    setUploadError(null);
    setUploading(true);
    const result = await uploadPDF(file);
    setUploading(false);
    if (result.error) {
      setUploadError(result.error);
      return;
    }

    const id = result.doc_id;
    const thread = {
      id,
      docId: id,
      name: file.name,
      kind: result.kind,
      stats: result.stats,
      pages: result.pages,
      chunks: result.chunks,
      date: new Date().toLocaleDateString(undefined, { day: "numeric", month: "short" }),
      summary: null,
      summaryShown: false, // typewriter effect only plays the first time
      messages: [
        { role: "assistant", text: `**${file.name}** is ready. Ask me anything about it.`, sources: [], evidence: [] },
      ],
    };
    setThreads((prev) => [thread, ...prev]);
    openChat(id);

    const data = await summarizePDF(id);
    updateThread(id, () => ({ summary: data.summary || "Summary unavailable." }));
  };

  const handleAsk = async () => {
    const text = question.trim();
    if (!text || !active || loading) return;
    const id = active.id; // remember which chat this question belongs to
    updateThread(id, (t) => ({ messages: [...t.messages, { role: "user", text }] }));
    setQuestion("");
    setSelectedMsg(null);
    setActiveCite(null);
    setLoading(true);

    const data = await askQuestion(text, active.docId);
    const answer = {
      role: "assistant",
      text: data.answer || data.error || "Something went wrong.",
      isError: !data.answer,
      query: text,
      route: data.route || null,
      sources: data.sources || [],
      evidence: data.evidence || [],
      table: data.table || null,
    };
    updateThread(id, (t) => ({ messages: [...t.messages, answer] }));
    setLoading(false);
  };

  const handleCite = (msgIndex, n) => {
    setSelectedMsg(msgIndex);
    setActiveCite(n);
  };

  const deleteChat = (id) => {
    setThreads((prev) => prev.filter((t) => t.id !== id));
    if (id === activeId) openChat(null);
  };

  return (
    <div className="app">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.md,.csv"
        hidden
        onChange={(e) => {
          handleFile(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <Sidebar
        threads={threads}
        activeId={activeId}
        onSelect={openChat}
        onNewChat={openFilePicker}
        onDelete={deleteChat}
        uploading={uploading}
        uploadError={uploadError}
      />
      <main className="chat">
        {active ? (
          <>
            <TopBar thread={active} />
            <ChatArea
              thread={active}
              loading={loading}
              shownIndex={shownIndex}
              activeCite={activeCite}
              onCite={handleCite}
              onSelectMessage={(i) => { setSelectedMsg(i); setActiveCite(null); }}
              onSummaryShown={() => updateThread(active.id, () => ({ summaryShown: true }))}
            />
            <InputBar question={question} setQuestion={setQuestion} onSend={handleAsk} loading={loading} />
          </>
        ) : (
          <Welcome onPick={openFilePicker} onDropFile={handleFile} uploading={uploading} />
        )}
      </main>
      <EvidencePanel
        hasDoc={!!active}
        message={shownMsg}
        activeCite={activeCite}
        onCite={(n) => handleCite(shownIndex, n)}
      />
    </div>
  );
}

export default App;
