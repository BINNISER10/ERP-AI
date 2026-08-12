from fastapi import APIRouter, HTTPException

from app.models.schemas import SqlQueryRequest, SqlQueryResponse
from app.services.sql_agent import SqlAgent

router = APIRouter()
agent = SqlAgent()


@router.post("/ask", response_model=SqlQueryResponse)
async def ask_sql(request: SqlQueryRequest) -> SqlQueryResponse:
    try:
        return await agent.run(request.question, schema_filter=request.schema_filter)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
