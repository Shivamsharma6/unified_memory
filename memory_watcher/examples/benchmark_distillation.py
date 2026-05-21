import sys
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
sys.path.append(str(Path(__file__).parent.parent))

from intelligence.distiller import MemoryDistiller

def run_benchmark():
    print("=== AUTONOMOUS MEMORY DISTILLATION BENCHMARK ===\n")
    
    # Setup temporary vault for benchmark
    base_dir = Path(__file__).parent.parent / "test_vault"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    # Create raw memories with different ages and characteristics
    now = datetime.now()
    daily_dir = base_dir / "Daily"
    daily_dir.mkdir(parents=True)
    
    # 1. Old, low-value memory -> Should Archive
    old_date = (now - timedelta(days=20)).strftime("%Y-%m-%d")
    (daily_dir / "old_lunch.md").write_text(f"""---
date: {old_date}
lifecycle: raw
---
I had a sandwich for lunch. It was okay. No coding done this afternoon.""")

    # 2. Medium-aged, standard memory -> Should Summarize
    mid_date = (now - timedelta(days=5)).strftime("%Y-%m-%d")
    (daily_dir / "mid_meeting.md").write_text(f"""---
date: {mid_date}
lifecycle: raw
---
Meeting with the team. We discussed the timeline for the new API. It will take 2 weeks. Need to ensure [[FastAPI]] is updated. John mentioned we should check the CORS settings. Overall productive.""")

    # 3. Very important, dense memory -> Should Promote & Proceduralize
    # Lots of entities = high density.
    recent_date = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    (daily_dir / "critical_bug.md").write_text(f"""---
date: {recent_date}
lifecycle: raw
importance: 0.8
---
Major error in production! The [[Docker]] container crashed because [[Qdrant]] ran out of memory. 
We need to set memory limits in the [[docker-compose.yml]]. 
Step 1: Open compose file. 
Step 2: Add mem_limit: 2g. 
Step 3: Restart services.
This fixes the [[ConnectionError]]!""")

    # Initialize and run distiller
    distiller = MemoryDistiller(str(base_dir))
    distiller.distill_cycle()
    
    print("\n--- RESULTS OF DISTILLATION CYCLE ---")
    
    # Check Archive
    archive_dir = base_dir / "Archive"
    print(f"\n[ARCHIVE FOLDER]")
    for f in archive_dir.glob("*.md"):
        print(f" Moved to archive: {f.name}")
        
    # Check Daily
    print(f"\n[DAILY FOLDER]")
    for f in daily_dir.glob("*.md"):
        content = f.read_text()
        state = [line for line in content.split('\n') if 'lifecycle:' in line][0]
        print(f" {f.name} -> {state}")
        if "summarized" in state:
            print("   (Note was rewritten with a summary at the top)")
        if "distilled" in state:
            print("   (Note was marked as distilled and linked to a procedure)")
            
    # Check Procedures
    proc_dir = base_dir / "Tasks"
    print(f"\n[PROCEDURES FOLDER]")
    for f in proc_dir.glob("*.md"):
        print(f" Created new procedure: {f.name}")
        print(" Content extract:")
        lines = f.read_text().split('\n')
        for line in lines[7:11]: # Print the lessons
            print(f"   {line}")
            
    # Cleanup
    shutil.rmtree(base_dir)

if __name__ == "__main__":
    run_benchmark()
