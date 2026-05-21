import re
from typing import List
from models.document import Document, Chunk, ChunkMetadata

class SemanticChunker:
    def chunk(self, doc: Document) -> Document:
        """
        Splits markdown by semantic headers (H2, H3).
        (Basic placeholder logic for expansion)
        """
        # Minimal structural split for now
        paragraphs = doc.raw_content.split('\n\n')
        for i, p in enumerate(paragraphs):
            if not p.strip(): continue
            meta = ChunkMetadata(source_file=doc.path, frontmatter=doc.frontmatter)
            doc.chunks.append(Chunk(content=p.strip(), metadata=meta))
        return doc
