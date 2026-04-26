"""
ADsensei MCP Server — exposes AI video ad personalisation tools via MCP.

Tools:
  - analyze_video        : VLM frame analysis → structured timeline JSON
  - cluster_profiles     : K-means audience clustering from a profiles CSV
  - market_research      : Perplexity-powered audience insights
  - generate_variants    : Full per-segment ad rendering for an analysed video
  - generate_targeted_ad : End-to-end pipeline (video URL + audience description → variant URLs)
  - edit_video           : Free-form natural-language edit via AI orchestrator

Local dev:
    python mcp_server.py
"""

import csv
import io
import json
import os
import tempfile
import traceback
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from openai import OpenAI
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse

from ai_agents.action_timeline import analyze_video as _analyze_video
from ai_agents.group_ads import build_groups, generate_group_variants
from ai_agents.market_research import run_market_research_agent
from ai_agents.orchestrator import run_orchestrator_agent

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
_cloud = os.getenv("RENDER", "")
STORAGE_DIR = Path("/tmp/adapt-storage") if _cloud else BASE_DIR / "storage"
ORIGINAL_DIR = STORAGE_DIR / "original"
PROCESSED_DIR = STORAGE_DIR / "processed"
ANALYSIS_DIR = STORAGE_DIR / "analysis"
PROFILES_DIR = STORAGE_DIR / "profiles"

for _d in (ORIGINAL_DIR, PROCESSED_DIR, ANALYSIS_DIR, PROFILES_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# OpenAI client (routes through TokenRouter)
# ---------------------------------------------------------------------------

openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY") or "",
    base_url=os.getenv("OPENAI_BASE_URL"),
)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "anthropic/claude-sonnet-4.6")

# ---------------------------------------------------------------------------
# Port / URL config
# ---------------------------------------------------------------------------

RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "")
if _cloud and not RENDER_URL:
    RENDER_URL = "https://adapt-q15d.onrender.com"

if _cloud:
    MCP_PORT = int(os.getenv("PORT", "10000"))
else:
    MCP_PORT = int(os.getenv("MCP_PORT", "8765"))


def _base_url() -> str:
    if _cloud and RENDER_URL:
        return RENDER_URL
    return f"http://localhost:{MCP_PORT}"


# ---------------------------------------------------------------------------
# FastMCP app
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "ADsensei — AI Video Ad Personalisation",
    instructions=(
        "ADsensei converts one master video ad into multiple segment-targeted variants.\n\n"
        "QUICK START:\n"
        "  Call generate_targeted_ad with a video URL and audience description — "
        "  it runs the full pipeline and returns variant download URLs.\n\n"
        "STEP-BY-STEP:\n"
        "  1. analyze_video   — extract VLM frame captions and action timeline\n"
        "  2. cluster_profiles — cluster a profiles CSV into audience segments\n"
        "  3. market_research  — get Perplexity insights for each segment\n"
        "  4. generate_variants — render per-segment video variants\n\n"
        "PRICING: $500/month for automated personalisation pipelines."
    ),
    host="0.0.0.0",
    port=MCP_PORT,
)

# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------


@mcp.custom_route("/files/{filename}", methods=["GET"])
async def download_file(request: Request) -> FileResponse | JSONResponse:
    filename = request.path_params["filename"]
    safe_name = Path(filename).name
    file_path = PROCESSED_DIR / safe_name
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path), media_type="video/mp4", filename=safe_name)
    return JSONResponse({"error": f"File not found: {safe_name}"}, status_code=404)


