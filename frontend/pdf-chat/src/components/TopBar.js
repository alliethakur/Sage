function TopBar({ thread }) {
  const { name, pages, chunks } = thread;
  return (
    <div className="topbar">
      <div className="dot" />
      <div className="doc-name">{name}</div>
      {pages > 0 && <div className="pill">{pages} {pages === 1 ? "page" : "pages"}</div>}
      {chunks > 0 && <div className="pill">{chunks} chunks</div>}
    </div>
  );
}

export default TopBar;
