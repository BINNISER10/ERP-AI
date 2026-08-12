"""Text-to-SQL agent with read-only PostgreSQL access and strict mutation blocking.

The agent uses an OpenAI model to translate natural language questions into
PostgreSQL queries, executes them with a read-only role, and returns the
results.
"""
import logging
import re
from typing import Any

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger(__name__)


class MutationBlockedError(Exception):
    """Raised when the generated SQL contains mutating operations."""


class SqlAgent:
    _BLOCKED_KEYWORDS = {
        "insert",
        "update",
        "delete",
        "drop",
        "truncate",
        "create",
        "alter",
        "grant",
        "revoke",
        "exec",
        "execute",
        "call",
        "--",
        ";",
    }

    def __init__(self, database_url: str | None = None, openai_api_key: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        self.openai_api_key = openai_api_key or settings.openai_api_key
        self.model = settings.openai_model
        # Use a readonly PostgreSQL user/role if available. Fallback to the
        # application user, but enforce keyword blocking to prevent writes.
        self.engine: Engine = create_engine(
            self.database_url,
            connect_args={"options": "-c default_transaction_read_only=on"},
            execution_options={"isolation_level": "READ COMMITTED"},
        )

    def _block_mutations(self, sql: str) -> None:
        """Reject any SQL containing mutating or dangerous keywords."""
        normalized = re.sub(r"\s+", " ", sql.lower())
        tokens = set(re.findall(r"\b\w+\b", normalized))
        for keyword in self._BLOCKED_KEYWORDS:
            if keyword in tokens or keyword in normalized:
                raise MutationBlockedError(f"Blocked keyword/operator detected: {keyword}")

    def _get_schema_context(self, schema_filter: list[str] | None) -> str:
        """Collect a minimal read-only schema summary for the prompt."""
        schemas = schema_filter or settings.allowed_schemas.split(",")
        tables: list[dict[str, Any]] = []
        try:
            with self.engine.connect() as conn:
                for schema in schemas:
                    query = text(
                        """
                        SELECT table_name, column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = :schema
                        ORDER BY table_name, ordinal_position
                        """
                    )
                    rows = conn.execute(query, {"schema": schema.strip()}).mappings().all()
                    tables.extend(rows)
        except SQLAlchemyError as exc:
            logger.warning("Could not read schema context: %s", exc)

        # Build a concise schema description.
        grouped: dict[str, list[str]] = {}
        for row in tables:
            table = str(row["table_name"])
            column = f"{row['column_name']} ({row['data_type']})"
            grouped.setdefault(table, []).append(column)

        lines = []
        for table, columns in grouped.items():
            lines.append(f"Table {table}: {', '.join(columns)}")
        return "\n".join(lines)

    async def _generate_sql(self, question: str, schema_context: str) -> str:
        """Call OpenAI GPT-4o to translate the question to a read-only SQL query."""
        if not self.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        prompt = (
            "You are a PostgreSQL expert. Convert the user's question into a "
            "single valid, read-only PostgreSQL SELECT query. "
            "Do not include explanations, comments, or any modifying SQL. "
            "Use only the tables and columns provided in the schema context. "
            "Use ILIKE for case-insensitive text matching. "
            "Limit results to 100 rows when appropriate. "
            "\n\nSchema:\n{schema}\n\nQuestion: {question}\n\nSQL:"
        ).format(schema=schema_context, question=question)

        async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 300,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip().replace("```sql", "").replace("```", "").strip()

    async def run(self, question: str, schema_filter: list[str] | None = None) -> dict[str, Any]:
        """Run the question through the SQL agent and return the results."""
        schema_context = self._get_schema_context(schema_filter)
        sql = await self._generate_sql(question, schema_context)

        # Strict safety checks before execution.
        self._block_mutations(sql)

        rows: list[dict[str, Any]] = []
        columns: list[str] = []
        try:
            with self.engine.connect() as conn:
                # Force read-only at connection level as well.
                conn.execute(text("SET TRANSACTION READ ONLY"))
                result = conn.execute(text(sql))
                columns = list(result.keys())
                rows = [dict(row) for row in result.mappings().all()]
        except SQLAlchemyError as exc:
            logger.error("SQL execution error: %s", exc)
            raise

        return {
            "sql": sql,
            "result": rows,
            "columns": columns,
            "row_count": len(rows),
        }
