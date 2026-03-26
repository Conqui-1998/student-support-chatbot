from pydantic import BaseModel
from typing import List, Optional

class ChatRequest(BaseModel):
    message:str
    
class SourceItem(BaseModel):
    title: str
    url: Optional[str] = None
    category: Optional[str] = None
    content: str
    score: float
    
class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceItem]
    fallback: bool = False
    category: Optional[str] = None
    