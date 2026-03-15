"""SQL generation using Ollama (Local, FREE, No API keys!)"""

from typing import Tuple
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ai.ollama_client import get_ollama_client
from app.core.ai.prompts import (
    build_sql_generation_prompt,
    extract_sql_from_response,
    extract_explanation_from_response,
    build_explanation,
)
from app.core.database.schema_inspector import SchemaInspector
from app.core.database.connection_manager import get_db_manager
from app.config import get_settings
from app.exceptions import AIAPIError, AIParseError
from app.utils.logger import get_logger, log_ai_request

logger = get_logger(__name__)


class SQLGenerator:
    """SQL generation using Ollama local AI."""

    def __init__(self):
        self.settings = get_settings()
        self.ai_client = get_ollama_client()
        self.schema_inspector = SchemaInspector()

    async def generate_sql(
        self,
        question: str,
        connection: AsyncConnection,
        db_id: str = "default",
        read_only: bool = True
    ) -> Tuple[str, str]:
        """
        Generate SQL from natural language using Ollama.

        Args:
            question: Natural language question
            connection: Database connection for schema introspection
            db_id: Database identifier
            read_only: Only used to hint the prompt (SELECT-only vs any SQL)

        Returns:
            Tuple of (sql, explanation)
        """
        try:
            # Get full schema context — all tables, all columns, sample data
            schema_context = await self.schema_inspector.get_schema_summary(
                connection,
                db_id=db_id,
                max_tables=50,
                include_sample_data=True,
                sample_rows=3
            )

            try:
                db_config = get_db_manager().get_database_config(db_id)
                raw_type = db_config.db_type.lower()
                database_type = "MySQL" if raw_type == "mysql" else "PostgreSQL"
            except Exception:
                database_type = "PostgreSQL"

            prompt = build_sql_generation_prompt(
                question=question,
                schema_context=schema_context,
                database_type=database_type,
                max_limit=self.settings.MAX_QUERY_RESULTS,
                read_only=read_only
            )

            if self.settings.LOG_LEVEL.upper() == "DEBUG":
                logger.debug("ollama_prompt_sent", prompt=prompt)

            response = await self.ai_client.generate_content(prompt)

            log_ai_request(
                logger,
                question=question,
                model=self.settings.OLLAMA_MODEL,
                success=True
            )

            sql = extract_sql_from_response(response)

            if not sql:
                logger.error("sql_extraction_failed", response=response[:500])
                raise AIParseError(
                    "Failed to extract SQL from Ollama response",
                    response=response
                )

            explanation = extract_explanation_from_response(response)
            if not explanation:
                explanation = build_explanation(question, sql)

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
