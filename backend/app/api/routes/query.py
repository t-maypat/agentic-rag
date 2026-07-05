from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.models import QueryRequest, QueryResponse
from app.security.access import public_access
from app.services.agent import answer_question
from app.services.query_cache import query_cache

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def query(payload: QueryRequest, request: Request, response: Response) -> QueryResponse:
    await public_access.enforce_query_access(
        request=request,
        query=payload.query,
        top_k=payload.top_k,
        captcha_token=payload.hcaptcha_token,
    )

    cached = query_cache.get(payload.query, payload.top_k)
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    answer = await run_in_threadpool(answer_question, payload.query, payload.top_k)
    query_cache.set(payload.query, payload.top_k, answer)
    response.headers["X-Cache"] = "MISS"
    return answer