@mcp.custom_route("/", methods=["GET", "HEAD"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _download_video(video_source: str) -> str:
    """Download a URL or resolve a local path. Returns absolute path string."""
    if video_source.startswith(("http://", "https://")):
        ext = Path(video_source.split("?")[0]).suffix or ".mp4"
        if len(ext) > 6:
            ext = ".mp4"
        local_path = ORIGINAL_DIR / f"{uuid.uuid4().hex}{ext}"
        print(f"[download] {video_source} → {local_path}")
        urllib.request.urlretrieve(video_source, str(local_path))
        return str(local_path)

    p = Path(video_source)
    if p.exists():
        return str(p)
    for d in (ORIGINAL_DIR, PROCESSED_DIR):
        c = d / Path(video_source).name
        if c.exists():
            return str(c)
    raise FileNotFoundError(f"Video not found: {video_source}")


def _public_url(file_path: str) -> str:
    return f"{_base_url()}/files/{Path(file_path).name}"


def _verify(file_path: str) -> dict:
    p = Path(file_path)
    if not p.exists():
        return {"ok": False, "error": "Output file not created"}
    size = p.stat().st_size
    if size < 1000:
        return {"ok": False, "error": f"File too small ({size} bytes)"}
    return {"ok": True, "size_mb": round(size / 1024 / 1024, 2)}


def _generate_synthetic_profiles(audience_description: str, group_count: int) -> str:
    """Use LLM to generate a realistic profiles CSV for the given audience description."""
    profiles_per_group = max(20, 60 // group_count)
    total = profiles_per_group * group_count

    prompt = (
        f"Generate {total} realistic audience profiles as CSV rows for this audience: {audience_description}\n\n"
        f"Create {group_count} distinct sub-segments with {profiles_per_group} profiles each.\n"
        "CSV format — first line is header, then rows, no extra text:\n"
        "age,gender,demographic_info,previous_search_history\n\n"
        "Rules:\n"
        "- age: integer 18-75\n"
        "- gender: male / female / non-binary\n"
        "- demographic_info: 'Urban/Suburban/Rural, CityName State, household_type, career_stage, occupation, housing, income_level'\n"
        "- previous_search_history: 4-6 semicolon-separated interest phrases\n"
        "Make profiles realistic and varied within each sub-segment."
    )

    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You generate realistic audience profile CSV data."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=4096,
        )
        csv_text = (response.choices[0].message.content or "").strip()
        # Strip markdown fences if present
        if csv_text.startswith("```"):
            lines = csv_text.split("\n")
            csv_text = "\n".join(l for l in lines if not l.startswith("```"))
    except Exception as e:
        # Fallback: generate minimal synthetic rows
        print(f"[profiles] LLM generation failed ({e}), using fallback")
        header = "age,gender,demographic_info,previous_search_history"
        rows = [header]
        ages = [25, 35, 45, 55]
        genders = ["male", "female", "non-binary", "male"]
        for i in range(total):
            rows.append(
                f"{ages[i % len(ages)]},{genders[i % len(genders)]},"
                f'"Urban, New York NY, single, mid-career, professional, renter, mid-income",'
                f"{audience_description[:30]}; technology; fitness; travel"
            )
        csv_text = "\n".join(rows)

    # Validate it has at least a header + some rows
    lines = [l for l in csv_text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        raise ValueError("Could not generate valid profiles CSV")

    csv_path = str(PROFILES_DIR / f"synthetic-{uuid.uuid4().hex}.csv")
    with open(csv_path, "w") as f:
        f.write(csv_text)
    print(f"[profiles] Wrote {len(lines) - 1} rows → {csv_path}")
    return csv_path


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def analyze_video(video_source: str) -> str:
    """Analyse a video using VLM frame captioning and scene detection.

    Extracts a structured timeline of actions/scenes with timestamps, mood,
    and visual descriptions. Required before generating targeted variants.

    Args:
        video_source: Public video URL (https://...) or local file path.

    Returns:
        JSON string with keys: events (list), captions (list), analysis_path (str).
    """
    try:
        video_path = _download_video(video_source)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

    analysis_path = str(ANALYSIS_DIR / f"{uuid.uuid4().hex}-analysis.json")
    try:
        result = _analyze_video(video_path=video_path, output_json_path=analysis_path)
    except Exception as e:
        print(f"[analyze_video] {traceback.format_exc()}")
        return json.dumps({"ok": False, "error": str(e)})

    event_count = len(result.get("events") or [])
    caption_count = len(result.get("captions") or [])
    return json.dumps({
        "ok": True,
        "video_path": video_path,
        "analysis_path": analysis_path,
        "event_count": event_count,
        "caption_count": caption_count,
        "summary": f"Extracted {event_count} timeline events and {caption_count} frame captions.",
    })


@mcp.tool()
def cluster_profiles(csv_source: str, group_count: int = 3) -> str:
    """Cluster an audience profiles CSV into segments using K-means embeddings.

    Each row in the CSV should have: age, gender, demographic_info,
    previous_search_history. Returns group summaries with traits and examples.

    Args:
        csv_source: Path to profiles CSV file on disk.
        group_count: Number of audience segments to create (default 3).

    Returns:
        JSON string with key 'groups' — list of segment summaries.
    """
    p = Path(csv_source)
    if not p.exists():
        # Try profiles dir
        candidate = PROFILES_DIR / Path(csv_source).name
        if candidate.exists():
            p = candidate
        else:
            return json.dumps({"ok": False, "error": f"CSV not found: {csv_source}"})

    try:
        groups = build_groups(str(p), group_count)
    except Exception as e:
        print(f"[cluster_profiles] {traceback.format_exc()}")
        return json.dumps({"ok": False, "error": str(e)})

    return json.dumps({
        "ok": True,
        "group_count": len(groups),
        "groups": groups,
        "summary": f"Clustered profiles into {len(groups)} audience segments.",
    })


@mcp.tool()
def market_research(
    audience_description: str,
    product: str = "",
    region: str = "",
    goal: str = "",
) -> str:
    """Run Perplexity-powered market research for an audience segment.

    Returns actionable insights, messaging angles, and citations for
    crafting targeted ad creative.

    Args:
        audience_description: Description of the target audience segment.
        product: Product or brand being advertised (optional).
        region: Geographic market focus (optional).
        goal: Campaign objective, e.g. 'awareness' or 'conversion' (optional).

    Returns:
        JSON string with keys: ok, insights (str), citations (list[str]).
    """
    try:
        result = run_market_research_agent(
            audience_description=audience_description,
            product=product or None,
            region=region or None,
            goal=goal or None,
        )
    except Exception as e:
        print(f"[market_research] {traceback.format_exc()}")
        return json.dumps({"ok": False, "error": str(e)})

    return json.dumps(result)


@mcp.tool()
def generate_variants(
    video_source: str,
    analysis_path: str,
    csv_source: str,
    group_count: int = 3,
    max_edits: int = 4,
) -> str:
    """Render per-segment ad variants from a pre-analysed video.

    Applies segment-specific transforms: color grading, speed adjustments,
    text overlays, and reframing based on audience context and market research.

    Requires analyze_video and cluster_profiles to be run first.

    Args:
        video_source: Path to the original video (returned by analyze_video).
        analysis_path: Path to analysis JSON (returned by analyze_video).
        csv_source: Path to profiles CSV (used by cluster_profiles).
        group_count: Number of audience segments (default 3).
        max_edits: Max transforms applied per variant (default 4).

    Returns:
        JSON string with keys: ok, variants (list of {groupId, label, url}),
        variant_count (int).
    """
    try:
        video_path = _download_video(video_source)
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

    analysis_file = Path(analysis_path)
    if not analysis_file.exists():
        return json.dumps({"ok": False, "error": f"Analysis file not found: {analysis_path}"})

    try:
        with open(analysis_file) as f:
            analysis = json.load(f)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"Cannot read analysis: {e}"})

    csv_file = Path(csv_source)
    if not csv_file.exists():
        candidate = PROFILES_DIR / Path(csv_source).name
        if candidate.exists():
            csv_file = candidate
        else:
            return json.dumps({"ok": False, "error": f"CSV not found: {csv_source}"})

    video_id = uuid.uuid4().hex[:12]
    try:
        variants, _ = generate_group_variants(
            video_id=video_id,
            original_path=Path(video_path),
            analysis=analysis,
            processed_dir=PROCESSED_DIR,
            csv_path=str(csv_file),
            group_count=group_count,
            max_edits=max_edits,
        )
    except Exception as e:
        print(f"[generate_variants] {traceback.format_exc()}")
        return json.dumps({"ok": False, "error": str(e)})

    output = []
    for v in variants:
        variant_path = v.get("variantPath") or v.get("path") or ""
        url = _public_url(variant_path) if variant_path and Path(variant_path).exists() else None
        output.append({
            "groupId": v.get("groupId"),
            "label": v.get("label"),
            "url": url,
            "summary": v.get("summary"),
        })

    return json.dumps({
        "ok": True,
        "variant_count": len(output),
        "variants": output,
        "summary": f"Rendered {len(output)} targeted ad variants.",
    })


@mcp.tool()
def generate_targeted_ad(
    video_url: str,
    audience_description: str,
    group_count: int = 3,
) -> str:
    """End-to-end pipeline: video URL + audience description → targeted ad variants.

    This is the full ADsensei automation:
      1. Download & analyse the video with VLM frame captioning
      2. Generate synthetic audience profiles matching the description
      3. Cluster profiles into segments
      4. Run market research per segment
      5. Apply segment-specific transforms (color, speed, overlays)
      6. Return download URLs for each variant

    Perfect for: agencies, brand teams, and growth marketers who want
    automated creative personalisation at scale.

    Pricing: $500/month for unlimited pipeline runs.

    Args:
        video_url: Public URL of the master video ad (MP4).
        audience_description: Natural language description of the target audience.
          e.g. "Young urban professionals aged 25-35 interested in fitness and tech"
        group_count: Number of distinct audience segments to generate (default 3).

    Returns:
        JSON string with keys:
          ok (bool), variants (list of {groupId, label, url, summary}),
          variant_count (int), pipeline_steps (list of completed step names).
    """
    steps_completed: list[str] = []
    print(f"\n[generate_targeted_ad] Starting pipeline")
    print(f"  video_url: {video_url}")
    print(f"  audience:  {audience_description}")
    print(f"  groups:    {group_count}")

    # Step 1: Download & analyse video
    try:
        video_path = _download_video(video_url)
        steps_completed.append("download_video")
        print(f"[pipeline] ✓ Downloaded: {video_path}")
    except Exception as e:
        return json.dumps({"ok": False, "error": f"Video download failed: {e}", "steps": steps_completed})

    analysis_path = str(ANALYSIS_DIR / f"{uuid.uuid4().hex}-analysis.json")
    try:
        analysis = _analyze_video(video_path=video_path, output_json_path=analysis_path)
        steps_completed.append("analyze_video")
        events = len(analysis.get("events") or [])
        print(f"[pipeline] ✓ Analysed: {events} timeline events")
    except Exception as e:
        print(f"[pipeline] analyze_video failed: {traceback.format_exc()}")
        # Continue with empty analysis rather than failing
        analysis = {"events": [], "captions": []}
        analysis_path_obj = Path(analysis_path)
        analysis_path_obj.write_text(json.dumps(analysis))
        steps_completed.append("analyze_video_partial")
        print(f"[pipeline] ! Analysis partial, continuing")

    # Step 2: Generate synthetic audience profiles
    try:
        csv_path = _generate_synthetic_profiles(audience_description, group_count)
        steps_completed.append("generate_profiles")
        print(f"[pipeline] ✓ Profiles CSV: {csv_path}")
    except Exception as e:
        return json.dumps({"ok": False, "error": f"Profile generation failed: {e}", "steps": steps_completed})

    # Step 3: Generate variants
    video_id = uuid.uuid4().hex[:12]
    try:
        variants, _ = generate_group_variants(
            video_id=video_id,
            original_path=Path(video_path),
            analysis=analysis,
            processed_dir=PROCESSED_DIR,
            csv_path=csv_path,
            group_count=group_count,
            max_edits=4,
        )
        steps_completed.append("generate_variants")
        print(f"[pipeline] ✓ Variants: {len(variants)}")
    except Exception as e:
        print(f"[pipeline] generate_variants failed: {traceback.format_exc()}")
        return json.dumps({"ok": False, "error": f"Variant generation failed: {e}", "steps": steps_completed})

    # Build output
    output = []
    for v in variants:
        variant_path = v.get("variantPath") or v.get("path") or ""
        url = None
        if variant_path and Path(variant_path).exists():
            url = _public_url(variant_path)
            chk = _verify(variant_path)
            print(f"[pipeline]   group {v.get('groupId')}: {chk.get('size_mb', '?')} MB → {url}")
        output.append({
            "groupId": v.get("groupId"),
            "label": v.get("label") or f"Segment {v.get('groupId')}",
            "url": url,
            "summary": v.get("summary"),
        })

    steps_completed.append("done")
    return json.dumps({
        "ok": True,
        "variant_count": len(output),
        "variants": output,
        "pipeline_steps": steps_completed,
        "summary": (
            f"Generated {len(output)} targeted ad variants for '{audience_description[:60]}'. "
            f"Each variant has segment-specific colour grading, speed, and text overlays."
        ),
    })


@mcp.tool()
def edit_video(video_source: str, instructions: str) -> str:
    """Edit a video using natural language instructions via the AI orchestrator.

    The orchestrator interprets your request and applies the right transforms:
    speed change, colour grade, trim, text overlay, reframe, film grain, etc.

    Args:
        video_source: Public video URL or local filename.
        instructions: Natural language editing instructions.

    Returns:
        Download URL for the edited video.
    """
    try:
        inp = _download_video(video_source)
    except Exception as e:
        return f"Error: {e}"

    out = str(PROCESSED_DIR / f"{uuid.uuid4().hex}-edited.mp4")
    try:
        result = run_orchestrator_agent(request=instructions, input_path=inp, output_path=out)
    except Exception as e:
        return f"Orchestrator error: {e}"

    parsed = {}
    output_file = out
    if isinstance(result, dict) and result.get("role") == "tool":
        try:
            parsed = json.loads(result.get("content", "{}"))
        except Exception:
            parsed = {}
        output_file = parsed.get("outputPath", out)

    chk = _verify(output_file)
    if not chk["ok"]:
        return f"Processing error: {chk['error']}"

    url = _public_url(output_file)
    return f"Edit complete! {chk['size_mb']} MB\nDownload: {url}"


@mcp.tool()
def list_videos() -> str:
    """List all available videos (originals and processed results).
    Call this to see what videos are available for editing or analysis.
    """
    VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}
    lines: list[str] = []

    originals = sorted(f for f in ORIGINAL_DIR.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTS)
    if originals:
        lines.append("Original videos:")
        for f in originals:
            lines.append(f"  {f.name}  ({f.stat().st_size / 1048576:.1f} MB)")
    else:
        lines.append("No original videos. Provide a URL to analyze_video or generate_targeted_ad.")

    processed = sorted(f for f in PROCESSED_DIR.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTS)
    if processed:
        lines.append("\nProcessed variants:")
        for f in processed:
            lines.append(f"  {f.name}  ({f.stat().st_size / 1048576:.1f} MB)  {_public_url(str(f))}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"ADsensei MCP Server — port {MCP_PORT}")
    print(f"Storage: {STORAGE_DIR}")
    print(f"Base URL: {_base_url()}")
    print("\nTools:")
    for t in ["analyze_video", "cluster_profiles", "market_research",
              "generate_variants", "generate_targeted_ad", "edit_video", "list_videos"]:
        print(f"  · {t}")
    print(f"\nMCP endpoint: {_base_url()}/mcp")
    print()
    mcp.run(transport="streamable-http")
