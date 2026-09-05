import re
import logging
import unicodedata
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
import networkx as nx

from models.memory_record import MemoryRecord

logger = logging.getLogger(__name__)


_WIKILINK_PATTERN = re.compile(r"\[\[(?P<target>[^\]|]+)(?:\|(?P<label>[^\]]+))?\]\]")


def normalize_entity_key(value: str) -> str:
    """Create a stable entity lookup key without changing its display name."""

    normalized = unicodedata.normalize("NFKC", str(value))
    return " ".join(normalized.split()).casefold()


def clean_wikilink(value: Any) -> str:
    if value is None:
        return ""
    while isinstance(value, (list, tuple)):
        if len(value) == 0:
            return ""
        value = value[0]
    cleaned = str(value).strip()
    match = _WIKILINK_PATTERN.fullmatch(cleaned)
    if match:
        cleaned = match.group("target")
    else:
        cleaned = cleaned.strip("[] \t\r\n")
    cleaned = cleaned.split("|", 1)[0].split("#", 1)[0]
    return unicodedata.normalize("NFKC", cleaned).strip()



@dataclass(frozen=True)
class ProjectedEntity:
    canonical_name: str
    normalized_key: str
    entity_type: str = "concept"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectedMention:
    entity_name: str
    normalized_key: str
    surface_text: str
    context: str


@dataclass(frozen=True)
class ProjectedClaim:
    subject: str
    predicate: str
    object: str
    status: str
    confidence: float
    evidence_memory_id: uuid.UUID
    evidence_path: str
    valid_from: str | None = None
    valid_to: str | None = None
    invalidated_by: uuid.UUID | None = None


@dataclass
class MemoryProjection:
    memory_id: uuid.UUID
    entities: list[ProjectedEntity] = field(default_factory=list)
    mentions: list[ProjectedMention] = field(default_factory=list)
    claims: list[ProjectedClaim] = field(default_factory=list)

    def retrieval_claims(self) -> list[ProjectedClaim]:
        return [claim for claim in self.claims if claim.status in {"explicit", "verified"}]


def _predicate(value: str) -> str:
    normalized = normalize_entity_key(value).replace("-", " ")
    return "_".join(normalized.split())


