"""FastAPI wrapper over the chat path.

  POST /sessions                       (multipart CSV)   -> {session_id, profile, columns}
  POST /sessions/{sid}/chat            {"message": ...}  -> {state, answer, artifacts}
  GET  /sessions/{sid}/artifacts/{name}                  -> the chart PNG
  GET  /health

Sessions are in-memory (one process). Conversation memory + a persistent sandbox are
Phase 8; for now each message is an independent turn over the session's profile + sandbox
+ models. Run with:  uvicorn src.api:app --reload   (from the data_analyst/ directory)
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src.chat import ChatSession
from src.logging_setup import generic, setup_logging
from src.models import get_models
from src.profiler import profile_csv
from src.sandbox import Sandbox

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"

setup_logging()
app = FastAPI(title="CSV Data Analyst")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

_SESSIONS: dict[str, dict] = {}


class ChatIn(BaseModel):
    message: str


def _profile_json(profile, filename: str) -> dict:
    """Serialize a Profile to the frontend's camelCase shape (types.ts Profile)."""
    return {
        "fileName": filename,
        "nRows": profile.n_rows,
        "nCols": profile.n_cols,
        "columns": [
            {"name": c.name, "dtype": c.dtype, "nNull": c.n_null,
             "nUnique": c.n_unique, "samples": c.samples,
             **({"issue": c.issue} if c.issue else {})}
            for c in profile.columns
        ],
    }


@app.post("/sessions")
def create_session(file: UploadFile = File(...)):
    """Upload a CSV -> profile it -> open a session."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{sid}_{file.filename}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        profile = profile_csv(dest)
    except Exception as e:  # noqa: BLE001 — surface any read error to the client
        raise HTTPException(400, f"could not read CSV: {e}")

    _SESSIONS[sid] = {
        "session": ChatSession(profile, Sandbox(data_path=dest), get_models()),
        "artifacts": {},
    }
    generic().info("session %s from %s (%d x %d)", sid, file.filename,
                   profile.n_rows, profile.n_cols)
    return {"session_id": sid, "profile": _profile_json(profile, file.filename or "upload.csv")}


@app.post("/sessions/sample")
def create_sample_session():
    """Open a session on the bundled Telco sample (no upload needed)."""
    csv = PROJECT_ROOT / "data" / "telco_churn.csv"
    if not csv.exists():
        raise HTTPException(404, "sample dataset not found")
    profile = profile_csv(csv)
    sid = uuid.uuid4().hex[:12]
    _SESSIONS[sid] = {
        "session": ChatSession(profile, Sandbox(data_path=csv), get_models()),
        "artifacts": {},
    }
    generic().info("sample session %s (%d x %d)", sid, profile.n_rows, profile.n_cols)
    return {"session_id": sid, "profile": _profile_json(profile, "telco_churn.csv")}


@app.post("/sessions/{sid}/chat")
def chat(sid: str, body: ChatIn):
    """Run one chat turn through the state machine."""
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "unknown session_id")

    end, ctx = sess["session"].ask(body.message)

    artifacts = []
    result = ctx.data.get("exec_result")
    if result and result.artifacts:
        for p in result.artifacts:
            name = Path(p).name
            sess["artifacts"][name] = p
            artifacts.append(name)

    return {
        "state": end.name,
        "answer": ctx.data.get("answer") or end.data.get("reason", ""),
        "artifacts": artifacts,
    }


@app.get("/sessions/{sid}/artifacts/{name}")
def get_artifact(sid: str, name: str):
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(404, "unknown session_id")
    path = sess["artifacts"].get(name)
    if not path or not Path(path).exists():
        raise HTTPException(404, "artifact not found")
    return FileResponse(path)


@app.get("/health")
def health():
    return {"ok": True, "sessions": len(_SESSIONS)}


if __name__ == "__main__":
    # In-process self-test (no server needed) via TestClient.
    from fastapi.testclient import TestClient

    client = TestClient(app)
    csv = PROJECT_ROOT / "data" / "telco_churn.csv"
    with open(csv, "rb") as f:
        r = client.post("/sessions", files={"file": ("telco_churn.csv", f, "text/csv")})
    info = r.json()
    prof = info["profile"]
    print("POST /sessions ->", r.status_code,
          {"session_id": info["session_id"], "nRows": prof["nRows"], "nCols": prof["nCols"]})
    sid = info["session_id"]

    for msg in ["What is the average monthly charge for churned customers?",
                "Show churn count by contract type as a bar chart."]:
        rc = client.post(f"/sessions/{sid}/chat", json={"message": msg})
        print(f"\nPOST /chat  {msg!r} ->", rc.status_code)
        print(" ", rc.json())
