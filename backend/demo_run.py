"""
Demo pipeline runner — validates analyze_video + generate_group_variants end-to-end.
Run from backend/: python3.11 demo_run.py
"""

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
DEMO_DIR = BASE_DIR / "storage" / "demo"
PROCESSED_DIR = BASE_DIR / "storage" / "processed"
PROFILES_DIR = BASE_DIR / "storage" / "profiles"

VIDEO_PATH = DEMO_DIR / "video.mp4"
ANALYSIS_PATH = DEMO_DIR / "analysis.json"
CSV_PATH = str(PROFILES_DIR / "demo.csv")
VIDEO_ID = "demo-001"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── Step 1: Video Analysis ─────────────────────────────────────────────────────
print("\n" + "="*60)
print("STEP 1: Analyzing video...")
print("="*60)

from ai_agents.action_timeline import analyze_video

def progress(event, payload):
    print(f"  [{event}] {payload}")

t0 = time.time()
analysis = analyze_video(
    video_path=str(VIDEO_PATH),
    output_json_path=str(ANALYSIS_PATH),
    progress_cb=progress,
)
elapsed = time.time() - t0

print(f"\nAnalysis done in {elapsed:.1f}s")
print(f"Output: {ANALYSIS_PATH}")

descs = analysis.get("perSecondDescriptions", [])
print(f"\nTotal per-second descriptions: {len(descs)}")
print("\nFirst 3 per-second descriptions:")
for i, d in enumerate(descs[:3]):
    print(f"  [{i}s] {d}")

if not ANALYSIS_PATH.exists():
    print("ERROR: analysis.json not created")
    sys.exit(1)

# ── Step 2: Generate Group Variants ───────────────────────────────────────────
print("\n" + "="*60)
print("STEP 2: Generating audience variants (group_count=3)...")
print("="*60)

from ai_agents.group_ads import generate_group_variants

t1 = time.time()
variants, metadata = generate_group_variants(
    video_id=VIDEO_ID,
    original_path=VIDEO_PATH,
    analysis=analysis,
    processed_dir=PROCESSED_DIR,
    csv_path=CSV_PATH,
    group_count=3,
)
elapsed2 = time.time() - t1

print(f"\nVariants generated in {elapsed2:.1f}s")
print(f"Total variants: {len(variants)}")

if not variants:
    print("WARNING: No variants produced — check API key and model availability.")
else:
    print("\nVariant file paths:")
    for v in variants:
        path = v.get("url") or v.get("path") or str(v)
        print(f"  {path}")
        # Confirm file exists
        p = Path(path) if Path(path).is_absolute() else PROCESSED_DIR / path
        exists = "✓" if p.exists() else "✗ MISSING"
        print(f"    → {exists}")

print("\n" + "="*60)
print("DEMO RUN COMPLETE")
print("="*60)
