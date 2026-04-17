import { useRef, useEffect } from "react";
import styles from "../constants/styles";

function ThinkingDots() {
  return (
    <div style={styles.thinking}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            ...styles.dot,
            animationDelay: `${i * 0.18}s`,
          }}
        />
      ))}
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
          <div style={styles.emptyIcon}>📚</div>
          <div style={styles.emptyText}>Upload a PDF and start chatting with it</div>
        </div>
      )}

      {messages.map((msg, i) => (
        <div key={i} style={styles.msgRow(msg.role)}>
          <div style={styles.bubble(msg.role)}>
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

      {loading && <ThinkingDots />}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatArea;