from fastapi import HTTPException

def internal_error():
    raise HTTPException(status_code=500, detail="Internal server error")
