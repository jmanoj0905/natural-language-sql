"""Helpers for translating low-level SQL execution errors into plain English."""

from __future__ import annotations

import re
from typing import Dict, List, Optional


_DUPLICATE_PATTERNS = (
    "duplicate key value violates unique constraint",
    "duplicate entry",
    "unique constraint failed",
    "violates unique constraint",
    "already exists",
)

_FOREIGN_KEY_PATTERNS = (
    "foreign key constraint",
    "violates foreign key constraint",
    "cannot add or update a child row",
    "a foreign key constraint fails",
)

_TIMEOUT_PATTERNS = (
    "timeout",
    "timed out",
    "statement timeout",
    "lock wait timeout exceeded",
)

_PERMISSION_PATTERNS = (
    "permission denied",
    "not allowed",
    "command denied",
    "must be owner",
)


def humanize_query_execution_error(error: Exception, sql: str) -> str:
    """Return a user-friendly explanation for a database execution error."""
    raw_error = str(error).strip()
    lowered = raw_error.lower()
    insert_context = _extract_insert_context(sql)
    record_label = _describe_record(insert_context)
    table_label = _describe_table(insert_context.get("table"))

    if any(pattern in lowered for pattern in _DUPLICATE_PATTERNS):
        if record_label:
            return f"Couldn't save this change because {record_label} already exists."
        if table_label:
            return f"Couldn't save this change because a matching row already exists in {table_label}."
        return "Couldn't save this change because a matching record already exists."

    if any(pattern in lowered for pattern in _FOREIGN_KEY_PATTERNS):
        return (
            "Couldn't save this change because it refers to another record that doesn't exist yet. "
            "Create the related record first, then try again."
        )

    column_name = _extract_column_name(raw_error)
    if (
        "cannot be null" in lowered
        or "null value in column" in lowered
        or "doesn't have a default value" in lowered
        or "has no default value" in lowered
    ):
        if column_name:
            return f"Couldn't save this change because the '{column_name}' field is required."
        return "Couldn't save this change because one of the required fields is missing."

    if "data too long" in lowered or "value too long" in lowered or "too long for type" in lowered:
        if column_name:
            return f"Couldn't save this change because the value for '{column_name}' is too long."
        return "Couldn't save this change because one of the values is too long."

    if (
        "invalid input syntax" in lowered
        or "incorrect integer value" in lowered
        or "invalid datetime format" in lowered
        or "truncated incorrect" in lowered
        or "out of range value" in lowered
    ):
        if column_name:
            return f"Couldn't run this query because the value for '{column_name}' has the wrong format."
        return "Couldn't run this query because one of the values has the wrong format for this database field."

    if "syntax error" in lowered or "you have an error in your sql syntax" in lowered:
        return "The generated SQL is not valid for this database, so it could not be executed."

    if "unknown column" in lowered or ("column" in lowered and "does not exist" in lowered):
        if column_name:
            return f"The query refers to a column named '{column_name}', but that column does not exist in this database."
        return "The query refers to a column that does not exist in this database."

    if "relation" in lowered and "does not exist" in lowered:
        table_name = _extract_relation_name(raw_error)
        if table_name:
            return f"The query refers to a table named '{table_name}', but that table does not exist in this database."
        return "The query refers to a table that does not exist in this database."

    if "table" in lowered and "doesn't exist" in lowered:
        table_name = _extract_relation_name(raw_error)
        if table_name:
            return f"The query refers to a table named '{table_name}', but that table does not exist in this database."
        return "The query refers to a table that does not exist in this database."

    if any(pattern in lowered for pattern in _TIMEOUT_PATTERNS):
        return "The database took too long to run this query. Try narrowing the request or running it again."

    if "deadlock detected" in lowered:
        return "The database hit a temporary locking conflict while running this query. Please try again."

    if any(pattern in lowered for pattern in _PERMISSION_PATTERNS):
        return "This database user does not have permission to run that query."

    cleaned = _clean_raw_message(raw_error)
    return f"The database couldn't run this query: {cleaned}"


def _extract_insert_context(sql: str) -> Dict[str, object]:
    match = re.search(
        r"INSERT\s+INTO\s+([`\"\w.]+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}

    table_name = _clean_identifier(match.group(1))
    column_names = [_clean_identifier(part) for part in _split_sql_list(match.group(2))]
    raw_values = _split_sql_list(match.group(3))
    values = {
        column: _clean_sql_literal(value)
        for column, value in zip(column_names, raw_values)
        if column
    }
    return {"table": table_name, "values": values}


def _split_sql_list(text: str) -> List[str]:
    items: List[str] = []
    current: List[str] = []
    in_single = False
    in_double = False
    depth = 0
    i = 0

    while i < len(text):
        char = text[i]

        if char == "'" and not in_double:
            if in_single and i + 1 < len(text) and text[i + 1] == "'":
                current.append("''")
                i += 2
                continue
            in_single = not in_single
            current.append(char)
            i += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            i += 1
            continue

        if not in_single and not in_double:
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                items.append("".join(current).strip())
                current = []
                i += 1
                continue

        current.append(char)
        i += 1

    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _clean_identifier(value: str) -> str:
    return value.strip().strip('`').strip('"')


def _clean_sql_literal(value: str) -> str:
    value = value.strip()
    if value.upper() == "NULL":
        return "null"
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def _describe_record(context: Dict[str, object]) -> Optional[str]:
    if not context:
        return None

    values = context.get("values") or {}
    if not isinstance(values, dict):
        return None

    entity = _singularize(_describe_table(context.get("table")) or "record")

    for column in ("name", "full_name"):
        if values.get(column):
            return f"{_article_for(entity)} {entity} named '{values[column]}'"

    if values.get("username"):
        return f"{_article_for(entity)} {entity} with username '{values['username']}'"

    if values.get("email"):
        return f"{_article_for(entity)} {entity} with email '{values['email']}'"

    if values.get("id"):
        return f"{_article_for(entity)} {entity} with id '{values['id']}'"

    return None


def _describe_table(table_name: Optional[object]) -> Optional[str]:
    if not table_name or not isinstance(table_name, str):
        return None
    clean = table_name.split(".")[-1]
    return clean.replace("_", " ")


def _singularize(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("ses"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _article_for(word: str) -> str:
    return "an" if word[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _extract_column_name(raw_error: str) -> Optional[str]:
    patterns = [
        r"column ['\"]?([\w.]+)['\"]?",
        r"field ['\"]?([\w.]+)['\"]?",
        r"for key ['\"]?([\w.]+)['\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_error, flags=re.IGNORECASE)
        if match:
            return match.group(1).split(".")[-1]
    return None


def _extract_relation_name(raw_error: str) -> Optional[str]:
    patterns = [
        r"relation ['\"]?([\w.]+)['\"]?",
        r"table ['\"]?([\w.]+)['\"]?",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_error, flags=re.IGNORECASE)
        if match:
            return match.group(1).split(".")[-1]
    return None


def _clean_raw_message(raw_error: str) -> str:
    first_line = raw_error.splitlines()[0].strip()
    prefixes = (
        "Query execution failed:",
        "(pymysql.err.integrityerror)",
        "(sqlalchemy.exc.integrityerror)",
    )
    cleaned = first_line
    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    return cleaned.rstrip(".")
