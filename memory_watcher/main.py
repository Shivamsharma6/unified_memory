import asyncio
import logging
import signal
import sys
from pathlib import Path
from services.watcher import MemoryWatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    target_dir = str(Path(__file__).parent.parent.absolute())
    watcher = MemoryWatcher(target_dir=target_dir)
    
    # Graceful shutdown setup
    loop = asyncio.get_running_loop()
    main_task = asyncio.create_task(watcher.start())
    
    def handle_signal(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        main_task.cancel()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
        
    try:
        await main_task
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
