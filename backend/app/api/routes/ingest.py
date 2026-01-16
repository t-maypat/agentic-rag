from fastapi import APIRouter

from app.models import IngestRequest, IngestResponse
from app.services.ingest import ingest_documents


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    ingested, chunks = ingest_documents(request.paths, request.documents)
    return IngestResponse(ingested=ingested, chunks=chunks)
