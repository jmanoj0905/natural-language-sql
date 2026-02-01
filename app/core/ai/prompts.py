"""Prompt templates for SQL generation with Ollama."""

from typing import Optional, List


def build_sql_generation_prompt(
    question: str,
    schema_context: str,
    database_type: str = "PostgreSQL",
    max_limit: int = 100,
    read_only: bool = False
) -> str:
    """
    Build a prompt for SQL generation with Ollama.

    Args:
        question: Natural language question
        schema_context: Database schema information
        database_type: Type of database (PostgreSQL, MySQL, etc.)
        max_limit: Maximum LIMIT value allowed
        read_only: If True, only SELECT queries allowed. If False, allows DELETE/UPDATE/INSERT

    Returns:
        str: Formatted prompt
    """
    if read_only:
        operation_rules = """**Rules:**
1. Generate ONLY SELECT queries (read-only mode)
2. Use proper JOINs when querying multiple tables
3. Include appropriate WHERE clauses for filtering
4. Add a LIMIT clause (maximum {max_limit} rows)
5. Use standard SQL syntax compatible with {database_type}
6. Return valid, executable SQL
7. Use table and column names exactly as shown in the schema
8. Handle NULL values appropriately
9. Use proper date/time functions if needed"""
    else:
        operation_rules = """**Rules:**
1. Generate DELETE, UPDATE, INSERT, or SELECT queries as requested
2. Use standard SQL syntax (no PostgreSQL-specific extensions)
3. Generate the SQL that matches the user's intent exactly
4. For DELETE: DELETE FROM table WHERE condition
5. For UPDATE: UPDATE table SET column = value WHERE condition
6. For INSERT: INSERT INTO table (columns) VALUES (values)
7. Use table and column names exactly as shown in the schema
8. Return valid, executable SQL that does what the user asked

**Important for User Deletions:**
- When deleting a user by name (e.g., "delete alice brown"), treat the ENTIRE name as the username value
- Example: "delete alice brown" → WHERE username = 'alice_brown' (NOT WHERE username = 'alice' AND role = 'brown')
- Example: "delete user john doe" → WHERE username = 'john_doe'
- Use underscores to connect multi-word names unless the schema shows otherwise
- CHECK THE SAMPLE DATA above to see actual username formats and values"""

    prompt = f"""You are an expert SQL query generator. Convert the natural language question into a valid SQL query.

**Database Type:** {database_type}

**Database Schema with Sample Data:**
{schema_context}

IMPORTANT: The schema above includes actual sample rows from each table. Use this sample data to:
- Identify exact values (e.g., if user says "delete alice brown", check if username='alice_brown' exists in sample data)
- Understand data formats (e.g., how names are stored, whether they use underscores)
- Match user input to actual column values
- Generate more accurate WHERE clauses

**Question:** {question}

{operation_rules.format(max_limit=max_limit, database_type=database_type)}

**Response Format:**
Provide your response in exactly this format:

```sql
[Your SQL query here]
```

**Explanation:**
[Brief 1-2 sentence explanation of what the query does and why]

IMPORTANT: The SQL query must be wrapped in a ```sql code block."""

    return prompt


def build_schema_aware_prompt(
    question: str,
    table_names: list,
    database_type: str = "PostgreSQL"
) -> str:
    """
    Build a simplified prompt when full schema is not available.

    Args:
        question: Natural language question
        table_names: List of available table names
        database_type: Type of database

    Returns:
        str: Formatted prompt
    """
    tables_str = ", ".join(table_names)

    prompt = f"""You are an expert SQL query generator for {database_type}.

**Available Tables:** {tables_str}

**Question:** {question}

**Rules:**
1. Generate ONLY SELECT queries
2. Use only the tables listed above
3. Make reasonable assumptions about column names
4. Include appropriate JOINs, WHERE clauses, and ORDER BY if needed
5. Add a LIMIT clause

**Response Format:**
```sql
[Your SQL query here]
```

**Explanation:**
[Brief explanation]"""

    return prompt


