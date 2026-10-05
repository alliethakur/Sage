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
Use "list" to return matching rows (for example to look up one row's values).
Use [] for no filters. Column names must match the table exactly."""


def parse_plan(text):
    """Pull the JSON object out of the LLM's reply."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON plan found.")
    return json.loads(match.group(0))


def _check_column(df, col):
    if col not in df.columns:
        raise ValueError(f"Unknown column: {col!r}")
    return col


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
        mask &= _compare(df[_check_column(df, f.get("column"))], op, f.get("value"))
    matched = df[mask]

    aggregate = plan.get("aggregate") or "list"
    if aggregate not in AGGREGATES:
        raise ValueError(f"Aggregate not allowed: {aggregate!r}")
    column = plan.get("column")
    if column is not None:
        _check_column(df, column)
    if aggregate in {"sum", "mean", "min", "max"} and column is None:
        raise ValueError(f"'{aggregate}' needs a column.")
    limit = max(1, min(int(plan.get("limit") or MAX_ROWS), MAX_ROWS))
    result = {"matched_rows": int(len(matched)), "total_rows": int(len(df))}

    group_by = plan.get("group_by")
    if group_by:
        _check_column(df, group_by)
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
        _check_column(df, sort["column"])
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
