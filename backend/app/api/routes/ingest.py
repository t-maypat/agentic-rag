import logging

from fastapi import APIRouter, HTTPException

from app.models import IngestRequest, IngestResponse
from app.services.ingest import ingest_documents


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    try:
        ingested, chunks = ingest_documents(request.paths, request.documents)
        return IngestResponse(ingested=ingested, chunks=chunks)
    except Exception as exc:  # noqa: BLE001
        logging.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
