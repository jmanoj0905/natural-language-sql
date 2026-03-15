"""Prompt templates for SQL generation with Ollama."""

import re
from typing import Optional


def build_sql_generation_prompt(
    question: str,
    schema_context: str,
    database_type: str = "PostgreSQL",
    max_limit: int = 100,
    read_only: bool = False
) -> str:
    """
    Build a prompt for SQL generation using sqlcoder's expected format.
    """
    if read_only:
        constraint = f"Use {database_type} syntax. Only generate SELECT queries. Add LIMIT {max_limit} if none specified."
    else:
        constraint = f"Use {database_type} syntax. Generate exactly the SQL the user is asking for."

    return f"""### Task
Generate a SQL query to answer the following question: `{question}`

{constraint}

### Database Schema
The query will run on a database with the following schema:
{schema_context}

### SQL
Given the database schema, here is the SQL query that answers `{question}`:
```sql"""


def extract_sql_from_response(response: str) -> Optional[str]:
    """Extract SQL query from AI response."""
    if not response or not response.strip():
        return None

    text = response.strip()

    # 1. ```sql ... ``` code block
    match = re.search(r'```sql\s*(.*?)\s*```', text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # 2. Any ``` ... ``` code block
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        if sql.lower().startswith('sql'):
            sql = sql[3:].strip()
        return sql

    # 3. Raw SQL (sqlcoder typically returns just the SQL)
    sql_keywords = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'CREATE', 'ALTER', 'DROP')
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

    # 4. Whole response looks like SQL
    if text.upper().lstrip().startswith(sql_keywords):
        text = text.strip()
        if not text.endswith(';'):
            text += ';'
        return text

    return None


def extract_explanation_from_response(response: str) -> str:
    """Extract explanation from AI response."""
    if not response:
        return "SQL query generated successfully."

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

    return explanation if explanation else "SQL query generated successfully."
