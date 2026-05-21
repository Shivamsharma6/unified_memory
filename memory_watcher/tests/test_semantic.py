import sys
import unittest
from pathlib import Path

# Add parent dir to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from models.document import Document
from chunkers.semantic import SemanticChunker

class TestSemanticChunker(unittest.TestCase):
    def setUp(self):
        self.chunker = SemanticChunker(max_chunk_size=100)
        
    def test_frontmatter_and_metadata(self):
        md = """---
type: semantic
tags: ["#ai", "#memory"]
date: 2026-05-21
---
# Unified Memory
This connects [[Hermes]] to [[OpenClaw]].
"""
        doc = Document(path="test.md", raw_content=md)
        doc = self.chunker.chunk(doc)
        
        self.assertEqual(len(doc.chunks), 1)
        chunk = doc.chunks[0]
        self.assertEqual(chunk.metadata.semantic_category, "semantic")
        self.assertIn("#ai", chunk.metadata.tags)
        self.assertIn("Hermes", chunk.metadata.entities)
        self.assertEqual(str(chunk.metadata.timestamps["created"]), "2026-05-21")
        self.assertEqual(chunk.metadata.heading_hierarchy, ["Unified Memory"])

    def test_hierarchy_preservation(self):
        md = """# H1
text1
## H2
text2
### H3
text3
## H2-Alt
text4
"""
        doc = Document(path="test.md", raw_content=md)
        doc = self.chunker.chunk(doc)
        
        self.assertEqual(len(doc.chunks), 4)
        self.assertEqual(doc.chunks[0].metadata.heading_hierarchy, ["H1"])
        self.assertEqual(doc.chunks[1].metadata.heading_hierarchy, ["H1", "H2"])
        self.assertEqual(doc.chunks[2].metadata.heading_hierarchy, ["H1", "H2", "H3"])
        self.assertEqual(doc.chunks[3].metadata.heading_hierarchy, ["H1", "H2-Alt"])

    def test_code_block_preservation(self):
        md = """# Code
```python
# A comment
def foo():
    pass
```"""
        doc = Document(path="test.md", raw_content=md)
        doc = self.chunker.chunk(doc)
        self.assertIn("```python", doc.chunks[0].content)
        self.assertIn("def foo():", doc.chunks[0].content)

if __name__ == '__main__':
    unittest.main()
