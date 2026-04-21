import { useRef } from "react";
import styles from "../constants/styles";
function Sidebar({ activeRecent, setActiveRecent, onFileSelect, recents = [], onNewChat }) {
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const f = e.target.files[0];
    if (f) onFileSelect(f);
  };

  return (
    <div style={styles.sidebar}>
      {/* Logo */}
      <div style={styles.sidebarLogo}>
        <div style={styles.logoIcon} />   {/* empty div, styled as a small sage dot */}
        <span style={styles.logoText}>Sage</span>
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

      {/* New Chat */}
        <button
          style={{
            ...styles.uploadBtn,
            marginBottom: "4px",
            color: "#7C9A7E",
            borderColor: "#2a3a2c",
            background: "transparent",
          }}
          onClick={() => {
            setActiveRecent(null);
            onNewChat();
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#1C2B1E";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <span>+</span> New chat
        </button>

      {/* Recents */}
      <div style={styles.sidebarSection}>Threads</div>
      {recents.map((r, i) => (
        <div
          key={i}
          style={{
            ...styles.recentItem,
            ...(activeRecent === i ? styles.recentItemActive : {}),
          }}
          onClick={() => setActiveRecent(i)}
          onMouseEnter={(e) => {
            if (activeRecent !== i) e.currentTarget.style.background = "#1d1e22";
          }}
          onMouseLeave={(e) => {
            if (activeRecent !== i) e.currentTarget.style.background = "transparent";
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