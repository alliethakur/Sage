import { useRef, useEffect, useState } from "react";
import styles from "../constants/styles";

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      title="Copy response"
      style={{
        position: "absolute",
        top: "8px",
        right: "8px",
        background: "none",
        border: "none",
        cursor: "pointer",
        padding: "2px",
        borderRadius: "4px",
        color: copied ? "#7C9A7E" : "#3e3f49",
        fontSize: "11px",
        fontFamily: "inherit",
        lineHeight: 1,
        transition: "color 0.15s",
        display: "flex",
        alignItems: "center",
        gap: "3px",
      }}
    >
      {copied ? (
        "Copied! ✓"
      ) : (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
    </button>
  );
}

const LOADING_MESSAGES = [
  "Searching your document...",
  "Reading relevant pages...",
  "Generating answer...",
];

function LoadingIndicator() {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ ...styles.thinking, gap: "10px" }}>
      <div style={{ display: "flex", gap: "4px" }}>
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            style={{ ...styles.dot, animationDelay: `${i * 0.18}s` }}
          />
        ))}
      </div>
      <span style={{ fontSize: "12.5px", color: "#4a4b55" }}>
        {LOADING_MESSAGES[msgIndex]}
      </span>
      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function ChatArea({ messages, loading }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={styles.chatArea}>
      {messages.length === 0 && (
        <div style={styles.emptyState}>
          <div style={styles.emptyText}>Upload a PDF and start chatting with it</div>
        </div>
      )}

      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0);    }
        }
      `}</style>

      {messages.map((msg, i) => (
        <div key={i} style={{ ...styles.msgRow(msg.role), animation: "fadeSlideUp 300ms ease-out" }}>
          <div
            style={{
              ...styles.bubble(msg.role),
              ...(msg.role === "assistant" ? { position: "relative", paddingRight: "32px" } : {}),
            }}
          >
            {msg.role === "assistant" && <CopyButton text={msg.text} />}
            <p style={{ margin: 0 }}>{msg.text}</p>
            {msg.sources.length > 0 && (
              <div style={styles.sourceTag}>
                <span>□</span>
                {msg.sources.join(", ")}
              </div>
            )}
          </div>
        </div>
      ))}

      {loading && <LoadingIndicator />}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatArea;
