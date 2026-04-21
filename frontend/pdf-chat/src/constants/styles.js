const styles = {
  root: {
    display: "flex",
    height: "100vh",
    background: "#111210",
    fontFamily: "'DM Sans', 'Segoe UI', sans-serif",
    color: "#e8e8ea",
    overflow: "hidden",
  },

  // ── Sidebar ──────────────────────────────────────────
  sidebar: {
    width: "260px",
    minWidth: "260px",
    background: "#18191c",
    borderRight: "1px solid #2a2b2f",
    display: "flex",
    flexDirection: "column",
    padding: "20px 14px",
    gap: "8px",
  },
  sidebarLogo: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "6px 10px 18px",
    borderBottom: "1px solid #2a2b2f",
    marginBottom: "8px",
  },
  logoIcon: {
    width: "8px",
    height: "8px",
    background: "#7C9A7E",
    borderRadius: "50%",
    flexShrink: 0,
  },
  logoText: {
    fontSize: "15px",
    fontWeight: "600",
    letterSpacing: "-0.2px",
    color: "#f0f0f2",
  },
  uploadBtn: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 14px",
    background: "#222428",
    border: "1px solid #2e2f35",
    borderRadius: "10px",
    color: "#c8c8cc",
    fontSize: "13px",
    cursor: "pointer",
    transition: "background 0.15s, border-color 0.15s",
    marginBottom: "16px",
    fontFamily: "inherit",
  },
  sidebarSection: {
    fontSize: "10px",
    fontWeight: "600",
    letterSpacing: "0.08em",
    color: "#555660",
    textTransform: "uppercase",
    padding: "0 10px",
    marginBottom: "4px",
  },
  recentItem: {
    padding: "9px 12px",
    borderRadius: "8px",
    cursor: "pointer",
    transition: "background 0.12s",
  },
  recentItemActive: {
    background: "#222428",
  },
  recentName: {
    fontSize: "13px",
    color: "#d0d0d4",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
    marginBottom: "2px",
  },
  recentDate: {
    fontSize: "11px",
    color: "#4a4b55",
  },

  // ── Main area ────────────────────────────────────────
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    background: "#111214",
  },

  // top bar
  topBar: {
    height: "52px",
    borderBottom: "1px solid #1e1f23",
    display: "flex",
    alignItems: "center",
    padding: "0 24px",
    gap: "10px",
  },
  statusDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    background: "#4ade80",
    flexShrink: 0,
  },
  statusDotIdle: {
    background: "#3a3b42",
  },
  topBarName: {
    fontSize: "13px",
    color: "#c0c0c6",
    flex: 1,
  },
  topBarPages: {
    fontSize: "12px",
    color: "#3e3f49",
  },

  // chat
  chatArea: {
    flex: 1,
    overflowY: "auto",
    padding: "28px 32px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  emptyState: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "12px",
    opacity: 0.35,
    userSelect: "none",
  },
  emptyIcon: {
    fontSize: "36px",
    marginBottom: "4px",
  },
  emptyText: {
    fontSize: "14px",
    color: "#666",
  },

  // message bubbles
  msgRow: (role) => ({
    display: "flex",
    justifyContent: role === "user" ? "flex-end" : "flex-start",
  }),
  bubble: (role) => ({
    maxWidth: "68%",
    padding: "11px 16px",
    borderRadius: role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
    background: role === "user" ? "#1C2B1E" : "#1c1d21",
    color: role === "user" ? "#E8E6E1" : "#d4d4d8", 
    fontSize: "14px",
    lineHeight: "1.6",
    boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
  }),
  sourceTag: {
    marginTop: "8px",
    paddingTop: "7px",
    borderTop: "1px solid rgba(255,255,255,0.07)",
    fontSize: "11px",
    color: "#5a5b66",
    display: "flex",
    alignItems: "center",
    gap: "5px",
  },

  // thinking indicator
  thinking: {
    display: "flex",
    gap: "5px",
    padding: "12px 16px",
    background: "#1c1d21",
    borderRadius: "16px 16px 16px 4px",
    alignSelf: "flex-start",
    width: "fit-content",
  },
  dot: {
    width: "6px",
    height: "6px",
    borderRadius: "50%",
    background: "#444",
    animation: "bounce 1.2s infinite ease-in-out",
  },

  // input bar
  inputBar: {
    padding: "16px 24px",
    borderTop: "1px solid #1a1b1f",
    display: "flex",
    gap: "10px",
    alignItems: "center",
    background: "#111214",
  },
  input: {
    flex: 1,
    padding: "10px 18px",
    background: "#1c1d22",
    border: "1px solid #2a2b32",
    borderRadius: "24px",
    color: "#e0e0e4",
    fontSize: "14px",
    outline: "none",
    fontFamily: "inherit",
    transition: "border-color 0.15s",
  },
  sendBtn: {
    width: "38px",
    height: "38px",
    borderRadius: "50%",
    background: "#7C9A7E",
    border: "none",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    transition: "opacity 0.15s, transform 0.1s",
  },
};

export default styles;