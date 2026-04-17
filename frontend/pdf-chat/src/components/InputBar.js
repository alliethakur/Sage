import styles from "../constants/styles";

function InputBar({ question, setQuestion, onSend, loading }) {
  const handleKeyPress = (e) => {
    if (e.key === "Enter") onSend();
  };

  return (
    <div style={styles.inputBar}>
      <input
        type="text"
        placeholder="Ask anything about your PDF..."
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyPress={handleKeyPress}
        style={styles.input}
        onFocus={(e) => (e.target.style.borderColor = "#5a4fcf")}
        onBlur={(e) => (e.target.style.borderColor = "#2a2b32")}
      />
      <button
        onClick={onSend}
        disabled={loading}
        style={{
          ...styles.sendBtn,
          opacity: loading ? 0.5 : 1,
        }}
        onMouseEnter={(e) => !loading && (e.currentTarget.style.transform = "scale(1.08)")}
        onMouseLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      </button>
    </div>
  );
}

export default InputBar;