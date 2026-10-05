import { useEffect, useRef, useState } from "react";

// Words not worth highlighting
const STOPWORDS = new Set(
  "a an the of in on at to for by with and or is are was were be been do does did what which who whom how why when where this that these those it its they their them we our you your can could would should much many used use from as about into than then there".split(" ")
);

function questionWords(query) {
  return [...new Set((query || "").toLowerCase().match(/[a-z0-9]+/g) || [])].filter(
    (w) => w.length > 2 && !STOPWORDS.has(w)
  );
}

// Wrap words from the question in <mark> so you can see why a chunk matched
function Highlighted({ text, words }) {
  if (!words.length) return text;
  const pattern = new RegExp(`\\b(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})\\w*`, "gi");
  const parts = [];
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    parts.push(text.slice(last, m.index), <mark key={m.index}>{m[0]}</mark>);
    last = m.index + m[0].length;
  }
  parts.push(text.slice(last));
  return parts;
}

function ScoreBar({ label, value, kind }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="score">
      <span>{label}</span>
      <div className={`bar ${kind}`}><i style={{ width: `${pct}%` }} /></div>
      <span>{value.toFixed(2)}</span>
    </div>
  );
}

function Chunk({ chunk, words, active, onClick }) {
  const [expanded, setExpanded] = useState(false);
  const ref = useRef(null);
  const long = chunk.text.length > 260;
  const text = expanded || !long ? chunk.text : chunk.text.slice(0, 260) + "…";

  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  return (
    <div ref={ref} className={`chunk ${active ? "on" : ""} ${chunk.cited ? "" : "dim"}`} onClick={onClick}>
      <div className="chunk-top">
        <span className="num">[{chunk.n}]</span>
        <span className="tag page">Page {chunk.page}</span>
        {chunk.found_by.includes("keyword") && <span className="tag kw">keyword</span>}
        {chunk.found_by.includes("meaning") && <span className="tag mean">meaning</span>}
        {!chunk.cited && <span className="tag unused">not used</span>}
      </div>
      <p className="chunk-text"><Highlighted text={text} words={words} /></p>
      {long && (
        <button className="more" onClick={(e) => { e.stopPropagation(); setExpanded((x) => !x); }}>
          {expanded ? "show less" : "show more"}
        </button>
      )}
      <ScoreBar label="meaning" value={chunk.meaning_score} kind="mean" />
      <ScoreBar label="keyword" value={chunk.keyword_score} kind="kw" />
    </div>
  );
}

function EvidencePanel({ hasDoc, message, activeCite, onCite }) {
  const evidence = message?.evidence || [];
  const cited = evidence.filter((e) => e.cited).length;
  const words = questionWords(message?.query);

  let empty = null;
  if (!hasDoc) empty = "Upload a document to start.\nThe chunks Sage reads will appear here.";
  else if (!message?.query) empty = "Ask a question.\nYou'll see exactly which chunks the answer came from.";
  else if (message.route === "casual") empty = "Casual reply.\nNo document search was needed.";
  else if (message.route === "overview") empty = `Overview question.\nAnswered from the start of the document${message.sources?.length ? `\n(${message.sources.join(", ")})` : ""}.`;
  else if (!evidence.length) empty = "Nothing in the document matched this question,\nso Sage didn't answer.";

  return (
    <aside className="evidence">
      <div className="ev-head">
        <div className="ev-title">Evidence</div>
        {evidence.length > 0 && <div className="ev-meta">{evidence.length} retrieved · {cited} cited</div>}
      </div>
      {message?.query && (
        <div className="ev-query"><i>query ›</i> {message.query}</div>
      )}
      {empty ? (
        <div className="ev-empty" style={{ whiteSpace: "pre-line" }}>{empty}</div>
      ) : (
        <div className="ev-list">
          {evidence.map((chunk) => (
            <Chunk
              key={chunk.n}
              chunk={chunk}
              words={words}
              active={activeCite === chunk.n}
              onClick={() => onCite(chunk.n)}
            />
          ))}
        </div>
      )}
    </aside>
  );
}

export default EvidencePanel;
