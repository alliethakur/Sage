import { useState } from "react";
import styles from "./constants/styles";
import { uploadPDF, askQuestion } from "./services/api";
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

  const handleFileSelect = async (selectedFile) => {
    setFile(selectedFile);
    setLoading(true);
    await uploadPDF(selectedFile);
    setLoading(false);
    setUploaded(true);
    setMessages([
      {
        role: "assistant",
        text: `PDF loaded. This document is "${selectedFile.name}". Ask me anything.`,
        sources: [],
      },
    ]);
  };

  const handleAsk = async () => {
    if (!question.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: question, sources: [] }]);
    setQuestion("");
    setLoading(true);
    const data = await askQuestion(question);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: data.answer, sources: data.sources || [] },
    ]);
    setLoading(false);
  };

  return (
    <div style={styles.root}>
      <Sidebar
        activeRecent={activeRecent}
        setActiveRecent={setActiveRecent}
        onFileSelect={handleFileSelect}
      />
      <div style={styles.main}>
        <TopBar uploaded={uploaded} fileName={file?.name} />
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