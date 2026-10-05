function Sidebar({ threads, activeId, onSelect, onNewChat, onDelete, uploading, uploadError }) {
  return (
    <aside className="sidebar">
      <div className="logo">
        <div className="logo-mark" />
        Sage
      </div>

      {/* One chat = one document, so "New chat" goes straight to picking a file */}
      <button className="btn primary" onClick={onNewChat} disabled={uploading}>
        {uploading ? "Reading document…" : "+ New chat"}
      </button>

      {uploadError && <div className="error">{uploadError}</div>}

      <div className="section">Chats</div>
      {threads.length === 0 && <div className="empty-note">Your chats will appear here.</div>}
      {threads.map((t) => (
        <div
          key={t.id}
          className={`thread ${t.id === activeId ? "active" : ""}`}
          onClick={() => onSelect(t.id)}
          title={t.name}
        >
          <div className="thread-text">
            <div className="name">{t.name}</div>
            <div className="meta">
              {t.pages ? `${t.pages} ${t.pages === 1 ? "page" : "pages"} · ` : ""}
              {t.date}
            </div>
          </div>
          <button
            className="delete"
            title="Remove chat"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(t.id);
            }}
          >
            ✕
          </button>
        </div>
      ))}
    </aside>
  );
}

export default Sidebar;
