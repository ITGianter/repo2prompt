"""FastAPI server for repo2prompt web interface.

Provides endpoints for running the pipeline and streaming results via SSE.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .runner import PipelineError, RunParams, run_pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="repo2prompt", version="0.1.0")

# CORS (same-origin, but allow for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Run state management
# ---------------------------------------------------------------------------

@dataclass
class RunState:
    queue: asyncio.Queue[dict[str, Any]]
    cancel: asyncio.Event
    task: asyncio.Task
    started_at: float


active_runs: dict[str, RunState] = {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    path: str = "."
    output: str | None = None
    exclude: list[str] = []
    copy: bool = False
    no_summary: bool = False
    interactive: bool = False
    verbose: int = 0
    log_level: str | None = None
    model: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.3
    max_workers: int = 5
    max_lines: int | None = None
    outline_only: bool = False
    outline_threshold: int | None = None
    show_tokens: bool = False
    token_model: str | None = None


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/api/run")
async def start_run(req: RunRequest) -> dict[str, str]:
    """Start a new pipeline run. Returns a run_id for SSE streaming."""
    run_id = str(uuid.uuid4())
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    cancel = asyncio.Event()

    params = RunParams(
        path=req.path,
        output=req.output,
        exclude=req.exclude,
        copy=req.copy,
        no_summary=req.no_summary,
        interactive=req.interactive,
        verbose=req.verbose,
        log_level=req.log_level,
        model=req.model,
        api_key=req.api_key,
        base_url=req.base_url,
        temperature=req.temperature,
        max_workers=req.max_workers,
        max_lines=req.max_lines,
        outline_only=req.outline_only,
        outline_threshold=req.outline_threshold,
        show_tokens=req.show_tokens,
        token_model=req.token_model,
    )

    task = asyncio.create_task(run_pipeline(params, queue, cancel))

    active_runs[run_id] = RunState(
        queue=queue,
        cancel=cancel,
        task=task,
        started_at=asyncio.get_event_loop().time(),
    )

    # Clean up when done
    task.add_done_callback(lambda _: _cleanup_run(run_id))

    return {"run_id": run_id}


@app.get("/api/stream/{run_id}")
async def stream_events(run_id: str):
    """SSE endpoint for streaming pipeline events."""
    run = active_runs.get(run_id)
    if not run:
        async def not_found():
            yield _sse_event("error", {"type": "error", "msg": "Run not found", "code": "NOT_FOUND"})
        return StreamingResponse(not_found(), media_type="text/event-stream")

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(run.queue.get(), timeout=30.0)
                    yield _sse_event(event["type"], event)
                    if event["type"] in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            yield _sse_event("error", {"type": "error", "msg": "Connection closed", "code": "CANCELLED"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/cancel/{run_id}")
async def cancel_run(run_id: str) -> dict[str, str]:
    """Cancel a running pipeline."""
    run = active_runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.cancel.set()
    return {"status": "cancelling"}


# ---------------------------------------------------------------------------
# Serve frontend static files
# ---------------------------------------------------------------------------

FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the frontend index.html."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)


# Mount static files (CSS, JS)
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format an SSE event."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _cleanup_run(run_id: str) -> None:
    """Remove a completed run from active_runs after a delay."""
    async def _delayed_cleanup():
        await asyncio.sleep(60)  # Keep run data for 60 seconds
        active_runs.pop(run_id, None)

    asyncio.create_task(_delayed_cleanup())
