from fastapi import APIRouter

from app.models import QueryRequest, QueryResponse
from app.services.agent import answer_question


router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    return answer_question(request.query, request.top_k)
