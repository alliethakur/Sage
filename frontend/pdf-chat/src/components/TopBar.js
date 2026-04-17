import styles from "../constants/styles";

function TopBar({ uploaded, fileName }) {
  return (
    <div style={styles.topBar}>
      <div
        style={{
          ...styles.statusDot,
          ...(uploaded ? {} : styles.statusDotIdle),
        }}
      />
      <span style={styles.topBarName}>
        {uploaded ? fileName : "No document loaded"}
      </span>
      {uploaded && <span style={styles.topBarPages}>12 pages</span>}
    </div>
  );
}

export default TopBar;