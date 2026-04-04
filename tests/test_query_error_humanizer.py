"""Tests for app.core.query.error_humanizer."""

from app.core.query.error_humanizer import humanize_query_execution_error


class TestHumanizeQueryExecutionError:
    def test_duplicate_insert_uses_record_context(self):
        sql = (
            "INSERT INTO customers (name, email, city, country) "
            "VALUES ('Manoj J', 'manoj@example.com', 'Bangalore', 'IN');"
        )
        error = Exception(
            "duplicate key value violates unique constraint \"customers_name_key\""
        )

        message = humanize_query_execution_error(error, sql)

        assert "Manoj J" in message
        assert "already exists" in message

    def test_missing_required_field_mentions_column(self):
        sql = "INSERT INTO customers (name) VALUES ('Manoj J');"
        error = Exception("null value in column \"email\" violates not-null constraint")

        message = humanize_query_execution_error(error, sql)

        assert message == "Couldn't save this change because the 'email' field is required."

    def test_missing_table_is_humanized(self):
        sql = "SELECT * FROM customer_orders"
        error = Exception('relation "customer_orders" does not exist')

        message = humanize_query_execution_error(error, sql)

        assert "customer_orders" in message
        assert "does not exist" in message
