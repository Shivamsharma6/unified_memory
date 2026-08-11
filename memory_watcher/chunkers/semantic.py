import re
import hashlib
import yaml
from pathlib import Path
from typing import List, Dict, Any, Tuple
from models.document import Document, Chunk, ChunkMetadata

class SemanticChunker:
    def __init__(self, max_chunk_size: int = 1500, overlap_size: int = 200):
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        
        # Regex patterns
        self.frontmatter_pattern = re.compile(r'^---\n(.*?)\n---', re.DOTALL | re.MULTILINE)
        self.header_pattern = re.compile(r'^(#{1,6})\s+(.*)')
        self.wikilink_pattern = re.compile(r'\[\[(.*?)\]\]')
        self.tag_pattern = re.compile(r'(?:^|\s)#([a-zA-Z0-9_-]+)')
        
    def _extract_entities(self, text: str) -> List[str]:
        return list(set(self.wikilink_pattern.findall(text)))

    def _extract_tags(self, text: str) -> List[str]:
        return list(set(self.tag_pattern.findall(text)))

    def _generate_chunk_id(self, source: str, hierarchy: List[str], index: int) -> str:
        unique_str = f"{source}::{'|'.join(hierarchy)}::{index}"
        return hashlib.sha256(unique_str.encode()).hexdigest()[:12]

    def _parse_frontmatter(self, raw_content: str) -> Tuple[Dict[str, Any], str]:
        match = self.frontmatter_pattern.search(raw_content)
        if match:
            try:
                fm = yaml.safe_load(match.group(1)) or {}
                return fm, raw_content[match.end():].strip()
            except yaml.YAMLError:
                pass
        return {}, raw_content

    def _split_long_text(self, text: str) -> List[str]:
        """Splits long text by paragraphs with semantic overlap."""
        paragraphs = re.split(r'\n\n+', text)
        chunks = []
        current_chunk = []
        current_size = 0
        
        for p in paragraphs:
            p_len = len(p)
            if current_size + p_len > self.max_chunk_size and current_chunk:
                # Yield current chunk
                joined = "\n\n".join(current_chunk)
                chunks.append(joined)
                
                # Setup next chunk with overlap (keep last paragraph)
                overlap_p = current_chunk[-1]
                current_chunk = [overlap_p, p]
                current_size = len(overlap_p) + len(p)
            else:
                current_chunk.append(p)
                current_size += p_len
                
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
            
        return chunks

    def chunk(self, doc: Document) -> Document:
        frontmatter, content = self._parse_frontmatter(doc.raw_content)
        doc.frontmatter = frontmatter
        
        raw_tags = frontmatter.get("tags", [])
        tag_values = raw_tags if isinstance(raw_tags, list) else [raw_tags]
        doc_tags = list(
            dict.fromkeys(
                str(tag).strip()
                for tag in tag_values
                if tag is not None and str(tag).strip()
            )
        )
        doc_category = frontmatter.get("type", None)
        timestamp_data = frontmatter.get("timestamps", {})
        if not isinstance(timestamp_data, dict):
            timestamp_data = {}
        doc_timestamps = {
            "created": timestamp_data.get("created") or frontmatter.get("date"),
            "updated": timestamp_data.get("updated") or frontmatter.get("updated")
        }
        
        lines = content.split('\n')
        document_title = next(
            (
                match.group(2).strip()
                for line in lines
                if (match := self.header_pattern.match(line)) and len(match.group(1)) == 1
            ),
            Path(doc.path).stem if doc.path else "Memory",
        )
        
        chunks = []
        hierarchy = []
        current_block = []
        in_code_block = False
        chunk_index = 0
        
        def finalize_block():
            nonlocal current_block, chunk_index
            if not current_block: return
            text = "\n".join(current_block).strip()
            if not text: return
            
            # Split if too long, else list of one
            sub_chunks = self._split_long_text(text)
            
            for sub_text in sub_chunks:
                entities = self._extract_entities(sub_text)
                tags = list(dict.fromkeys(doc_tags + self._extract_tags(sub_text)))
                context_hierarchy = list(hierarchy) if hierarchy else [document_title]
                if context_hierarchy[0] != document_title:
                    context_hierarchy.insert(0, document_title)
                context = "\n".join(
                    f"{'#' * min(level, 6)} {heading}"
                    for level, heading in enumerate(context_hierarchy, start=1)
                )
                chunk_content = f"{context}\n\n{sub_text.strip()}"
                
                meta = ChunkMetadata(
                    chunk_id=self._generate_chunk_id(doc.path, context_hierarchy, chunk_index),
                    source_file=doc.path,
                    heading_hierarchy=context_hierarchy,
                    tags=tags,
                    entities=entities,
                    timestamps=doc_timestamps,
                    backlinks=entities, # Simplified: outgoing wikilinks act as local backlinks context
                    semantic_category=doc_category
                )
                chunks.append(Chunk(content=chunk_content, metadata=meta))
                chunk_index += 1
            current_block = []

        for line in lines:
            # Code block toggle
            if line.strip().startswith('```'):
                in_code_block = not in_code_block
                current_block.append(line)
                continue
                
            if in_code_block:
                current_block.append(line)
                continue
                
            # Header processing
            header_match = self.header_pattern.match(line)
            if header_match:
                # Flush previous block
                finalize_block()
                
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                
                # Adjust hierarchy
                if level <= len(hierarchy):
                    hierarchy = hierarchy[:level-1]
                hierarchy.append(title)
            else:
                current_block.append(line)
                
        # Flush final block
        finalize_block()
        
        doc.chunks = chunks
        return doc
