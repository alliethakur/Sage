"""Type-aware loading and chunking for Sage.

Each file type is split in the way that suits it:
  - PDF, TXT, MD (prose): recursive splitting measured in TOKENS of the embedding
    model, so every chunk fits inside MiniLM's 256-token window (anything longer
    is silently cut off by the model and never searched).
  - CSV and Excel (tables): ROW-ATOMIC chunks. An Excel sheet is first converted
    to a clean CSV (title rows skipped, dates tidied), then handled like a CSV. Rows are never split in half, and every chunk
    repeats the column names so a row still makes sense on its own.

Every chunk gets a human-readable `location` ("Page 7", "Lines 12-30", "Rows 2-9")
that Sage shows as its citation.
"""
import csv
import datetime
import io
import os
import shutil

import pandas as pd

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from embeddings import count_tokens  # the embedding model's own tokenizer (no PyTorch)

CHUNK_TOKENS = 128      # well inside MiniLM's 256-token limit
OVERLAP_TOKENS = 16     # small overlap so a sentence cut at a boundary isn't lost
MAX_CSV_ROWS = 5000     # keeps indexing fast for large tables
SUPPORTED = {".pdf": "pdf", ".txt": "text", ".md": "text", ".csv": "csv",
             ".xlsx": "excel", ".xlsm": "excel"}

def prose_splitter():
    # Recursive splitting (paragraphs, then sentences, then words), measured in tokens
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_TOKENS,
        chunk_overlap=OVERLAP_TOKENS,
        length_function=count_tokens,
        add_start_index=True,
    )

def read_text(path):
    """Read a text file, trying UTF-8 first, then the common Windows encoding."""
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not read this file's text encoding.")

def file_kind(filename):
    ext = "." + filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    return SUPPORTED.get(ext)

def plural(n, word):
    return f"{n:,} {word}{'' if n == 1 else 's'}"


# ---------- PDF ----------

def load_pdf(path):
    pages = [Document(page_content=page.extract_text() or "", metadata={"page": i})
             for i, page in enumerate(PdfReader(path).pages)]
    if not "".join(p.page_content for p in pages).strip():
        raise ValueError("This PDF appears to be scanned. Please upload a text-based PDF.")

    chunks = []
    for chunk in prose_splitter().split_documents(pages):
        page = int(chunk.metadata.get("page", 0))
        # 'page' is the physical page position in the file (0-indexed), which can
        # differ from the printed page number when a PDF has front matter.
        chunk.metadata = {"page": page, "location": f"Page {page + 1}"}
        chunks.append(chunk)

    sections = [(f"Page {i + 1}", p.page_content) for i, p in enumerate(pages)]
    return sections, chunks, plural(len(pages), "page")


# ---------- TXT / MD ----------

def load_text(path):
    text = read_text(path)
    if not text.strip():
        raise ValueError("This file is empty.")

    chunks = []
    for chunk in prose_splitter().create_documents([text]):
        start = chunk.metadata.get("start_index", 0)
        first = text.count("\n", 0, max(start, 0)) + 1
        last = first + chunk.page_content.count("\n")
        label = f"Line {first}" if first == last else f"Lines {first}–{last}"
        chunk.metadata = {"location": label}
        chunks.append(chunk)

    # Sections of 40 lines, used for the summary and "overview" questions
    lines = text.splitlines()
    sections = []
    for i in range(0, len(lines), 40):
        block = lines[i:i + 40]
        sections.append((f"Lines {i + 1}–{i + len(block)}", "\n".join(block)))
    return sections, chunks, plural(len(lines), "line")


# ---------- CSV ----------

