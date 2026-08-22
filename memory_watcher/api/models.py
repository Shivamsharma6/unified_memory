from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    entities: List[str] = Field(default_factory=list)
    collections: List[str] = Field(default_factory=list)
    min_score: float = 0.7
    compress: bool = True
    max_tokens: int = 1500
    memory_types: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    source_agents: List[str] = Field(default_factory=list)
    include_historical: bool = False

class SearchResult(BaseModel):
    chunk_id: str
    text: str
    score: float
    importance: float
    source_file: str
    entities: List[str]
    memory_id: Optional[str] = None
    revision_id: Optional[str] = None
    memory_type: Optional[str] = None
    rank_sources: List[str] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)

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
    source_agent: Optional[str] = None
    project: Optional[str] = None
    distill: bool = False
    importance: Optional[float] = None
    entities: List[str] = Field(default_factory=list)


class SummarizeRequest(BaseModel):
    topic: str
    max_tokens: int = 2048

class ContextRequest(BaseModel):
    task: str
    max_tokens: int = 2000

class ProcedureRequest(BaseModel):
    task: str
