import pytest

from app.services.sql_agent import MutationBlockedError, SqlAgent


class TestSqlAgent:
    def test_block_mutations_rejects_insert(self):
        agent = SqlAgent(database_url="postgresql://user:pass@localhost/db")
        with pytest.raises(MutationBlockedError):
            agent._block_mutations("INSERT INTO users (name) VALUES ('test')")

    def test_block_mutations_rejects_delete(self):
        agent = SqlAgent(database_url="postgresql://user:pass@localhost/db")
        with pytest.raises(MutationBlockedError):
            agent._block_mutations("DELETE FROM invoices WHERE id = 1")

    def test_block_mutations_allows_select(self):
        agent = SqlAgent(database_url="postgresql://user:pass@localhost/db")
        # Should not raise.
        agent._block_mutations("SELECT * FROM res_partner WHERE name ILIKE '%acme%'")
