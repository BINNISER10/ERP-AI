from fastapi import APIRouter, File, UploadFile, HTTPException

from app.models.schemas import OcrRequest, OcrResponse
from app.services.ocr_engine import OcrEngine

router = APIRouter()
engine = OcrEngine()


@router.post("/invoice", response_model=OcrResponse)
async def parse_invoice(
    file: UploadFile = File(...),
    meta: OcrRequest | None = None,
) -> OcrResponse:
    try:
        return await engine.parse_invoice(file, meta)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
