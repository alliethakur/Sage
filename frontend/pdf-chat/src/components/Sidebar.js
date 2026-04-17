import { useRef } from "react";
import styles from "../constants/styles";

const RECENTS = [
  { name: "BEE654B-module-5.pdf", date: "Today" },
  { name: "NPTEL-ML-week3.pdf", date: "Yesterday" },
  { name: "DSA-notes-unit2.pdf", date: "2 days ago" },
];

function Sidebar({ activeRecent, setActiveRecent, onFileSelect }) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) onFileSelect(f);
  };

  return (
    <div style={styles.sidebar}>
      {/* Logo */}
      <div style={styles.sidebarLogo}>
        <div style={styles.logoIcon}>📄</div>
        <span style={styles.logoText}>DocuMind</span>
      </div>

      {/* Upload button */}
      <button
        style={styles.uploadBtn}
        onClick={() => fileInputRef.current?.click()}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "#282930";
          e.currentTarget.style.borderColor = "#3e3f48";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "#222428";
          e.currentTarget.style.borderColor = "#2e2f35";
        }}
      >
        <span>↑</span> Upload PDF
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        style={{ display: "none" }}
        onChange={handleFileChange}
      />

      {/* Recents */}
      <div style={styles.sidebarSection}>Recent</div>
      {RECENTS.map((r, i) => (
        <div
          key={i}
          style={{
            ...styles.recentItem,
            ...(activeRecent === i ? styles.recentItemActive : {}),
          }}
          onClick={() => setActiveRecent(i)}
          onMouseEnter={(e) => {
            if (activeRecent !== i)
              e.currentTarget.style.background = "#1d1e22";
          }}
          onMouseLeave={(e) => {
            if (activeRecent !== i)
              e.currentTarget.style.background = "transparent";
          }}
        >
          <div style={styles.recentName}>{r.name}</div>
          <div style={styles.recentDate}>{r.date}</div>
        </div>
      ))}
    </div>
  );
}

export default Sidebar;