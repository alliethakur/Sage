import { useState } from "react";

// Empty screen: drop a PDF anywhere on it, or click to browse
function Welcome({ onPick, onDropFile, uploading }) {
  const [over, setOver] = useState(false);

  const onDrop = (e) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onDropFile(file);
  };

  return (
    <div
      className="welcome"
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <div className={`dropzone ${over ? "over" : ""}`} onClick={uploading ? undefined : onPick}>
        <div className="icon">{uploading ? "…" : "↑"}</div>
        <h2>{uploading ? "Reading your document…" : "Chat with a document"}</h2>
        <p>{uploading ? "Splitting it into chunks and building the search index." : "Drop a PDF, TXT, CSV or Excel file here, or click to browse."}</p>
        <div className="features">
          <span className="pill">Cites the exact chunk</span>
          <span className="pill">Says so when it doesn't know</span>
          <span className="pill">Keyword + meaning search</span>
        </div>
      </div>
    </div>
  );
}

export default Welcome;
