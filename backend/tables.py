"""Exact table questions for CSV files ("fare of passenger 2", "how many survived?").

Search (RAG) finds text; it can't look up a row by ID or count over 891 rows.
So for these questions the LLM writes a small JSON *query plan*, and this module
runs it with pandas on the full table.

Safety: the LLM never writes code. A plan can only use the operations allowed
below, and every column name is checked against the real table.
"""
import json
import re

import pandas as pd

OPS = {"==", "!=", ">", ">=", "<", "<=", "contains"}
AGGREGATES = {"count", "sum", "mean", "min", "max", "list"}
MAX_ROWS = 20  # most rows returned to the LLM and the Evidence panel


def load_table(path):
    # sep=None lets pandas detect commas, semicolons, tabs, ...
    df = pd.read_csv(path, sep=None, engine="python", encoding_errors="replace")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def describe(df):
    """Short description of the table for the planning prompt."""
    lines = [f"Rows: {len(df)}", "Columns (type: example values):"]
    for col in df.columns:
        examples = ", ".join(repr(_clean(v)) for v in df[col].dropna().unique()[:3])
        lines.append(f"- {col} ({df[col].dtype}): {examples}")
    return "\n".join(lines)


PLAN_INSTRUCTIONS = """Write a JSON query plan that answers the question from this table.
Reply with ONLY the JSON, using exactly these keys:
{
  "filters": [{"column": "<column>", "op": "==|!=|>|>=|<|<=|contains", "value": <value>}],
  "group_by": "<column>" or null,
  "aggregate": "count|sum|mean|min|max|list",
  "column": "<column to sum/average/min/max/list>" or null,
  "sort": {"column": "<column>", "descending": true|false} or null,
  "limit": <number of rows to return, at most 20>
}
Rules:
- Every condition in the question needs its own filter. Words like "survived",
  "female", "in class 1" or "older than 30" are conditions, even when the question
  also asks to group or count.
- Use "list" to return matching rows (for example to look up one row's values).
- Use [] for filters only when the question has no conditions at all.
- Column names must match the table exactly.

Examples (for a table with columns Name, Dept, Salary, Active):
Q: How many active employees are in each department?
{"filters": [{"column": "Active", "op": "==", "value": 1}], "group_by": "Dept",
 "aggregate": "count", "column": null, "sort": null, "limit": 20}
Q: What is the average salary of people in Sales?
{"filters": [{"column": "Dept", "op": "==", "value": "Sales"}], "group_by": null,
 "aggregate": "mean", "column": "Salary", "sort": null, "limit": 20}
Q: Who earns the most?
{"filters": [], "group_by": null, "aggregate": "list", "column": null,
 "sort": {"column": "Salary", "descending": true}, "limit": 1}"""


def describe_plan(plan):
    """The plan in plain words, so the answer can say exactly what was computed."""
    filters = plan.get("filters") or []
    conditions = " AND ".join(f"{f.get('column')} {f.get('op')} {f.get('value')!r}" for f in filters)
    parts = [f"Filters applied: {conditions}" if conditions else "Filters applied: NONE (all rows were used)"]
    if plan.get("group_by"):
        parts.append(f"grouped by {plan['group_by']}")
    aggregate = plan.get("aggregate") or "list"
    parts.append(f"calculation: {aggregate}" + (f"({plan['column']})" if plan.get("column") else ""))
    return "; ".join(parts)


def unused_columns(plan, question, df):
    """Columns the question mentions that the plan never uses, e.g. 'survived' -> Survived.
    These usually mean the planner forgot a condition."""
    words = [w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) >= 4]
    has_number = bool(re.search(r"\d", question))
    used = {plan.get("group_by"), plan.get("column"), (plan.get("sort") or {}).get("column")}
    used |= {f.get("column") for f in plan.get("filters") or []}
    missing = []
    for col in df.columns:
        name = col.lower()
        if col in used or len(name) < 3:
            continue
        # ID columns ("PassengerId") only matter when the question gives a number
        if name.endswith("id") and not has_number:
            continue
        # same word ("sex"), shared stem ("survived" ~ "survival"), or contained ("class" in "pclass")
        if name in question.lower().split() or any(
            w.startswith(name[:5]) or name.startswith(w[:5]) or w in name for w in words
        ):
            missing.append(col)
    return missing


