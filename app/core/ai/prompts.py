"""Prompt templates for SQL generation with Ollama."""

import re
import json
from typing import Optional, List, Dict, Any


def build_sql_generation_prompt(
    question: str,
    schema_context: str,
    database_type: str = "PostgreSQL",
    read_only: bool = False,
    intent_context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build a prompt for SQL generation using sqlcoder's expected format.
    The prompt seeds the model with ```sql so it outputs raw SQL directly.
    The Ollama stop token ``` cuts off before the closing fence.

    Args:
        question: The natural language question
        schema_context: The database schema context
        database_type: Database type (PostgreSQL or MySQL)
        read_only: Whether to restrict to SELECT queries
        intent_context: Optional intent detection context for context-aware prompts

    The user request may be multi-line and may include pasted query results, so we
    avoid wrapping it in inline backticks.
    """
    enforcement = (
        "IMPORTANT: Only use table and column names that exist in the schema below — "
        "never invent or guess names."
    )
    row_guidance = (
        "If the user pasted previous query results, treat them as examples of rows to target. "
        "Do not use UI-only columns like __source_db__ unless they exist in the schema. "
        "Prefer real table columns such as id, email, name, or other business identifiers from those rows."
    )

    # Add context-aware handling based on intent
    context_guidance = ""
    if intent_context:
        intent = intent_context.get("intent", "")

        # Handle complex filter queries
        if intent in ("complex_filter", "compound_read_write"):
            context_guidance = """
### Complex Filter Handling
When the user asks with conditions like "and", "but", "only if", "similar to":
- Break down each condition clearly
- Use AND for conditions that must ALL be true
- Use OR only when explicitly stated
- For "similar to X" patterns, use LIKE with wildcards (e.g., '%clothes%')
- Order conditions logically: primary filter first, then secondary filters
"""

        # Handle aggregation queries
        if intent == "aggregation":
            context_guidance = """
### Aggregation Queries
When the user asks for counts, sums, averages:
- Use appropriate aggregate functions: COUNT(*), SUM(column), AVG(column), MIN(column), MAX(column)
- Always include a GROUP BY clause when aggregating by category
- For "how many" questions, use COUNT(*) with appropriate filters
- Consider using HAVING for filtering aggregated results
"""

        # Handle multi-database reference
        if intent_context.get("database_refs"):
            db_refs = intent_context["database_refs"]
            if len(db_refs) > 1:
                context_guidance += f"""
### Multi-Database Query
The user referenced multiple databases: {", ".join(db_refs)}.
If the user wants to query across multiple databases with different schemas,
generate separate SQL for each database based on their respective schemas.
Separate multiple SQL statements with semicolons (;).
"""

    if read_only:
        constraint = (
            f"Use {database_type} syntax. Only generate SELECT queries. "
            f"{enforcement} {row_guidance}{context_guidance}"
        )
    else:
        constraint = (
            f"Use {database_type} syntax. Generate exactly the SQL the user is asking for. "
            f"If the question asks to both modify data AND view results, output the write "
            f"statement (UPDATE/INSERT/DELETE) followed by a SELECT statement, separated by a "
            f"semicolon on a new line. "
            f"{enforcement} {row_guidance}{context_guidance}"
        )

    return f"""### Task
Generate a SQL query for the user's request.

### User Request
The request may span multiple lines and may include pasted rows from earlier results.
{question}

### Rules
{constraint}
Return SQL only. Do not include prose before the SQL.

### Database Schema
The query will run on a database with the following schema:
{schema_context}

### SQL
```sql"""


def build_sql_correction_prompt(
    question: str,
    schema_context: str,
    failed_sql: str,
    error_message: str,
    database_type: str = "PostgreSQL",
    read_only: bool = False,
) -> str:
    """Build a prompt that asks the model to fix SQL that failed at execution.

    Seeds the response with ```sql so extract_sql_from_response parses the
    output exactly like the generation prompt does.
    """
    constraint = "Only generate SELECT queries. " if read_only else ""
    return f"""### Task
The previous SQL query failed to execute. Fix it.

### User Request
{question}

### Previous SQL (this failed)
{failed_sql}

### Database Error
{error_message}

### Rules
Use {database_type} syntax. {constraint}Only use table and column names that exist in the schema below — never invent or guess names. A "no such column" or "no such table" error usually means a name is misspelled or has the wrong casing; find the correct name in the schema. Return SQL only. Do not include prose before the SQL.

### Database Schema
{schema_context}

### SQL
```sql"""


def _parse_json_response(text: str) -> Optional[dict]:
    """Try to parse a JSON object from the response text."""
    text = text.strip()
    # Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Extract first {...} block (model may wrap in prose)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def extract_sql_from_response(response: str) -> Optional[str]:
    """Extract SQL query from AI response.

    sqlcoder:7b usually returns raw SQL after the seeded ```sql opener, but some
    responses include a short lead-in such as "Here is the SQL query:" before the
    statement. This extractor accepts both forms.
    """
    if not response or not response.strip():
        return None

    text = response.strip()
    sql_keywords = (
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "WITH",
        "CREATE",
        "ALTER",
        "DROP",
    )

    # 1. Raw SQL — a line starts with a SQL keyword (primary path for sqlcoder)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(sql_keywords):
            start_idx = text.index(stripped)
            return _normalize_sql_candidate(text[start_idx:])

    # 2. ```sql ... ``` code block
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return _normalize_sql_candidate(match.group(1).strip())

    # 3. Any ``` ... ``` code block
    match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        if sql.lower().startswith("sql"):
            sql = sql[3:].strip()
        return _normalize_sql_candidate(sql)

    # 4. Prose + SQL on the same line/text, e.g. "Here is the SQL query: DELETE ..."
    keyword_pattern = r"\b(?:SELECT|INSERT|UPDATE|DELETE|WITH|CREATE|ALTER|DROP)\b"
    match = re.search(keyword_pattern, text, re.IGNORECASE)
    if match:
        return _normalize_sql_candidate(text[match.start() :])

    # 5. JSON response (fallback for other models)
    parsed = _parse_json_response(text)
    if parsed and isinstance(parsed, dict):
        for key in ("sql", "query", "sql_query", "statement"):
            if isinstance(parsed.get(key), str) and parsed[key].strip():
                return _normalize_sql_candidate(parsed[key].strip())
        for v in parsed.values():
            if isinstance(v, str) and v.strip().upper().startswith(sql_keywords):
                return _normalize_sql_candidate(v.strip())

    return None


def _normalize_sql_candidate(candidate: str) -> Optional[str]:
    """Trim prose around a SQL candidate and ensure it ends cleanly."""
    if not candidate:
        return None

    sql = candidate.strip().strip("`").strip()

    for marker in ("\nExplanation:", "\n**Explanation", "\nNote:", "\n---"):
        if marker in sql:
            sql = sql[: sql.index(marker)].strip()

    # If prose follows after the SQL statement, keep everything up to the last semicolon.
    if ";" in sql:
        sql = sql[: sql.rfind(";") + 1].strip()
    else:
        sql_lines = [line.rstrip() for line in sql.splitlines() if line.strip()]
        collected = []
        for line in sql_lines:
            upper = line.strip().upper()
            if collected and not upper.startswith(
                (
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "WITH",
                    "FROM",
                    "WHERE",
                    "JOIN",
                    "LEFT",
                    "RIGHT",
                    "INNER",
                    "OUTER",
                    "GROUP",
                    "ORDER",
                    "LIMIT",
                    "VALUES",
                    "SET",
                    "AND",
                    "OR",
                    "RETURNING",
                    "ON",
                    "UNION",
                    "HAVING",
                    "OFFSET",
                )
            ):
                break
            collected.append(line)
        sql = "\n".join(collected).strip()
        if sql and not sql.endswith(";"):
            sql += ";"

    return sql or None


def extract_explanation_from_response(response: str) -> str:
    """Extract explanation from AI response."""
    if not response:
        return ""

    # JSON response (some models return structured output)
    parsed = _parse_json_response(response.strip())
    if (
        parsed
        and isinstance(parsed.get("explanation"), str)
        and parsed["explanation"].strip()
    ):
        explanation = parsed["explanation"].strip()
        if len(explanation) > 500:
            explanation = explanation[:497] + "..."
        return explanation

    # Labelled explanation in the response text
    text_without_code = re.sub(r"```.*?```", "", response, flags=re.DOTALL)
    if "Explanation:" in text_without_code:
        explanation = text_without_code.split("Explanation:", 1)[1].strip()
    elif "**Explanation:**" in text_without_code:
        explanation = text_without_code.split("**Explanation:**", 1)[1].strip()
    else:
        explanation = ""

    explanation = explanation.strip()
    if len(explanation) > 500:
        explanation = explanation[:497] + "..."

    return explanation


def build_explanation(question: str, sql: str) -> str:
    """Build a human-readable explanation from the question and generated SQL.

    sqlcoder only outputs raw SQL — no explanation. This generates one
    from what the user asked and what SQL was produced.
    """
    # Determine the operation type
    upper = sql.strip().upper()
    if upper.startswith("SELECT"):
        action = "Retrieves"
    elif upper.startswith("INSERT"):
        action = "Inserts"
    elif upper.startswith("UPDATE"):
        action = "Updates"
    elif upper.startswith("DELETE"):
        action = "Deletes"
    elif upper.startswith("WITH"):
        action = "Retrieves (using CTE)"
    else:
        action = "Executes"

    # Extract table names from FROM / JOIN / INTO / UPDATE clauses
    tables = []
    for token in re.findall(
        r"(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        sql,
        re.IGNORECASE,
    ):
        t = token.lower()
        if t not in tables and t not in (
            "select",
            "where",
            "set",
            "values",
            "on",
            "and",
            "or",
        ):
            tables.append(t)

    table_part = ", ".join(tables) if tables else "the database"

    return f'{action} data from {table_part} in response to: "{question}"'
