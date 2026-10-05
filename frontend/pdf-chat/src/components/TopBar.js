function TopBar({ thread }) {
  const { name, stats, pages, chunks } = thread;
  // stats is "15 pages" / "61 lines" / "1,204 rows"; older chats only have pages
  const size = stats || (pages > 0 ? `${pages} ${pages === 1 ? "page" : "pages"}` : null);
  return (
    <div className="topbar">
      <div className="dot" />
      <div className="doc-name">{name}</div>
      {size && <div className="pill">{size}</div>}
      {chunks > 0 && <div className="pill">{chunks} chunks</div>}
    </div>
  );
}

export default TopBar;