def _context_at(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    return text[line_start:line_end].strip()


def extract_projection(record: MemoryRecord) -> MemoryProjection:
    """Extract mentions and evidenced claims without promoting prose guesses."""
    from datetime import datetime, timezone

    projection = MemoryProjection(memory_id=record.memory_id)
    entities: dict[str, ProjectedEntity] = {}

    valid_from_ts = str(
        record.timestamps.occurred
        or record.timestamps.created
        or record.frontmatter.get("date")
        or datetime.now(timezone.utc).isoformat()
    )

    def add_entity(name: str, *, aliases: list[str] | None = None, entity_type: str = "concept") -> str:
        canonical = clean_wikilink(name)
        key = normalize_entity_key(canonical)
        if not key:
            return key
        current = entities.get(key)
        merged_aliases = tuple(
            dict.fromkeys(
                [*(current.aliases if current else ()), *(clean_wikilink(alias) for alias in aliases or [])]
            )
        )
        entities[key] = ProjectedEntity(
            canonical_name=current.canonical_name if current else canonical,
            normalized_key=key,
            entity_type=current.entity_type if current else entity_type,
            aliases=merged_aliases,
        )
        return key

    add_entity(record.title, aliases=record.aliases, entity_type=record.memory_type)
    for entity in record.entities:
        add_entity(entity)

    for match in _WIKILINK_PATTERN.finditer(record.body):
        entity_name = clean_wikilink(match.group("target"))
        key = add_entity(entity_name)
        projection.mentions.append(
            ProjectedMention(
                entity_name=entity_name,
                normalized_key=key,
                surface_text=(match.group("label") or entity_name).strip(),
                context=_context_at(record.body, match.start(), match.end()),
            )
        )

    related_to = record.frontmatter.get("related_to") or []
    if not isinstance(related_to, list):
        related_to = [related_to]
    for target in related_to:
        object_name = clean_wikilink(target)
        if not object_name:
            continue
        add_entity(object_name)
        projection.claims.append(
            ProjectedClaim(
                subject=record.title,
                predicate="related_to",
                object=object_name,
                status="explicit",
                confidence=1.0,
                evidence_memory_id=record.memory_id,
                evidence_path=record.vault_path,
                valid_from=valid_from_ts,
            )
        )

    for relationship in record.relationships:
        object_name = clean_wikilink(relationship.target)
        if not object_name:
            continue
        add_entity(object_name)
        projection.claims.append(
            ProjectedClaim(
                subject=record.title,
                predicate=_predicate(relationship.predicate),
                object=object_name,
                status=relationship.status,
                confidence=1.0 if relationship.status in {"explicit", "verified"} else 0.5,
                evidence_memory_id=record.memory_id,
                evidence_path=record.vault_path,
                valid_from=valid_from_ts,
            )
        )

    # Extract Dataview-style inline relations: [[predicate::target]] or [predicate:: [[target]]]
    dataview_double = re.compile(r"\[\[(?P<predicate>[a-zA-Z0-9_\-\s]+)::(?P<target>[^\]]+)\]\]")
    dataview_single = re.compile(r"\[(?P<predicate>[a-zA-Z0-9_\-\s]+)::\s*\[\[(?P<target>[^\]]+)\]\]\]")

    existing_claim_triples = {
        (normalize_entity_key(c.subject), _predicate(c.predicate), normalize_entity_key(c.object))
        for c in projection.claims
    }

    for pattern in (dataview_double, dataview_single):
        for match in pattern.finditer(record.body):
            pred_raw = match.group("predicate").strip()
            target_raw = match.group("target").strip()
            pred = _predicate(pred_raw)
            obj_name = clean_wikilink(target_raw)
            if pred and obj_name:
                triple = (normalize_entity_key(record.title), pred, normalize_entity_key(obj_name))
                if triple not in existing_claim_triples:
                    add_entity(obj_name)
                    projection.claims.append(
                        ProjectedClaim(
                            subject=record.title,
                            predicate=pred,
                            object=obj_name,
                            status="explicit",
                            confidence=1.0,
                            evidence_memory_id=record.memory_id,
                            evidence_path=record.vault_path,
                            valid_from=valid_from_ts,
                        )
                    )
                    existing_claim_triples.add(triple)

    projection.entities = list(entities.values())
    return projection

class GraphExtractor:
    """
    Extracts entities and relationships from markdown memories to build a Knowledge Graph.
    """
    def __init__(self):
        self.wikilink_pattern = re.compile(r'\[\[(.*?)\]\]')
        
        # Heuristic relationship detection based on sentence structure around wikilinks
        self.rel_patterns = {
            "uses": re.compile(r'(?:uses|utilizes|leverages)\s+\[\[(.*?)\]\]', re.I),
            "depends_on": re.compile(r'(?:depends on|requires|needs)\s+\[\[(.*?)\]\]', re.I),
            "fixes": re.compile(r'(?:fixes|resolves|patches)\s+\[\[(.*?)\]\]', re.I),
            "caused_by": re.compile(r'(?:caused by|due to)\s+\[\[(.*?)\]\]', re.I),
            "improves": re.compile(r'(?:improves|enhances|optimizes)\s+\[\[(.*?)\]\]', re.I),
            "replaces": re.compile(r'(?:replaces|supersedes|deprecates)\s+\[\[(.*?)\]\]', re.I),
            "references": re.compile(r'(?:see also|references?|mentioned)\s+\[\[(.*?)\]\]', re.I),
        }

        
        self.entity_types = ["project", "person", "technology", "procedure", "issue", "fix", "architecture", "concept"]

    def _infer_entity_type(self, entity: str, context: str) -> str:
        """Simple heuristic to infer entity type from its name or surrounding context."""
        ent_lower = entity.lower()
        if "bug" in ent_lower or "error" in ent_lower or "issue" in ent_lower: return "issue"
        if "fix" in ent_lower or "patch" in ent_lower: return "fix"
        if "architecture" in ent_lower or "system" in ent_lower: return "architecture"
        if "how to" in ent_lower or "step" in ent_lower: return "procedure"
        if entity.istitle() and " " in entity: return "person" # Extremely naive heuristic
        return "concept"

    def extract_from_markdown(self, source_file: str, content: str, frontmatter: dict) -> nx.DiGraph:
        """Build a directed graph of entities and relationships from a single document."""
        G = nx.DiGraph()
        
        # Add the document itself as a node
        doc_node = f"DOC:{source_file}"
        G.add_node(doc_node, type="document", label=source_file)
        
        # Extract explicit frontmatter relations
        if "related_to" in frontmatter:
            related_to = frontmatter["related_to"]
            if not isinstance(related_to, (list, tuple)):
                related_to = [related_to]
            for rel in related_to:
                rel_clean = clean_wikilink(rel)
                if rel_clean:
                    G.add_node(rel_clean, type="concept")
                    G.add_edge(doc_node, rel_clean, relation="related_to")

        # Parse sentences for contextual relationships
        sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', content) if s.strip()]
        
        for sentence in sentences:
            raw_entities = self.wikilink_pattern.findall(sentence)
            if not raw_entities:
                continue
            
            entities_in_sentence = []
            for raw_ent in raw_entities:
                cleaned = clean_wikilink(raw_ent)
                if cleaned and cleaned not in entities_in_sentence:
                    entities_in_sentence.append(cleaned)
                    
            if not entities_in_sentence:
                continue
                
            # Add all entities and link to document
            for ent in entities_in_sentence:
                ent_type = self._infer_entity_type(ent, sentence)
                if not G.has_node(ent):
                    G.add_node(ent, type=ent_type, label=ent)
                G.add_edge(doc_node, ent, relation="references")
                
            # Detect directed relationships between the document (or primary entity) and extracted entities
            for rel_name, pattern in self.rel_patterns.items():
                matches = pattern.findall(sentence)
                for raw_target in matches:
                    target_ent = clean_wikilink(raw_target)
                    if not target_ent:
                        continue
                    # If multiple entities in sentence, assume the first one acts on the target
                    # Else the document acts on the target
                    source_ent = entities_in_sentence[0] if len(entities_in_sentence) > 1 and entities_in_sentence[0] != target_ent else doc_node
                    
                    if not G.has_node(target_ent):
                        G.add_node(target_ent, type=self._infer_entity_type(target_ent, sentence), label=target_ent)
                    
                    G.add_edge(source_ent, target_ent, relation=rel_name)
                    
        return G
