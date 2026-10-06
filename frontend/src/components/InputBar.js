function InputBar({ question, setQuestion, onSend, loading }) {
  const handleKeyDown = (e) => {
    // Enter sends, Shift+Enter makes a new line
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="composer">
      <div className="input">
        <textarea
          rows={1}
          placeholder="Ask about this document…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button className="send" onClick={onSend} disabled={loading || !question.trim()} title="Send">
          ↑
        </button>
      </div>
      <div className="hint">Answers come only from your document. If it isn't there, Sage says so.</div>
    </div>
  );
}

export default InputBar;
