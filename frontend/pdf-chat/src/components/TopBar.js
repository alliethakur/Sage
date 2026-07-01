import { useState, useEffect, useRef } from "react";
import styles from "../constants/styles";

function TopBar({ uploaded, fileName, summary, staleName }) {
  const [open, setOpen] = useState(true);
  const [displayedText, setDisplayedText] = useState("");
  const [done, setDone] = useState(false);
  const indexRef = useRef(0);

  // auto-expand the panel as soon as a file is uploaded
  useEffect(() => {
    if (uploaded) setOpen(true);
  }, [uploaded]);

  // typewriter effect: fires whenever summary arrives or is cleared
  useEffect(() => {
    if (!summary) {
      setDisplayedText("");
      setDone(false);
      indexRef.current = 0;
      return;
    }

    setOpen(true);
    indexRef.current = 0;
    setDisplayedText("");
    setDone(false);

    const interval = setInterval(() => {
      indexRef.current += 1;
      setDisplayedText(summary.slice(0, indexRef.current));
      if (indexRef.current >= summary.length) {
        clearInterval(interval);
        setDone(true);
      }
    }, 20);

    return () => clearInterval(interval);
  }, [summary]);

  const stale = !uploaded && !!staleName;
  const cooking = uploaded && !summary;
  const showPanel = cooking || !!summary || stale;

  const displayName = uploaded ? fileName : staleName ? staleName : "No document loaded";

  return (
    <div>
      <div style={styles.topBar}>
        <div
          style={{
            ...styles.statusDot,
            ...(uploaded ? {} : styles.statusDotIdle),
          }}
        />
        <span style={styles.topBarName}>{displayName}</span>
        {uploaded && <span style={styles.topBarPages}>12 pages</span>}
        {showPanel && !stale && (
          <button
            onClick={() => setOpen((o) => !o)}
            style={{
              background: "none",
              border: "none",
              color: "#4a4b55",
              fontSize: "11px",
              cursor: "pointer",
              padding: "2px 6px",
              fontFamily: "inherit",
              letterSpacing: "0.02em",
            }}
          >
            {open ? "▾ Summary" : "▸ Summary"}
          </button>
        )}
      </div>

      {showPanel && (open || stale) && (
        <div
          style={{
            padding: "12px 24px",
            borderBottom: "1px solid #1e1f23",
            background: "#131417",
            fontSize: "12.5px",
            lineHeight: "1.65",
            color: "#7a7b85",
          }}
        >
          {stale ? (
            <span style={{ color: "#4a4b55", fontStyle: "italic" }}>
              Re-upload this PDF to ask questions about it.
            </span>
          ) : cooking ? (
            <span style={{ color: "#4a4b55", fontStyle: "italic" }}>
              Cooking your summary...
            </span>
          ) : (
            <>
              {displayedText}
              {done && (
                <div
                  style={{
                    marginTop: "8px",
                    fontSize: "11px",
                    color: "#3a7a3c",
                    letterSpacing: "0.03em",
                  }}
                >
                  ✓ Ready
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default TopBar;
