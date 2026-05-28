"""
Memory Consolidation System for UAMS.

Implements periodic consolidation jobs that:
  1. Gather raw/low-value memories
  2. Cluster similar memories
  3. Summarize patterns
  4. Create abstractions
  5. Reduce redundancy
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

from memory_watcher.memory_types.memory_types import MemoryCategory, get_memory_type
from memory_watcher.memory_types.episodic import EpisodicMemory
from memory_watcher.memory_types.scoring import ImportanceScorer

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationResult:
    """Result of a consolidation operation."""
    memories_processed: int
    memories_retained: int
    memories_pruned: int
    clusters_created: int
    abstractions_generated: int
    redundancy_reduced: int
    summary: str = ""

    def __str__(self) -> str:
        return (
            f"ConsolidationResult: processed={self.memories_processed}, "
            f"retained={self.memories_retained}, pruned={self.memories_pruned}, "
            f"clusters={self.clusters_created}, abstractions={self.abstractions_generated}, "
            f"redundancy_reduced={self.redundancy_reduced}"
        )


class MemoryConsolidator:
    """Periodically consolidates raw memories into stable knowledge."""

    def __init__(self, min_importance_for_retention: float = 0.3, max_cluster_size: int = 10, redundancy_threshold: float = 0.8):
        self.min_importance = min_importance_for_retention
        self.max_cluster_size = max_cluster_size
        self.redundancy_threshold = redundancy_threshold
        self.scorer = ImportanceScorer()

    def consolidate(self, memories: List[EpisodicMemory], category: Optional[MemoryCategory] = None) -> ConsolidationResult:
        """Run full consolidation on a batch of memories."""
        if not memories:
            return ConsolidationResult(
                memories_processed=0, memories_retained=0,
                memories_pruned=0, clusters_created=0,
                abstractions_generated=0, redundancy_reduced=0,
            )

        scored = []
        for mem in memories:
            score = self.scorer.score(
                content=mem.summary,
                emotional_state=mem.emotional_state,
                metadata={"mention_count": len(mem.related_memories)},
                category=category,
            )
            scored.append((mem, score))

        clusters = self._cluster_memories(scored)
        abstractions = self._summarize_clusters(clusters)
        pruned, redundancy_count = self._reduce_redundancy(clusters, abstractions)

        total = len(memories)
        pruned_count = sum(len(cluster) - 1 for cluster in pruned)
        retained = total - pruned_count

        return ConsolidationResult(
            memories_processed=total,
            memories_retained=retained,
            memories_pruned=pruned_count,
            clusters_created=len(clusters),
            abstractions_generated=len(abstractions),
            redundancy_reduced=redundancy_count,
            summary=self._build_summary(total, retained, pruned_count, len(clusters), len(abstractions)),
        )

    def _cluster_memories(self, scored: List[Tuple[EpisodicMemory, ImportanceScore]]) -> List[List[Tuple[EpisodicMemory, ImportanceScore]]]:
        """Cluster memories by event_type and key topics."""
        clusters: Dict[str, List[Tuple[EpisodicMemory, ImportanceScore]]] = defaultdict(list)
        for mem, score in scored:
            cluster_key = f"{mem.event_type}:{'|'.join(sorted(mem.participants[:3]))}"
            clusters[cluster_key].append((mem, score))
        result = list(clusters.values())
        result.sort(key=lambda c: len(c), reverse=True)
        return result

    def _summarize_clusters(self, clusters: List[List[Tuple[EpisodicMemory, ImportanceScore]]]) -> List[Dict[str, Any]]:
        """Summarize each cluster into an abstraction."""
        abstractions = []
        for cluster in clusters:
            if not cluster:
                continue
            event_types = set(m.event_type for m, _ in cluster)
            all_participants = set()
            all_tools = set()
            all_lessons = []
            total_importance = 0.0
            for mem, score in cluster:
                all_participants.update(mem.participants)
                if mem.context.platform:
                    all_tools.add(mem.context.platform)
                if mem.outcome.lessons_learned:
                    all_lessons.extend(mem.outcome.lessons_learned)
                total_importance += score.weighted_score
            avg_importance = total_importance / len(cluster)
            abstractions.append({
                "event_types": list(event_types),
                "participants": list(all_participants),
                "tools": list(all_tools),
                "lessons": list(set(all_lessons)),
                "avg_importance": round(avg_importance, 4),
                "count": len(cluster),
                "memory_ids": [m.id for m, _ in cluster],
            })
        return abstractions

    def _reduce_redundancy(self, clusters, abstractions) -> Tuple[List, int]:
        """Reduce redundancy by keeping only the highest-importance memory from each cluster."""
        pruned_clusters = []
        total_pruned = 0
        for cluster in clusters:
            if len(cluster) <= 1:
                pruned_clusters.append(cluster)
                continue
            sorted_cluster = sorted(cluster, key=lambda x: x[1].weighted_score, reverse=True)
            keeper = sorted_cluster[0]
            pruned_clusters.append([keeper])
            for mem, score in sorted_cluster[1:]:
                if keeper[0].id not in mem.related_memories:
                    mem.related_memories.append(keeper[0].id)
                total_pruned += 1
        return pruned_clusters, total_pruned

    def _build_summary(self, total, retained, pruned_count, clusters, abstractions) -> str:
        retention_rate = (retained / max(total, 1)) * 100
        return (
            f"Consolidated {total} memories: retained {retained} "
            f"({retention_rate:.0f}%), pruned {pruned_count}, "
            f"created {clusters} clusters and {abstractions} abstractions."
        )

    def get_low_value_memories(self, memories: List[EpisodicMemory], category: Optional[MemoryCategory] = None) -> List[EpisodicMemory]:
        """Return memories below the importance threshold."""
        threshold = 0.3  # Default threshold for unclassified memories
        if category:
            config = get_memory_type(category)
            threshold = config.min_importance_threshold
        return [mem for mem in memories if mem.importance < threshold]

    def promote_to_concept(self, episodic_memories: List[EpisodicMemory]) -> Optional[Dict[str, Any]]:
        """Promote a cluster of episodic memories into a semantic concept."""
        if len(episodic_memories) < 3:
            return None

        all_lessons = []
        all_tools = set()
        all_participants = set()
        total_importance = 0.0

        for mem in episodic_memories:
            if mem.outcome.lessons_learned:
                all_lessons.extend(mem.outcome.lessons_learned)
            if mem.context.platform:
                all_tools.add(mem.context.platform)
            all_participants.update(mem.participants)
            total_importance += mem.importance

        avg_importance = total_importance / len(episodic_memories)
        lessons_list = list(set(all_lessons))

        return {
            "type": "semantic_concept",
            "source_memories": [m.id for m in episodic_memories],
            "lessons": lessons_list,
            "tools": list(all_tools),
            "participants": list(all_participants),
            "avg_importance": round(avg_importance, 4),
            "count": len(episodic_memories),
            "summary": f"Pattern from {len(episodic_memories)} interactions: {', '.join(lessons_list[:3])}" if lessons_list else "No lessons extracted",
        }
