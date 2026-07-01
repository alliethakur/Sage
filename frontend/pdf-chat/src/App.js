import { useState } from "react";
import styles from "./constants/styles";
import { uploadPDF, askQuestion, summarizePDF } from "./services/api";
import Sidebar from "./components/Sidebar";
import TopBar from "./components/TopBar";
import ChatArea from "./components/ChatArea";
import InputBar from "./components/InputBar";

function App() {
  const [file, setFile] = useState(null);
  const [uploaded, setUploaded] = useState(false);
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [activeRecent, setActiveRecent] = useState(null);
  const [threads, setThreads] = useState([]);
  const [summary, setSummary] = useState(null);
  const [uploadError, setUploadError] = useState(null);


  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setLoading(true);
    const uploadResult = await uploadPDF(selectedFile);
    if (uploadResult.error) {
      setUploadError(uploadResult.error);
      setLoading(false);
      return;
    }
    setUploaded(true);
    const data = await summarizePDF();
    setSummary(data.summary || null);
    setLoading(false);
    const initMsg = {
      role: "assistant",
      text: `"${selectedFile.name}" loaded. Ask me anything.`,
      sources: [],
    };
    setMessages([initMsg]);
    setThreads((prev) => [
      { name: selectedFile.name, date: "Today", messages: [initMsg] },
      ...prev,
    ]);
    setActiveRecent(0);
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    const userMsg = { role: "user", text: question, sources: [] };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setLoading(true);
    const data = await askQuestion(question);
    console.log(data);
    const assistantMsg = { role: "assistant", text: data.answer, sources: data.sources || [] };
    setMessages((prev) => [...prev, assistantMsg]);
    setThreads((prev) =>
      prev.map((t, i) =>
        i === activeRecent
          ? { ...t, messages: [...t.messages, userMsg, assistantMsg] }
          : t
      )
    );
    setLoading(false);
  };
   const handleNewChat = () => {
    setFile(null);
    setUploaded(false);
    setMessages([]);
    setActiveRecent(null);
    setSummary(null);
    setUploadError(null);
  };

  return (
    <div style={styles.root}>
      <Sidebar
        activeRecent={activeRecent}
        setActiveRecent={(i) => {
           setActiveRecent(i);
           if (i !== null && threads[i]) setMessages(threads[i].messages);
         }}
        uploadError={uploadError}
        onFileSelect={handleFileSelect}
        onNewChat={handleNewChat}
        recents={threads}
      />
      <div style={styles.main}>
        <TopBar uploaded={uploaded} fileName={file?.name} summary={summary} />
        <ChatArea messages={messages} loading={loading} />
        {uploaded && (
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