def load_csv(path):
    text = read_text(path)
    if not text.strip():
        raise ValueError("This CSV is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:5000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        raise ValueError("This CSV needs a header row and at least one data row.")

    header = [h.strip() or f"column_{i + 1}" for i, h in enumerate(rows[0])]
    data = rows[1:]
    total_rows = len(data)
    data = data[:MAX_CSV_ROWS]
    columns_line = "Columns: " + ", ".join(header)

    def row_text(row_number, row):
        cells = [f"{col}: {val.strip()}" for col, val in zip(header, row) if val.strip()]
        return f"Row {row_number}: " + "; ".join(cells)

    # Spreadsheet-style numbering: the header is row 1, data starts at row 2
    row_texts = [(i + 2, row_text(i + 2, r)) for i, r in enumerate(data)]

    # Row-atomic chunks: add whole rows until the token budget is reached
    chunks = []
    budget = CHUNK_TOKENS - count_tokens(columns_line)
    group, used = [], 0
    def flush():
        if not group:
            return
        first, last = group[0][0], group[-1][0]
        label = f"Row {first}" if first == last else f"Rows {first}–{last}"
        body = columns_line + "\n" + "\n".join(t for _, t in group)
        chunks.append(Document(page_content=body, metadata={"location": label}))
    for number, line in row_texts:
        tokens = count_tokens(line)
        if group and used + tokens > budget:
            flush()
            group, used = [], 0
        group.append((number, line))
        used += tokens
    flush()

    # Sections of 25 rows for the summary and "overview" questions
    note = f"{columns_line}\nTotal data rows: {total_rows:,}"
    if total_rows > MAX_CSV_ROWS:
        note += f" (only the first {MAX_CSV_ROWS:,} are searchable)"
    sections = []
    for i in range(0, len(row_texts), 25):
        block = row_texts[i:i + 25]
        label = f"Rows {block[0][0]}–{block[-1][0]}"
        body = "\n".join(t for _, t in block)
        sections.append((label, (note + "\n" if i == 0 else "") + body))
    return sections, chunks, plural(total_rows, "row")


# ---------- Excel ----------

def _cell(value):
    """Turn one Excel cell into clean text (dates without 00:00:00, 5.0 -> 5)."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, datetime.datetime):
        if (value.hour, value.minute, value.second) == (0, 0, 0):
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return " ".join(str(value).split())  # also flattens line breaks inside a cell


def excel_to_csv(path, out_path):
    """Convert the first non-empty sheet of an Excel file to a CSV.
    Returns (sheet name, number of non-empty sheets)."""
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    except Exception:
        raise ValueError("Could not open this Excel file. Try saving it again as .xlsx or CSV.")

    usable = []
    for name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")  # drop empty rows and columns
        if len(df) >= 2:
            usable.append((name, df))
    if not usable:
        raise ValueError("This Excel file has no sheet with a header row and data.")
    name, df = usable[0]

    # Office sheets often start with a title ("Sales Report 2025") above the real table.
    # The header is the first row (of the first 10) that fills at least half the columns.
    filled = df.head(10).notna().sum(axis=1).tolist()
    need = max(2, df.shape[1] / 2) if df.shape[1] > 1 else 1
    header_at = next((i for i, n in enumerate(filled) if n >= need), 0)

    header, seen = [], {}
    for i, h in enumerate(df.iloc[header_at]):
        h = _cell(h) or f"column_{i + 1}"
        seen[h] = seen.get(h, 0) + 1
        header.append(h if seen[h] == 1 else f"{h}_{seen[h]}")  # make duplicate names unique

    rows = [[_cell(v) for v in row] for row in df.iloc[header_at + 1:].itertuples(index=False)]
    rows = [r for r in rows if any(r)]
    if not rows:
        raise ValueError(f"Sheet '{name}' has a header row but no data.")

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return name, len(usable)


def load_file(path, filename, table_out=None):
    """Return (kind, sections, chunks, stats) for a supported file, or raise ValueError.
    For tables (CSV / Excel), a clean CSV copy is written to table_out for exact queries."""
    kind = file_kind(filename)
    if kind is None:
        raise ValueError("Only PDF, TXT, MD, CSV and Excel (.xlsx) files are supported.")

    note = ""
    if kind == "excel":
        csv_path = path + ".csv"
        try:
            sheet, sheet_count = excel_to_csv(path, csv_path)
            sections, chunks, stats = load_csv(csv_path)
            if table_out:
                shutil.copy(csv_path, table_out)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
        note = f" · sheet '{sheet}'" + (f" (1 of {sheet_count})" if sheet_count > 1 else "")
        kind = "csv"  # from here on, Sage treats it exactly like a CSV
    else:
        loader = {"pdf": load_pdf, "text": load_text, "csv": load_csv}[kind]
        sections, chunks, stats = loader(path)
        if kind == "csv" and table_out:
            shutil.copy(path, table_out)

    if not chunks:
        raise ValueError("No readable text was found in this file.")
    return kind, sections, chunks, stats + note
