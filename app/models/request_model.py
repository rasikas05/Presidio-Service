from pydantic import BaseModel, Field
from typing import List, Optional

class TextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    analyzer_results: Optional[List[dict]] = None