def parse_plan(text):
    """Pull the JSON object out of the LLM's reply."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON plan found.")
    return json.loads(match.group(0))


def _norm(name):
    """'Total (₹)' -> 'total', 'Unit Price' -> 'unitprice': letters and digits only."""
    return re.sub(r"[^0-9a-z]", "", str(name).lower())


def _check_column(df, col):
    """Return the real column name. Forgives small slips like 'Total' for 'Total (₹)'
    or 'unit price' for 'Unit Price', but only when exactly one column fits."""
    if col in df.columns:
        return col
    wanted = _norm(col)
    if wanted:
        for test in (lambda c: _norm(c) == wanted, lambda c: _norm(c).startswith(wanted)):
            fits = [c for c in df.columns if test(c)]
            if len(fits) == 1:
                return fits[0]
    raise ValueError(f"Unknown column: {col!r}. Real columns: {', '.join(map(str, df.columns))}")


def _compare(series, op, value):
    """Apply one filter. Numbers compare as numbers; text compares case-insensitively."""
    numeric = pd.to_numeric(series, errors="coerce")
    try:
        number = float(value)
        is_number = numeric.notna().any()
    except (TypeError, ValueError):
        is_number = False

    if op == "contains":
        return series.astype(str).str.contains(str(value), case=False, regex=False, na=False)
    if is_number:
        left, right = numeric, number
    else:
        left, right = series.astype(str).str.strip().str.lower(), str(value).strip().lower()
    return {
        "==": left == right, "!=": left != right, ">": left > right,
        ">=": left >= right, "<": left < right, "<=": left <= right,
    }[op]


def _clean(value):
    """Make pandas/numpy values JSON-friendly."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 4)
    return value


def run_plan(df, plan):
    """Run a validated plan. Returns a JSON-friendly result."""
    mask = pd.Series(True, index=df.index)
    for f in plan.get("filters") or []:
        op = f.get("op")
        if op not in OPS:
            raise ValueError(f"Operation not allowed: {op!r}")
        f["column"] = _check_column(df, f.get("column"))  # store the real name
        mask &= _compare(df[f["column"]], op, f.get("value"))
    matched = df[mask]

    aggregate = plan.get("aggregate") or "list"
    if aggregate not in AGGREGATES:
        raise ValueError(f"Aggregate not allowed: {aggregate!r}")
    column = plan.get("column")
    if column is not None:
        column = plan["column"] = _check_column(df, column)
    if aggregate in {"sum", "mean", "min", "max"} and column is None:
        raise ValueError(f"'{aggregate}' needs a column.")
    limit = max(1, min(int(plan.get("limit") or MAX_ROWS), MAX_ROWS))
    result = {"matched_rows": int(len(matched)), "total_rows": int(len(df))}

    group_by = plan.get("group_by")
    if group_by:
        group_by = plan["group_by"] = _check_column(df, group_by)
        groups = matched.groupby(group_by, dropna=False)
        if aggregate in {"count", "list"}:
            series = groups.size()
        else:
            series = getattr(pd.to_numeric(matched[column], errors="coerce").groupby(matched[group_by]), aggregate)()
        series = series.sort_values(ascending=False).head(limit)
        value_name = "count" if aggregate in {"count", "list"} else f"{aggregate}({column})"
        result.update(kind="groups", columns=[group_by, value_name],
                      rows=[[_clean(k), _clean(v)] for k, v in series.items()])
        return result

    if aggregate == "count":
        result.update(kind="value", label="count", value=int(len(matched)))
        return result
    if aggregate in {"sum", "mean", "min", "max"}:
        value = getattr(pd.to_numeric(matched[column], errors="coerce"), aggregate)()
        result.update(kind="value", label=f"{aggregate}({column})", value=_clean(value))
        return result

    # "list": return the matching rows themselves
    sort = plan.get("sort")
    if sort and sort.get("column"):
        sort["column"] = _check_column(df, sort["column"])
        matched = matched.sort_values(sort["column"], ascending=not sort.get("descending", False))
    shown = matched.head(limit)
    columns = list(df.columns) if column is None else [column]
    result.update(
        kind="rows",
        columns=["Row"] + columns,
        # Spreadsheet-style row numbers (header is row 1), matching search citations
        rows=[[int(i) + 2] + [_clean(v) for v in shown.loc[i, columns]] for i in shown.index],
    )
    return result
