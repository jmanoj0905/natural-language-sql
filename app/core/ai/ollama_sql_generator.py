"""SQL generation using Ollama (Local, FREE, No API keys!)"""

from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ai.ollama_client import get_ollama_client
from app.core.ai.prompts import (
    build_sql_generation_prompt,
    extract_sql_from_response,
    extract_explanation_from_response
)
from app.core.database.schema_inspector import SchemaInspector
from app.config import get_settings
from app.exceptions import AIAPIError, AIParseError
from app.utils.logger import get_logger, log_ai_request

logger = get_logger(__name__)


class SQLGenerator:
    """
    SQL generation using Ollama local AI.

    Benefits:
    - Completely FREE
    - No API keys
    - Runs locally
    - Privacy-friendly
    """

    def __init__(self):
        """Initialize SQL generator with Ollama."""
        self.settings = get_settings()
        self.ai_client = get_ollama_client()
        self.schema_inspector = SchemaInspector()

    async def generate_sql(
        self,
        question: str,
        connection: AsyncConnection,
        include_schema: bool = True,
        read_only: bool = True,
        db_id: str = "default"
    ) -> Tuple[str, str]:
        """Generate SQL query from natural language using Ollama."""
        try:
            # Get schema context with sample data
            schema_context = ""
            if include_schema:
                schema_context = await self.schema_inspector.get_schema_summary(
                    connection,
                    db_id=db_id,
                    max_tables=20,
                    include_sample_data=True,
                    sample_rows=3
                )
                logger.debug("schema_context_retrieved_with_samples")

            # Build prompt
            prompt = build_sql_generation_prompt(
                question=question,
                schema_context=schema_context,
                database_type="PostgreSQL",
                max_limit=self.settings.MAX_QUERY_RESULTS,
                read_only=read_only
            )

            logger.debug(
                "prompt_built",
                question=question[:100],
                prompt_length=len(prompt)
            )

            # Call Ollama
            response = await self.ai_client.generate_content(prompt)

            # Log request
            log_ai_request(
                logger,
                question=question,
                model=self.settings.OLLAMA_MODEL,
                success=True
            )

            # Extract SQL and explanation
            sql = extract_sql_from_response(response)

            if not sql:
                logger.error("sql_extraction_failed", response=response[:500])
                raise AIParseError(
                    "Failed to extract SQL from Ollama response",
                    response=response
                )

            explanation = extract_explanation_from_response(response)

            logger.info(
                "sql_generated",
                question=question[:100],
                sql=sql[:200],
                explanation=explanation[:100]
            )

            return sql, explanation

        except AIAPIError:
            log_ai_request(
                logger,
                question=question,
                model=self.settings.OLLAMA_MODEL,
                success=False,
                error="Ollama API error"
            )
            raise

        except Exception as e:
            logger.error(
                "sql_generation_failed",
                error=str(e),
                question=question[:100]
            )
            raise AIAPIError(f"SQL generation failed: {str(e)}")

    async def generate_and_explain(
        self,
        question: str,
        connection: AsyncConnection
    ) -> dict:
        """Generate SQL with detailed response."""
        sql, explanation = await self.generate_sql(question, connection)

        return {
            "sql": sql,
            "explanation": explanation,
            "model": self.settings.OLLAMA_MODEL,
            "temperature": self.settings.OLLAMA_TEMPERATURE
        }
