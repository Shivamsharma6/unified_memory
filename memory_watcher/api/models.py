from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    entities: List[str] = Field(default_factory=list)
    collections: List[str] = Field(default_factory=list)
    min_score: float = 0.7
    compress: bool = True

class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    importance: float
    source_file: str
    entities: List[str]

class SearchResponse(BaseModel):
    query: str
    intent: str
    expanded_entities: List[str]
    results: List[SearchResult]
    context_tokens_used: int

class RememberRequest(BaseModel):
    text: str
    category: str = "episodic"
    tags: List[str] = Field(default_factory=list)

class SummarizeRequest(BaseModel):
    topic: str
    max_tokens: int = 500

class ContextRequest(BaseModel):
    task: str
    max_tokens: int = 2000
