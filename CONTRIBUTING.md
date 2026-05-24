# Contributing

Thanks for helping improve UAMS.

## Development Setup

```bash
git clone https://github.com/Shivamsharma6/unified_memory.git
cd unified_memory
./install.sh
```

Run checks:

```bash
memory_watcher/.venv/bin/python -m pytest memory_watcher/tests memory_watcher/api/tests -q
memory_watcher/.venv/bin/pip check
./uams doctor
```

## Pull Request Guidelines

- Keep changes focused and small.
- Add or update tests for behavior changes.
- Do not commit logs, caches, embeddings, private vault notes, or generated HTML.
- Follow `AGENTS.md` for memory notes and examples.
- Keep default services local-first unless a change explicitly adds secure remote deployment support.

## Adapter Contributions

New agent adapters should:

- use MCP when possible,
- retrieve context before work,
- store distilled memory after durable work,
- avoid raw transcript storage,
- include a minimal setup example and test.
