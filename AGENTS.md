# Agent Operating Protocol for Unified Memory

1. **Role of this Vault:** This is the Canonical Memory Vault for the Unified Agent Memory System. It acts as the single source of truth for both humans and agents.
2. **Read/Write Operations:**
   - Agents must prefer Markdown files for all durable text storage.
   - Updates must be additive where possible. If modifying existing concepts, ensure backlinks are preserved.
3. **Directory Usage:**
   - `Daily/`: For running daily logs or unstructured thought dumping.
   - `AI/AgentMemories/`: For agent-specific long-term persistent states.
   - `AI/Summaries/`: For compressed versions of long texts.
4. **Graph and Embeddings:**
   - Agents should not manually edit binary embeddings or graph databases directly through file writes; rely on the API layer or designated sync tools.
5. **Obsidian Compatibility:**
   - Use standard `[[Wikilinks]]` for internal linking.
   - Frontmatter (YAML) is encouraged for structured metadata (tags, aliases, dates).
