"""Evaluate Sage against a fixed question set.

Usage (with the backend running on port 5000):
    python eval/run_eval.py                 # full run with hybrid search
    python eval/run_eval.py --ablation      # also compare dense-only / keyword-only / hybrid
    python eval/run_eval.py --only titanic  # one document only

Put the test files listed in eval/questions.json into eval/docs/ first.
Results are printed and saved to eval/results/ (JSON with every answer + a Markdown summary).
"""
import argparse
import json
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

HERE = Path(__file__).parent
REFUSAL = "couldn't find this in the document"


def upload(base, path):
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload", files={"file": (path.name, f)}, timeout=600)
    data = r.json()
    if "doc_id" not in data:
        sys.exit(f"Upload failed for {path.name}: {data}")
    return data["doc_id"]


def ask(base, doc_id, question, mode):
    start = time.time()
    r = requests.post(f"{base}/ask", json={"question": question, "doc_id": doc_id, "mode": mode}, timeout=180)
    data = r.json()
    data["latency"] = round(time.time() - start, 2)
    return data


def score(item, resp):
    """Grade one answer. Returns a dict of per-question metrics (None = not applicable)."""
    # NFKC turns special spaces (e.g. the narrow no-break space in "EAT\u202fME") into normal ones
    answer = unicodedata.normalize("NFKC", resp.get("answer") or "")
    failed = "answer" not in resp
    refused = REFUSAL in answer.lower()
    evidence = resp.get("evidence") or []
    locations = [e.get("location") for e in evidence]
    cited = [e.get("location") for e in evidence if e.get("cited")]
    pages = item.get("pages")

    result = {
        "error": resp.get("error") if failed else None,
        "refused": refused,
        "route_ok": (resp.get("route") == item["route"]) if item.get("route") and not failed else None,
        "correct": None,
        "hit_at_5": None,
        "citation_precision": None,
    }
    if item["type"] == "answer":
        result["correct"] = (not failed and not refused and
                             all(re.search(p, answer, re.IGNORECASE) for p in item["expect"]))
        if pages and resp.get("route") == "document_question":
            result["hit_at_5"] = any(loc in pages for loc in locations)
            if cited:
                result["citation_precision"] = sum(loc in pages for loc in cited) / len(cited)
    elif item["type"] == "refuse":
        result["correct"] = not failed and refused
    return result


def rate(values):
    values = [v for v in values if v is not None]
    return (sum(values) / len(values), len(values)) if values else (None, 0)


def summarize(rows):
    answerable = [r for r in rows if r["type"] == "answer"]
    refuse = [r for r in rows if r["type"] == "refuse"]
    return {
        "answer_accuracy": rate([r["correct"] for r in answerable]),
        "false_refusal_rate": rate([r["refused"] for r in answerable]),
        "refusal_accuracy": rate([r["correct"] for r in refuse]),
        "route_accuracy": rate([r["route_ok"] for r in rows]),
        "retrieval_hit_at_5": rate([r["hit_at_5"] for r in rows]),
        "citation_precision": rate([r["citation_precision"] for r in rows]),
        "median_latency_s": (statistics.median([r["latency"] for r in rows]), len(rows)) if rows else (None, 0),
        "errors": (sum(1 for r in rows if r["error"]), len(rows)),
    }


def fmt(metric, value):
    v, n = value
    if v is None:
        return "n/a"
    if metric == "errors":
        return f"{v} of {n}"
    if metric == "median_latency_s":
        return f"{v:.1f}s"
    return f"{v * 100:.0f}% (n={n})"


def run(base, data, docs, only, mode, sleep, doc_ids):
    rows = []
    items = [q for q in data["questions"] if not only or q["doc"] == only]
    for i, item in enumerate(items, 1):
        resp = ask(base, doc_ids[item["doc"]], item["q"], mode)
        row = {**item, **score(item, resp), "mode": mode, "answer": resp.get("answer"),
               "route_got": resp.get("route"), "latency": resp["latency"],
               "evidence_locations": [e.get("location") for e in resp.get("evidence") or []]}
        rows.append(row)
        mark = {True: "PASS", False: "FAIL", None: "  - "}[row["correct"]]
        print(f"[{mode}] {i:2}/{len(items)} {mark}  {item['doc']:9} {item['q'][:60]}")
        time.sleep(sleep)  # be gentle with the free API rate limit
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5000")
    parser.add_argument("--only", choices=["attention", "alice", "titanic"])
    parser.add_argument("--ablation", action="store_true",
                        help="also run the PDF questions with dense-only and keyword-only search")
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    data = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    docs = HERE / "docs"
    needed = {k: v for k, v in data["documents"].items() if not args.only or k == args.only}
    for name in needed.values():
        if not (docs / name).exists():
            sys.exit(f"Missing eval/docs/{name}. Copy the test files into eval/docs first.")

    try:
        requests.get(args.base, timeout=5)
    except requests.ConnectionError:
        sys.exit(f"Can't reach the Sage backend at {args.base}. Start it first: cd backend, python app.py")

    print("Uploading test documents...")
    doc_ids = {key: upload(args.base, docs / name) for key, name in needed.items()}

    all_rows = run(args.base, data, docs, args.only, "hybrid", args.sleep, doc_ids)
    summaries = {"hybrid": summarize(all_rows)}

    if args.ablation:
        pdf_data = {"questions": [q for q in data["questions"]
                                  if q["doc"] == "attention" and q.get("route") == "document_question"]}
        hybrid_pdf = [r for r in all_rows if r["doc"] == "attention" and r.get("route") == "document_question"]
        summaries["pdf: hybrid"] = summarize(hybrid_pdf)
        for mode in ("dense", "keyword"):
            rows = run(args.base, pdf_data, docs, None, mode, args.sleep, doc_ids)
            summaries[f"pdf: {mode} only"] = summarize(rows)
            all_rows += rows

    # Report
    metrics = list(next(iter(summaries.values())).keys())
    lines = ["| Metric | " + " | ".join(summaries) + " |", "|---|" + "---|" * len(summaries)]
    for m in metrics:
        lines.append(f"| {m} | " + " | ".join(fmt(m, s[m]) for s in summaries.values()) + " |")
    table = "\n".join(lines)
    failures = [r for r in all_rows if r["correct"] is False]
    print("\n" + table)
    if failures:
        print("\nFailed questions:")
        for r in failures:
            print(f"  [{r['mode']}] {r['q']}\n      -> {(r['answer'] or r['error'] or '')[:150]!r}")

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    (out / f"{stamp}.json").write_text(json.dumps({"summaries": summaries, "rows": all_rows}, indent=2), encoding="utf-8")
    (out / f"{stamp}.md").write_text(f"# Sage eval {stamp}\n\n{table}\n", encoding="utf-8")
    print(f"\nSaved eval/results/{stamp}.json and .md")


if __name__ == "__main__":
    main()
