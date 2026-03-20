"""Prompt templates for SQL generation with Ollama."""

import re
import json
from typing import Optional


def build_sql_generation_prompt(
    question: str,
    schema_context: str,
    database_type: str = "PostgreSQL",
    read_only: bool = False
) -> str:
    """
    Build a prompt for SQL generation using sqlcoder's expected format.
    The prompt seeds the model with ```sql so it outputs raw SQL directly.
    The Ollama stop token ``` cuts off before the closing fence.
    """
    enforcement = (
        "IMPORTANT: Only use table and column names that exist in the schema below — "
        "never invent or guess names."
    )
    if read_only:
        constraint = (
            f"Use {database_type} syntax. Only generate SELECT queries. "
            f"{enforcement}"
        )
    else:
        constraint = (
            f"Use {database_type} syntax. Generate exactly the SQL the user is asking for. "
            f"If the question asks to both modify data AND view results, output the write "
            f"statement (UPDATE/INSERT/DELETE) followed by a SELECT statement, separated by a "
            f"semicolon on a new line. "
            f"{enforcement}"
        )

    return f"""### Task
Generate a SQL query to answer the following question: `{question}`

{constraint}

### Database Schema
The query will run on a database with the following schema:
{schema_context}

### SQL
Given the database schema, here is the SQL query that answers `{question}`:
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
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def extract_sql_from_response(response: str) -> Optional[str]:
    """Extract SQL query from AI response.

    sqlcoder:7b returns raw SQL after the seeded ```sql opener — no fences in the
    response itself (the stop token cuts them off). Pattern order prioritises that.
    """
    if not response or not response.strip():
        return None

    text = response.strip()
    sql_keywords = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'CREATE', 'ALTER', 'DROP')

    # 1. Raw SQL — first line starts with a SQL keyword (primary path for sqlcoder)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(sql_keywords):
            start_idx = text.index(stripped)
            raw = text[start_idx:]
            for marker in ('\nExplanation:', '\n**Explanation', '\nNote:', '\n---'):
                if marker in raw:
                    raw = raw[:raw.index(marker)]
            raw = raw.strip()
            if not raw.endswith(';'):
                raw += ';'
            return raw

    # 2. ```sql ... ``` code block
    match = re.search(r'```sql\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 3. Any ``` ... ``` code block
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        if sql.lower().startswith('sql'):
            sql = sql[3:].strip()
        return sql

    # 4. JSON response (fallback for other models)
    parsed = _parse_json_response(text)
    if parsed and isinstance(parsed, dict):
        for key in ("sql", "query", "sql_query", "statement"):
            if isinstance(parsed.get(key), str) and parsed[key].strip():
                return parsed[key].strip()
        for v in parsed.values():
            if isinstance(v, str) and v.strip().upper().startswith(sql_keywords):
                return v.strip()

    return None


def extract_explanation_from_response(response: str) -> str:
    """Extract explanation from AI response."""
    if not response:
        return ""

    # JSON response (some models return structured output)
    parsed = _parse_json_response(response.strip())
    if parsed and isinstance(parsed.get("explanation"), str) and parsed["explanation"].strip():
        explanation = parsed["explanation"].strip()
        if len(explanation) > 500:
            explanation = explanation[:497] + "..."
        return explanation

    # Labelled explanation in the response text
    text_without_code = re.sub(r'```.*?```', '', response, flags=re.DOTALL)
    if 'Explanation:' in text_without_code:
        explanation = text_without_code.split('Explanation:', 1)[1].strip()
    elif '**Explanation:**' in text_without_code:
        explanation = text_without_code.split('**Explanation:**', 1)[1].strip()
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
    if upper.startswith('SELECT'):
        action = 'Retrieves'
    elif upper.startswith('INSERT'):
        action = 'Inserts'
    elif upper.startswith('UPDATE'):
        action = 'Updates'
    elif upper.startswith('DELETE'):
        action = 'Deletes'
    elif upper.startswith('WITH'):
        action = 'Retrieves (using CTE)'
    else:
        action = 'Executes'

    # Extract table names from FROM / JOIN / INTO / UPDATE clauses
    tables = []
    for token in re.findall(
        r'(?:FROM|JOIN|INTO|UPDATE)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        sql, re.IGNORECASE,
    ):
        t = token.lower()
        if t not in tables and t not in (
            'select', 'where', 'set', 'values', 'on', 'and', 'or',
        ):
            tables.append(t)

    table_part = ', '.join(tables) if tables else 'the database'

    return f'{action} data from {table_part} in response to: "{question}"'
