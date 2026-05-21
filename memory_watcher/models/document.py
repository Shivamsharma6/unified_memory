from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChunkMetadata(BaseModel):
    chunk_id: str
    source_file: str
    heading_hierarchy: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    timestamps: Dict[str, Any] = Field(default_factory=dict)
    backlinks: List[str] = Field(default_factory=list)
    semantic_category: Optional[str] = None

class Chunk(BaseModel):
    content: str
    metadata: ChunkMetadata
    embedding: Optional[List[float]] = None

class Document(BaseModel):
    path: str
    raw_content: str
    frontmatter: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[Chunk] = Field(default_factory=list)