def extract_sql_from_response(response: str) -> Optional[str]:
    """
    Extract SQL query from AI response.

    Args:
        response: AI API response text

    Returns:
        str: Extracted SQL query, or None if not found
    """
    # Look for SQL code block
    import re

    # Pattern: ```sql ... ```
    pattern = r'```sql\s*(.*?)\s*```'
    match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)

    if match:
        sql = match.group(1).strip()
        return sql

    # Fallback: Look for any code block
    pattern = r'```\s*(.*?)\s*```'
    match = re.search(pattern, response, re.DOTALL)

    if match:
        sql = match.group(1).strip()
        # Remove "sql" if it's the first word
        if sql.lower().startswith('sql'):
            sql = sql[3:].strip()
        return sql

    # If no code block found, return None
    return None


def extract_explanation_from_response(response: str) -> str:
    """
    Extract explanation from AI response.

    Args:
        response: AI API response text

    Returns:
        str: Extracted explanation
    """
    # Remove code blocks
    import re
    text_without_code = re.sub(r'```.*?```', '', response, flags=re.DOTALL)

    # Look for "Explanation:" section
    if 'Explanation:' in text_without_code:
        explanation = text_without_code.split('Explanation:', 1)[1].strip()
    elif '**Explanation:**' in text_without_code:
        explanation = text_without_code.split('**Explanation:**', 1)[1].strip()
    else:
        # Use the entire text without code as explanation
        explanation = text_without_code.strip()

    # Clean up and limit length
    explanation = explanation.strip()
    if len(explanation) > 500:
        explanation = explanation[:497] + "..."

    return explanation if explanation else "SQL query generated successfully."


def build_write_operation_prompt(
    question: str,
    schema_context: str,
    database_type: str = "PostgreSQL",
    available_extensions: List[str] = []
) -> str:
    """
    Build prompt for write operations (UPDATE, DELETE, INSERT).

    More conservative than read operations - uses only standard SQL.

    Args:
        question: Natural language request
        schema_context: Database schema information
        database_type: Type of database
        available_extensions: List of installed PostgreSQL extensions

    Returns:
        str: Formatted prompt for write operations
    """
    extensions_note = ""
    if available_extensions:
        extensions_note = f"\n**Installed Extensions:** {', '.join(available_extensions)}"

    prompt = f"""You are an expert SQL query generator for WRITE operations. Convert the natural language request into valid SQL.

**Database Type:** {database_type}
{extensions_note}

**CRITICAL CONSTRAINTS:**
1. Use ONLY standard SQL-92 syntax
2. Do NOT use database-specific extension functions (pg_trgm, pg_trgm_lower, uuid_generate, etc.)
3. Use simple pattern matching: LIKE, ILIKE (case-insensitive), = (exact)
4. For user lookup by name, use: WHERE LOWER(username) = LOWER('name') OR username ILIKE '%name%'
5. Return ONLY the WHERE clause for filtering, not the full DELETE/UPDATE statement
6. Be conservative - if uncertain, match fewer records rather than more

**Database Schema:**
{schema_context}

**User Request:** {question}

**Your Task:**
Analyze the request and return a WHERE clause that safely identifies the target records.

**Examples of SAFE matching:**
- WHERE LOWER(username) = 'alice_brown'
- WHERE username ILIKE '%alice%' AND username ILIKE '%brown%'
- WHERE email = 'user@example.com'

**Examples of UNSAFE matching (DO NOT USE):**
- WHERE pg_trgm_lower(username) = 'alice_brown'
- WHERE username ~* 'regex'
- WHERE similarity(username, 'alice') > 0.5

**Response Format:**
```sql
WHERE [your condition here]
```

**Explanation:**
[1-2 sentences explaining the matching logic and what will be selected]

IMPORTANT: The WHERE clause must use only standard SQL. No extensions."""

    return prompt
