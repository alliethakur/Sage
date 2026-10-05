import { useRef, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import remarkGfm from "remark-gfm"; // tables, strikethrough, task lists
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";

// The model sometimes writes maths as \( ... \) or \[ ... \].
// remark-math only understands $...$ and $$...$$, so convert them.
function normalizeMath(text) {
  return text
    .replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => `$$${m}$$`)
    .replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => `$${m}$`);
}

// Turn citation markers like [1] into special links, rendered as clickable chips below
function linkCitations(text) {
  return text.replace(/\[(\d+)\](?!\()/g, (_, n) => `[${n}](#cite-${n})`);
}

const ROUTE_LABELS = {
  document_question: "hybrid search",
  overview: "start of document",
  casual: "no search needed",
  table_query: "exact query over the full table",
};

function Answer({ msg, index, activeCite, isShown, onCite }) {
  const components = {
    a: ({ href, children }) => {
      if (href?.startsWith("#cite-")) {
        const n = Number(href.slice(6));
        return (
          <button
            className={`cite ${isShown && activeCite === n ? "on" : ""}`}
            onClick={() => onCite(index, n)}
            title="Show this source"
          >
            {n}
          </button>
        );
      }
      return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
    },
  };

  return (
    <div className="answer">
      <ReactMarkdown components={components} remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
        {linkCitations(normalizeMath(msg.text))}
      </ReactMarkdown>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text.replace(/\[\d+\]/g, "")); // copy without citation numbers
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return <button onClick={copy}>{copied ? "Copied ✓" : "Copy"}</button>;
}

// Types the summary out once, right after upload; afterwards it shows instantly
function Summary({ text, alreadyShown, onShown }) {
  const [shown, setShown] = useState(alreadyShown ? text : "");
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (!text) return;
    if (alreadyShown) {
      setShown(text);
      return;
    }
    let i = 0;
    const timer = setInterval(() => {
      i += 3;
      setShown(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(timer);
        onShown();
      }
    }, 16);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);

  return (
    <div className="summary">
      <div className="summary-title">
        SUMMARY
        <button className="summary-toggle" onClick={() => setOpen((o) => !o)}>{open ? "Hide" : "Show"}</button>
      </div>
      {open && (text ? shown : "Writing a summary…")}
    </div>
  );
}

const LOADING_MESSAGES = ["Searching your document…", "Reading the best chunks…", "Writing the answer…"];

function Thinking() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => (x + 1) % LOADING_MESSAGES.length), 1100);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="thinking fade-up">
      <div className="bounce"><span /><span /><span /></div>
      {LOADING_MESSAGES[i]}
    </div>
  );
}

function ChatArea({ thread, loading, shownIndex, activeCite, onCite, onSelectMessage, onSummaryShown }) {
  const bottomRef = useRef(null);
  const { messages } = thread;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  return (
    <div className="messages">
      <Summary
        key={thread.id}
        text={thread.summary}
        alreadyShown={thread.summaryShown}
        onShown={onSummaryShown}
      />

      {messages.map((msg, i) =>
        msg.role === "user" ? (
          <div key={i} className="msg user fade-up">{msg.text}</div>
        ) : (
          <div key={i} className={`msg bot fade-up ${i === shownIndex && (msg.evidence?.length || msg.table) ? "selected" : ""}`}>
            {msg.route && (
              <div className="route">
                route → <b>{msg.route}</b> · {ROUTE_LABELS[msg.route] || ""}
                {msg.evidence?.length ? ` · ${msg.evidence.length} chunks` : ""}
              </div>
            )}
            <Answer msg={msg} index={i} activeCite={activeCite} isShown={i === shownIndex} onCite={onCite} />
            {msg.query && !msg.isError && (
              <div className="actions">
                <CopyButton text={msg.text} />
                {msg.evidence?.length > 0 && (
                  <button onClick={() => onSelectMessage(i)}>
                    {msg.evidence.filter((e) => e.cited).length} of {msg.evidence.length} sources cited
                  </button>
                )}
                {msg.table && <button onClick={() => onSelectMessage(i)}>Show query</button>}
                {msg.sources?.length > 0 && <span>{msg.sources.join(", ")}</span>}
              </div>
            )}
          </div>
        )
      )}

      {loading && <Thinking />}
      <div ref={bottomRef} />
    </div>
  );
}

export default ChatArea;
