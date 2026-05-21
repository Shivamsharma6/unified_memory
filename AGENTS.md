# Agent Operating Protocol: Unified Multi-Agent Memory System

This document defines the strict operating procedures for all AI agents (Hermes, OpenClaw, VoiceAI, etc.) reading from and writing to this Unified Memory Vault. 

**Core Directive:** Agents must NEVER dump raw conversations blindly. All memories must be distilled into reusable, atomic, and heavily linked knowledge.

---

## 1. Memory Writing Conventions
- **Distillation over Transcription:** Extract the "why", "what", and "how" from interactions. Discard pleasantries and conversational filler.
- **Atomicity:** One concept, entity, or event per note. If a note covers multiple distinct topics, split it and link them.
- **Mandatory Metadata:** Every note MUST contain a YAML frontmatter block defining its type, tags, aliases, and timestamps.

### Memory Type Examples
**Episodic Memory (Events/Experiences)**
```markdown
---
type: episodic
date: 2026-05-21
entities: ["[[Shivam Sharma]]", "[[Unified Agent Memory]]"]
tags: ["#meeting", "#architecture"]
---
# 2026-05-21 System Architecture Kickoff
Discussed the phase 1 rollout of the [[Unified Agent Memory]] system with [[Shivam Sharma]]. Decision made to use Obsidian as the source of truth.
```

**Semantic Memory (Facts/Concepts)**
```markdown
---
type: semantic
aliases: ["UAMS", "Memory System"]
tags: ["#concept", "#system"]
---
# Unified Agent Memory System
A multi-agent architecture utilizing Markdown files, [[Qdrant]] for embeddings, and a [[Knowledge Graph]]. It acts as a shared brain for [[Hermes]], [[OpenClaw]], and [[VoiceAI]].
```

**Procedural Memory (How-Tos/Rules)**
```markdown
---
type: procedural
tags: ["#protocol", "#git"]
---
# How to Commit to Unified Memory
1. Verify YAML frontmatter is present.
2. Ensure all entities use wikilinks.
3. Run `git commit -m "type(scope): description"`.
```

## 2. Semantic Chunking Rules
- Keep paragraphs short and focused on a single logical block to ensure vector embeddings remain semantically dense.
- Use explicit H2 (`##`) and H3 (`###`) headers. Vector databases and retrieval layers will chunk documents based on these headers.
- Never write a wall of text exceeding 300 words without a structural break.

## 3. Naming Conventions
- **Concepts/Entities:** Use Title Case (e.g., `Unified Agent Memory.md`, `Shivam Sharma.md`).
- **Daily/Episodic Logs:** Use ISO 8601 Date format prefix (e.g., `2026-05-21-Architecture-Sync.md`).
- **Procedural:** Use action-oriented titles (e.g., `Deploying to Production.md`).

## 4. Entity Extraction Conventions
- Heavy use of Obsidian wikilinks: `[[Entity Name]]`.
- When encountering a new noun, project, or person of importance, wrap it in wikilinks immediately, even if the target page does not yet exist.
- Standardize entity types in the YAML frontmatter (e.g., `type: person`, `type: organization`).

## 5. Summary Generation Rules
- Summaries must be actionable and context-rich.
- Structure: Start with a 1-sentence TL;DR, followed by bulleted key decisions or facts, and end with unresolved questions or next actions.
- Remove all conversational context (e.g., "The user asked me to...", "I replied that..."). State facts directly.

## 6. Retrieval Best Practices
- **Hybrid Context:** When retrieving information, agents should seek both the vector similarity (semantic search) and traverse the wikilinks (graph search) to provide grounded answers.
- **Link Hopping:** If an agent retrieves a note that links to `[[Project X]]`, the agent should implicitly consider the context of `Project X` if relevant to the user's prompt.

## 7. Knowledge Graph Conventions
- The Knowledge Graph is constructed via YAML frontmatter and inline wikilinks.
- Use inline properties where applicable for relationship mapping: `[[WorksFor::OpenClaw]]` or simply rely on co-occurrence in the text.
- Maintain a list of standard relationships in the frontmatter if strict triples are needed (e.g., `related_to: ["[[Concept A]]"]`).

## 8. Context Compression Rules
- If a specific conversation or topic spans multiple daily notes, an agent must compress these into a single Semantic or Procedural note in the `Concepts/` or `Projects/` folder, replacing the scattered logs with a backlink.
- Redundant facts must be pruned. If a concept is updated, overwrite the old concept or explicitly mark the evolution (e.g., "Update 2026-05-21: Architecture shifted to include Qdrant").

## 9. Memory Aging Strategy
- **Short-term (Daily):** Raw notes and unrefined thoughts live in `Daily/`.
- **Promotion:** Once a concept or entity is referenced more than twice, it must be extracted from `Daily/` and promoted to `Concepts/`, `People/`, or `Projects/`.
- **Archiving:** Projects that are completed should have their `status: active` changed to `status: archived` in the frontmatter. Do not delete them; just tag them appropriately so they are deprioritized in active retrieval.

## 10. Markdown Formatting Rules
- **Headers:** Use `##` for main sections, `###` for sub-sections. Do not use `#` except for the single document title at the top.
- **Lists:** Prefer bullet points (`-`) for readable, scannable information.
- **Emphasis:** Use `**bold**` for key terms and concepts within a paragraph to aid human skimming.
- **Code:** Use fenced code blocks with language specifiers (e.g., ` ```python `).

---

## 🚫 Anti-Patterns to Avoid

- **The Raw Dump:** Saving a raw transcript of a chat. *(Correction: Extract the decisions and facts into a summary.)*
- **The Orphan Note:** Creating a note without any `[[wikilinks]]` or tags. *(Correction: Ensure every note connects to the broader graph.)*
- **The Naked Note:** Missing YAML frontmatter. *(Correction: Every file MUST start with `---` metadata `---`.)*
- **The Monolith:** A 2,000-word file with no headers. *(Correction: Break it down with H2/H3 tags or split into multiple atomic files.)*
- **Conversational Memory:** Storing memories as "I learned that Shivam likes X." *(Correction: Store as "Shivam prefers X.")*
