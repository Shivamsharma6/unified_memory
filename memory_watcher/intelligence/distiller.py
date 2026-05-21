import logging
import os
import re
import yaml
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryDistiller:
    """
    Autonomous Memory Intelligence Engine.
    Handles the lifecycle: raw -> summarized -> distilled -> proceduralized
    """
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.daily_dir = self.vault_path / "Daily"
        self.concepts_dir = self.vault_path / "Concepts"
        self.procedures_dir = self.vault_path / "Tasks"
        self.archive_dir = self.vault_path / "Archive"
        
        # Ensure dirs exist
        for d in [self.daily_dir, self.concepts_dir, self.procedures_dir, self.archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _parse_file(self, filepath: Path) -> Dict[str, Any]:
        """Parse frontmatter and content."""
        if not filepath.exists(): return {}
        content = filepath.read_text(encoding="utf-8")
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL | re.MULTILINE)
        
        if match:
            try:
                fm = yaml.safe_load(match.group(1)) or {}
                return {"frontmatter": fm, "content": match.group(2).strip(), "path": filepath}
            except yaml.YAMLError:
                pass
        return {"frontmatter": {}, "content": content, "path": filepath}

    def _write_file(self, filepath: Path, frontmatter: dict, content: str):
        """Write back to vault with frontmatter."""
        fm_str = yaml.dump(frontmatter, sort_keys=False)
        filepath.write_text(f"---\n{fm_str}---\n{content}", encoding="utf-8")

    def _calculate_importance(self, frontmatter: dict, content: str, age_days: int) -> float:
        """Score based on entities, backlinks, and age."""
        base = frontmatter.get("importance", 0.5)
        entities = len(re.findall(r'\[\[(.*?)\]\]', content))
        entity_boost = min(entities * 0.05, 0.3)
        decay = 0.5 ** (age_days / 30.0)
        score = (base + entity_boost) * decay
        return max(0.0, min(score, 1.0))

    def _extract_lessons(self, content: str) -> List[str]:
        """Mock LLM extraction of lessons/procedures from raw text."""
        lessons = []
        if "error" in content.lower() or "fail" in content.lower():
            lessons.append("Identified error pattern requiring structural patch.")
        if "docker" in content.lower():
            lessons.append("Docker environments require port mapping verification.")
        if "step" in content.lower():
            lessons.append("Sequence of operations detected.")
        return lessons

    def _generate_summary(self, content: str) -> str:
        """Mock LLM summarization."""
        sentences = [s for s in re.split(r'(?<=[.!?])\s+', content) if s]
        if len(sentences) <= 2:
            return content
        return f"{sentences[0]} ... [Distilled] ... {sentences[-1]}"

    def distill_cycle(self):
        """
        Run the autonomous distillation loop.
        Scans raw daily logs, scores them, ages them, and promotes them.
        """
        logger.info("Starting Autonomous Memory Distillation Cycle...")
        now = datetime.now()
        
        for file in self.daily_dir.glob("*.md"):
            if file.name == "README.md": continue
            
            doc = self._parse_file(file)
            fm = doc["frontmatter"]
            content = doc["content"]
            
            # Determine Age
            date_val = fm.get("date", now.strftime("%Y-%m-%d"))
            if isinstance(date_val, date) and not isinstance(date_val, datetime):
                doc_date = datetime.combine(date_val, datetime.min.time())
            elif isinstance(date_val, datetime):
                doc_date = date_val
            else:
                try:
                    doc_date = datetime.strptime(str(date_val), "%Y-%m-%d")
                except ValueError:
                    doc_date = now
                
            age_days = (now - doc_date).days
            state = fm.get("lifecycle", "raw")
            
            importance = self._calculate_importance(fm, content, age_days)
            logger.info(f"Evaluating {file.name} | State: {state} | Age: {age_days}d | Score: {importance:.2f}")
            
            # A. Archive low-value old memories
            if age_days > 14 and importance < 0.3 and state in ["raw", "summarized"]:
                logger.info(f"  -> Archiving {file.name} (Low value, aged)")
                new_path = self.archive_dir / file.name
                file.rename(new_path)
                fm["lifecycle"] = "archived"
                self._write_file(new_path, fm, content)
                continue
                
            # B. Summarize aging raw memories
            if age_days > 2 and state == "raw":
                logger.info(f"  -> Summarizing {file.name} (Aging raw memory)")
                summary = self._generate_summary(content)
                fm["lifecycle"] = "summarized"
                fm["importance"] = importance
                self._write_file(file, fm, f"# Distilled Summary\n{summary}\n\n## Raw Logs\n{content}")
                
            # C. Promote highly important memories to Procedural/Conceptual
            if importance >= 0.75 and state in ["raw", "summarized"]:
                logger.info(f"  -> Distilling & Promoting {file.name} to Procedural Knowledge!")
                
                lessons = self._extract_lessons(content)
                lessons_text = "\n".join([f"- {l}" for l in lessons])
                
                proc_name = f"PROC_{file.stem.replace('-', '_')}.md"
                proc_path = self.procedures_dir / proc_name
                
                proc_fm = {
                    "type": "procedural",
                    "lifecycle": "proceduralized",
                    "origin": f"[[{file.stem}]]",
                    "date": now.strftime("%Y-%m-%d")
                }
                
                proc_content = f"# Extracted Procedure\n\n## Lessons Learned\n{lessons_text}\n\n## Context\nGenerated autonomously from [[{file.stem}]]."
                self._write_file(proc_path, proc_fm, proc_content)
                
                fm["lifecycle"] = "distilled"
                fm["distilled_to"] = f"[[{proc_path.stem}]]"
                self._write_file(file, fm, content)
