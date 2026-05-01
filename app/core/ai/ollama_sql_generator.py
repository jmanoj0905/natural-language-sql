"""SQL generation using Ollama (Local, FREE, No API keys!)"""

from typing import Tuple, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.ai.ollama_client import generate_with_config
from app.core.ai.prompts import (
    build_sql_generation_prompt,
    extract_sql_from_response,
    extract_explanation_from_response,
    build_explanation,
)
from app.core.ai.query_planner import get_intent_detector
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
        self.schema_inspector = SchemaInspector()
        self.intent_detector = get_intent_detector()

    async def generate_sql(
        self,
        question: str,
        connection: AsyncConnection,
        db_id: str = "default",
        read_only: bool = True,
        registered_dbs: Optional[list] = None,
        provider: str = "ollama",
        model: str = "",
        api_key: str = "",
    ) -> Tuple[str, str]:
        """
        Generate SQL from natural language using Ollama.

        Args:
            question: Natural language question
            connection: Database connection for schema introspection
            db_id: Database identifier
            read_only: Only used to hint the prompt (SELECT-only vs any SQL)
            registered_dbs: List of registered database IDs for intent detection
            provider: AI provider to use for generation
            model: Optional provider-specific model override
            api_key: Optional API key for external providers

        Returns:
            Tuple of (sql, explanation)
        """
        try:
            # Detect query intent for context-aware prompting
            registered_dbs = registered_dbs or []
            query_plan = self.intent_detector.detect_intent(
                question=question, registered_dbs=registered_dbs
            )

            logger.info(
                "intent_detected",
                intent=query_plan.intent.value,
                database_refs=query_plan.database_refs,
                needs_decomposition=query_plan.needs_decomposition,
            )

            # Get full schema context — all tables, all columns, sample data
            schema_context = await self.schema_inspector.get_schema_summary(
                connection,
                db_id=db_id,
                max_tables=50,
                include_sample_data=True,
                sample_rows=3,
            )

            try:
                db_config = get_db_manager().get_database_config(db_id)
                raw_type = db_config.db_type.lower()
                database_type = "MySQL" if raw_type == "mysql" else "PostgreSQL"
            except Exception:
                database_type = "PostgreSQL"

            # Build intent context for context-aware prompts
            intent_context: Dict[str, Any] = {
                "intent": query_plan.intent.value,
                "database_refs": query_plan.database_refs,
                "needs_decomposition": query_plan.needs_decomposition,
            }

            prompt = build_sql_generation_prompt(
                question=question,
                schema_context=schema_context,
                database_type=database_type,
                read_only=read_only,
                intent_context=intent_context,
            )

            if self.settings.LOG_LEVEL.upper() == "DEBUG":
                logger.debug("ollama_prompt_sent", prompt=prompt)

            response = await generate_with_config(
                prompt,
                provider=provider,
                model=model,
                api_key=api_key,
            )

            log_ai_request(
                logger,
                question=question,
                model=model or self.settings.OLLAMA_MODEL,
                success=True,
                provider=provider,
            )

            sql = extract_sql_from_response(response)

            if not sql:
                logger.error("sql_extraction_failed", response=response[:500])
                raise AIParseError(
                    "Failed to extract SQL from Ollama response", response=response
                )

            explanation = extract_explanation_from_response(response)
            if not explanation:
                explanation = build_explanation(question, sql)

            logger.info(
                "sql_generated",
                question=question[:100],
                sql=sql[:200],
                explanation=explanation[:100],
            )

            return sql, explanation

        except AIAPIError:
            log_ai_request(
                logger,
                question=question,
                model=model or self.settings.OLLAMA_MODEL,
                success=False,
                error="Ollama API error",
                provider=provider,
            )
            raise

        except Exception as e:
            logger.error("sql_generation_failed", error=str(e), question=question[:100])
            raise AIAPIError(f"SQL generation failed: {str(e)}")
