import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from pipelines.ingestion import IngestionPipeline


def iter_markdown_files(vault_root: Path):
    ignored_parts = {".git", ".venv", "venv", "memory_watcher"}
    for path in vault_root.rglob("*.md"):
        if ignored_parts.intersection(path.parts):
            continue
        yield path


async def main():
    vault_root = Path(__file__).resolve().parents[2]
    pipeline = IngestionPipeline()
    await pipeline.initialize()

    files = list(iter_markdown_files(vault_root))
    print(f"Indexing {len(files)} markdown files from {vault_root}...")
    for path in files:
        await pipeline.process_file(str(path))

    print("Vault indexing complete.")


if __name__ == "__main__":
    asyncio.run(main())
