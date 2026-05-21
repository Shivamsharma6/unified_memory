from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChunkMetadata(BaseModel):
    source_file: str
    headers: List[str] = Field(default_factory=list)
    frontmatter: Dict[str, Any] = Field(default_factory=dict)

class Chunk(BaseModel):
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None

class Document(BaseModel):
    path: str
    raw_content: str
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[Chunk] = Field(default_factory=list)
