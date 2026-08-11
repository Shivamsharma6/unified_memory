import asyncio
import logging
import time
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from intelligence.distiller import MemoryDistiller
from pipelines.reconciliation import EXCLUDED_DIRECTORIES, Reconciler
from pipelines.vector_worker import VectorWorker
from storage.postgres_store import PostgresStore

logger = logging.getLogger(__name__)

class MemoryEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        queue: asyncio.Queue,
        loop: asyncio.AbstractEventLoop,
        vault_root: str | Path,
    ):
        self.queue = queue
        self.loop = loop
        self.vault_root = Path(vault_root).resolve()

    def is_valid_file(self, path: str) -> bool:
        p = Path(path).resolve(strict=False)
        if p.suffix != '.md': return False
        try:
            relative = p.relative_to(self.vault_root)
        except ValueError:
            return False
        if any(part.startswith('.') or part in EXCLUDED_DIRECTORIES for part in relative.parts):
            return False
        if ".backup-" in p.name:
            return False
        return True

    def _enqueue(self, path: str) -> None:
        if self.is_valid_file(path):
            asyncio.run_coroutine_threadsafe(self.queue.put(path), self.loop)

    def on_modified(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_created(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            self._enqueue(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            self._enqueue(event.dest_path)
            self._enqueue(event.src_path)

class MemoryWatcher:
    def __init__(self, target_dir: str, store=None, reconciler=None, vector_worker=None):
        self.target_dir = target_dir
        self.store = store or PostgresStore()
        self.reconciler = reconciler or Reconciler(target_dir, self.store)
        self.vector_worker = vector_worker or VectorWorker(self.store)
        self.queue = asyncio.Queue()
        self.pending = {}
        self.retry_counts = {}
        self.debounce_seconds = 2.0
        self.max_event_retries = int(os.getenv("UAMS_RECONCILE_EVENT_RETRIES", "3"))
        self.reconcile_interval = int(os.getenv("UAMS_RECONCILE_INTERVAL", "300"))
        self._files_since_distill = 0
        self._distill_interval = int(os.getenv("UAMS_DISTILL_INTERVAL", "10"))  # files between distill cycles
        vault_path = str(Path(target_dir))
        self._distiller = MemoryDistiller(vault_path=vault_path)

    async def _process_queue(self):
        while True:
            try:
                path = await self.queue.get()
                self.pending[path] = time.time()
            except asyncio.CancelledError:
                break

    async def _debounced_worker(self):
        while True:
            try:
                await asyncio.sleep(1.0)
                now = time.time()
                to_process = []
                
                for path, timestamp in list(self.pending.items()):
                    if now - timestamp > self.debounce_seconds:
                        to_process.append(path)
                        del self.pending[path]

                for path in to_process:
                    result = await self.reconciler.reconcile_path(path)
                    if result.status == "failed":
                        attempt = self.retry_counts.get(path, 0) + 1
                        self.retry_counts[path] = attempt
                        if attempt <= self.max_event_retries:
                            self.pending[path] = time.time() + min(2 ** attempt, 30)
                        logger.error("Reconciliation failed for %s: %s", path, result.error)
                    else:
                        self.retry_counts.pop(path, None)
                        self._files_since_distill += 1

                # Trigger distillation after N files processed
                if self._files_since_distill >= self._distill_interval:
                    self._files_since_distill = 0
                    logger.info(f"Distill cycle triggered after {self._distill_interval} files")
                    try:
                        await self._distiller.distill_cycle()
                    except Exception as e:
                        logger.error(f"Distill cycle failed: {e}")
            except asyncio.CancelledError:
                break

    async def _periodic_reconciliation(self):
        while True:
            try:
                await asyncio.sleep(self.reconcile_interval)
                result = await self.reconciler.scan()
                logger.info(
                    "Periodic reconciliation: discovered=%s staged=%s unchanged=%s failed=%s deleted=%s",
                    result.discovered,
                    result.staged,
                    result.unchanged,
                    result.failed,
                    result.deleted,
                )
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error("Periodic reconciliation failed: %s", error)

    async def start(self):
        await self.store.open()
        await self.store.migrate()
        await self.vector_worker.initialize()
        startup_result = await self.reconciler.startup_reconcile()
        logger.info(
            "Startup reconciliation: discovered=%s staged=%s unchanged=%s failed=%s deleted=%s",
            startup_result.discovered,
            startup_result.staged,
            startup_result.unchanged,
            startup_result.failed,
            startup_result.deleted,
        )
        loop = asyncio.get_running_loop()
        handler = MemoryEventHandler(self.queue, loop, self.target_dir)
        observer = Observer()
        observer.schedule(handler, self.target_dir, recursive=True)
        observer.start()
        
        logger.info(f"Started watching {self.target_dir} for changes...")
        
        queue_task = asyncio.create_task(self._process_queue())
        worker_task = asyncio.create_task(self._debounced_worker())
        periodic_task = asyncio.create_task(self._periodic_reconciliation())
        vector_task = asyncio.create_task(self.vector_worker.run_forever())
        
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Graceful shutdown initiated...")
            observer.stop()
            observer.join()
            queue_task.cancel()
            worker_task.cancel()
            periodic_task.cancel()
            vector_task.cancel()
            await asyncio.gather(
                queue_task,
                worker_task,
                periodic_task,
                vector_task,
                return_exceptions=True,
            )
            await self._distiller.shutdown()
            await self.store.close()
