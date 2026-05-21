import asyncio
import logging
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pipelines.ingestion import IngestionPipeline

logger = logging.getLogger(__name__)

class MemoryEventHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue, loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop

    def is_valid_file(self, path: str) -> bool:
        p = Path(path)
        if p.suffix != '.md': return False
        if any(part.startswith('.') for part in p.parts): return False
        if 'memory_watcher' in p.parts: return False # Ignore self
        return True

    def on_modified(self, event):
        if not event.is_directory and self.is_valid_file(event.src_path):
            asyncio.run_coroutine_threadsafe(self.queue.put(event.src_path), self.loop)

    def on_created(self, event):
        if not event.is_directory and self.is_valid_file(event.src_path):
            asyncio.run_coroutine_threadsafe(self.queue.put(event.src_path), self.loop)

class MemoryWatcher:
    def __init__(self, target_dir: str):
        self.target_dir = target_dir
        self.pipeline = IngestionPipeline()
        self.queue = asyncio.Queue()
        self.pending = {}
        self.debounce_seconds = 2.0

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
                    # Create a task so processing doesn't block debouncer
                    asyncio.create_task(self.pipeline.process_file(path))
            except asyncio.CancelledError:
                break

    async def start(self):
        loop = asyncio.get_running_loop()
        handler = MemoryEventHandler(self.queue, loop)
        observer = Observer()
        observer.schedule(handler, self.target_dir, recursive=True)
        observer.start()
        
        logger.info(f"Started watching {self.target_dir} for changes...")
        
        queue_task = asyncio.create_task(self._process_queue())
        worker_task = asyncio.create_task(self._debounced_worker())
        
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("Graceful shutdown initiated...")
            observer.stop()
            observer.join()
            queue_task.cancel()
            worker_task.cancel()
