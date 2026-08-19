import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import DocumentHunterResponse, OcrRequest, OcrResponse
from app.services.ocr_engine import OcrEngine

logger = logging.getLogger(__name__)

router = APIRouter()
engine = OcrEngine()


@router.post("/invoice", response_model=OcrResponse)
async def parse_invoice(
    file: UploadFile = File(...),
    meta: OcrRequest | None = None,
) -> OcrResponse:
    try:
        return await engine.parse_invoice(file, meta)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("OCR processing failed")
        raise HTTPException(status_code=500, detail="OCR processing failed.") from None


@router.post("/document-hunter", response_model=DocumentHunterResponse)
async def hunt_business_document(
    file: UploadFile = File(...),
) -> DocumentHunterResponse:
    """Intelligently scan, classify and extract Saudi CR, VAT, GOSI, and National Address documents."""
    try:
        result = await engine.parse_business_document(file)
        return DocumentHunterResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Document Hunter OCR failed")
        raise HTTPException(status_code=500, detail="Document Hunter processing failed.") from None