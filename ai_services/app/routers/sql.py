import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.models.schemas import SqlQueryRequest, SqlQueryResponse
from app.services.sql_agent import MutationBlockedError, SqlAgent

logger = logging.getLogger(__name__)

router = APIRouter()
agent = SqlAgent()


@router.post("/ask", response_model=SqlQueryResponse)
async def ask_sql(request: SqlQueryRequest) -> SqlQueryResponse:
    try:
        return await agent.run(request.question, schema_filter=request.schema_filter)
    except MutationBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.error("SQL agent configuration/validation error: %s", exc)
        raise HTTPException(status_code=503, detail="SQL agent is not configured correctly.") from exc
    except SQLAlchemyError:
        logger.exception("SQL execution failed against the database")
        raise HTTPException(status_code=502, detail="Database error while executing the query.") from None
    except Exception:
        logger.exception("Unexpected SQL agent failure")
        raise HTTPException(status_code=500, detail="Internal SQL agent error.") from None