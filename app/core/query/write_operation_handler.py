"""Handler for intelligent write operations with user confirmation."""

from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text
import re
import json

from app.core.ai.ollama_client import get_ollama_client
from app.core.database.schema_inspector import SchemaInspector
from app.exceptions import QueryExecutionError
from app.utils.logger import get_logger

logger = get_logger(__name__)


class WriteOperationHandler:
    """
    Handles write operations with:
    - Intelligent user matching
    - Impact preview
    - Confirmation workflow
    """

    def __init__(self):
        self.ai_client = get_ollama_client()
        self.schema_inspector = SchemaInspector()

    async def handle_delete_user(
        self,
        question: str,
        connection: AsyncConnection
    ) -> Dict[str, Any]:
        """
        Handle user deletion request with confirmation workflow.

        Returns:
            {
                "phase": "matching" | "confirmation" | "completed",
                "matches": [...],  # List of matching users
                "impact": {...},   # Cascade analysis
                "requires_confirmation": bool,
                "message": str
            }
        """
        # Step 1: Generate WHERE clause using AI
        where_clause = await self._generate_where_clause(question, connection)

        # Step 2: Find matching users
        matches = await self._find_matching_users(where_clause, connection)

        # Step 3: Handle match count
        if len(matches) == 0:
            return {
                "phase": "error",
                "matches": [],
                "message": f"No users found matching '{question}'"
            }

        elif len(matches) == 1:
            # Single match - analyze impact
            user = matches[0]
            impact = await self._analyze_cascade_impact(user['id'], connection)

            return {
                "phase": "confirmation",
                "matches": matches,
                "impact": impact,
                "requires_confirmation": True,
                "message": f"Found 1 user. This will delete {impact['total_records']} total records."
            }

        else:
            # Multiple matches - ask user to choose
            return {
                "phase": "disambiguation",
                "matches": matches,
                "message": f"Found {len(matches)} users. Please specify which one:",
                "requires_selection": True
            }

    async def handle_batch_delete_users(
        self,
        question: str,
        connection: AsyncConnection
    ) -> Dict[str, Any]:
        """
        Handle batch user deletion with extra safety checks.

        Returns preview of ALL matching users before execution.
        """
        # Generate WHERE clause
        where_clause = await self._generate_where_clause(question, connection)

        # Find all matching users (no LIMIT for batch preview)
        query = f"""
            SELECT
                id, username, email, full_name,
                created_at, is_active
            FROM users
            {where_clause}
        """

        result = await connection.execute(text(query))
        matches = [dict(row._mapping) for row in result.fetchall()]

        if len(matches) == 0:
            return {
                "phase": "error",
                "matches": [],
                "message": "No users found matching criteria"
            }

        # Analyze total cascade impact across all users
        total_orders = 0
        total_items = 0
        user_impacts = []

        for user in matches:
            impact = await self._analyze_cascade_impact(user['id'], connection)
            total_orders += impact['orders_count']
            total_items += impact['order_items_count']
            user_impacts.append({
                "user_id": user['id'],
                "username": user['username'],
                "orders": impact['orders_count'],
                "items": impact['order_items_count']
            })

        total_records = len(matches) + total_orders + total_items

        return {
            "phase": "batch_confirmation",
            "matches": matches,
            "batch_size": len(matches),
            "total_cascade_impact": {
                "users_count": len(matches),
                "orders_count": total_orders,
                "items_count": total_items,
                "total_records": total_records,
                "user_impacts": user_impacts
            },
            "requires_batch_confirmation": True,
            "message": f"BATCH DELETE: {len(matches)} users, {total_records} total records",
            "safety_warning": "This will permanently delete multiple users and all their data."
        }

    async def _generate_where_clause(
        self,
        question: str,
        connection: AsyncConnection
    ) -> str:
        """Generate WHERE clause using Ollama."""
        from app.core.ai.prompts import build_write_operation_prompt

        schema = await self.schema_inspector.get_schema_summary(connection)
        prompt = build_write_operation_prompt(
            question=question,
            schema_context=schema,
            database_type="PostgreSQL",
            available_extensions=[]  # Don't allow any extensions
        )

        response = await self.ai_client.generate_content(prompt)

        # Extract WHERE clause
        match = re.search(r'WHERE\s+(.*?)(?:```|$)', response, re.IGNORECASE | re.DOTALL)
        if match:
            where_clause = "WHERE " + match.group(1).strip()
            # Remove trailing explanation if present
            where_clause = where_clause.split('\n')[0].strip()
            return where_clause
        else:
            raise QueryExecutionError("Failed to generate WHERE clause")

    async def _find_matching_users(
        self,
        where_clause: str,
        connection: AsyncConnection
    ) -> List[Dict[str, Any]]:
        """Execute SELECT to find matching users."""
        query = f"""
            SELECT
                id,
                username,
                email,
                full_name,
                created_at,
                is_active
            FROM users
            {where_clause}
            LIMIT 10
        """

        result = await connection.execute(text(query))
        rows = result.fetchall()

        return [dict(row._mapping) for row in rows]

    async def _analyze_cascade_impact(
        self,
        user_id: int,
        connection: AsyncConnection
    ) -> Dict[str, Any]:
        """
        Analyze what will be deleted via CASCADE.

        Returns:
            {
                "user_id": 4,
                "username": "alice_brown",
                "orders_count": 2,
                "order_items_count": 5,
                "total_records": 8,  # 1 user + 2 orders + 5 items
                "details": [...]
            }
        """
        # Count orders
        orders_query = text("SELECT COUNT(*) FROM orders WHERE user_id = :user_id")
        orders_result = await connection.execute(orders_query, {"user_id": user_id})
        orders_count = orders_result.scalar()

        # Count order items (via orders)
        items_query = text("""
            SELECT COUNT(*)
            FROM order_items
            WHERE order_id IN (
                SELECT id FROM orders WHERE user_id = :user_id
            )
        """)
        items_result = await connection.execute(items_query, {"user_id": user_id})
        items_count = items_result.scalar()

        # Get order details
        details_query = text("""
            SELECT
                o.id as order_id,
                o.order_date,
                o.total_amount,
                o.status,
                COUNT(oi.id) as items_in_order
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.user_id = :user_id
            GROUP BY o.id, o.order_date, o.total_amount, o.status
        """)
        details_result = await connection.execute(details_query, {"user_id": user_id})
        order_details = [dict(row._mapping) for row in details_result.fetchall()]

        return {
            "user_id": user_id,
            "orders_count": orders_count,
            "order_items_count": items_count,
            "total_records": 1 + orders_count + items_count,
            "order_details": order_details
        }

    async def _log_to_audit(
        self,
        user_id: int,
        user_data: Dict[str, Any],
        impact: Dict[str, Any],
        connection: AsyncConnection,
        performed_by: str = "api_user"
    ) -> None:
        """Log deletion to audit table before executing."""
        audit_query = text("""
            INSERT INTO audit_log (
                operation_type,
                table_name,
                record_id,
                record_snapshot,
                cascade_impact,
                performed_by
            ) VALUES (
                :operation_type,
                :table_name,
                :record_id,
                :record_snapshot,
                :cascade_impact,
                :performed_by
            )
        """)

        await connection.execute(audit_query, {
            "operation_type": "delete_user",
            "table_name": "users",
            "record_id": user_id,
            "record_snapshot": json.dumps(user_data, default=str),
            "cascade_impact": json.dumps(impact, default=str),
            "performed_by": performed_by
        })

    async def execute_delete_user(
        self,
        user_id: int,
        connection: AsyncConnection,
        performed_by: str = "api_user"
    ) -> Dict[str, Any]:
        """
        Execute confirmed user deletion with audit logging.

        This should be called within a transaction context.
        """
        # Get user data before deletion for audit
        user_query = text("SELECT * FROM users WHERE id = :user_id")
        user_result = await connection.execute(user_query, {"user_id": user_id})
        user_row = user_result.fetchone()

        if not user_row:
            raise QueryExecutionError(f"User {user_id} not found")

        user_data = dict(user_row._mapping)

        # Get cascade impact for audit
        impact = await self._analyze_cascade_impact(user_id, connection)

        # Log to audit table
        await self._log_to_audit(user_id, user_data, impact, connection, performed_by)

        # Execute delete
        delete_query = text("DELETE FROM users WHERE id = :user_id")
        result = await connection.execute(delete_query, {"user_id": user_id})

        deleted_count = result.rowcount

        return {
            "success": True,
            "user_id": user_id,
            "deleted_count": deleted_count,
            "cascade_impact": impact,
            "audit_logged": True
        }
