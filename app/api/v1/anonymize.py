import time

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.models.request_model import TextRequest
from app.services.presidio_service import analyze_text, anonymize_text
from app.core.config import settings
from app.core.logging_config import logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

def validate_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("/anonymize")
@limiter.limit("5/minute")
def anonymize(request: Request, body: TextRequest, api_key: str = Depends(validate_api_key)):
    try:
        start_time = time.time()
        logger.info(f"Processing text length: {len(body.text)}")
        result = anonymize_text(body.text)

        end_time = time.time()
        logger.info(f"Processing time: {end_time - start_time:.3f} seconds")
        logger.info("Processing complete")

        return {
            "status": "success",
            "data": {
                "anonymized_text": result
            }
        }

    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal error")

@router.post("/analyze")
@limiter.limit("5/minute")
def analyze(request: Request, body: TextRequest, api_key: str = Depends(validate_api_key)):
    try:
        start_time = time.time()
        logger.info(f"Analyze text length: {len(body.text)}")
        entities = analyze_text(body.text)

        end_time = time.time()
        logger.info(f"Analyze processing time: {end_time - start_time:.3f} seconds")

        return {
            "status": "success",
            "data": {
                "entities": entities
            }
        }

    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Internal error")

