"""FastAPI wrapper over the chat path, with SQLite persistence.

  POST /sessions                       (multipart CSV)   -> {session_id, profile}
  POST /sessions/sample                                   -> {session_id, profile}
  GET  /sessions                       (X-User-Id)        -> [past chats]
  POST /sessions/{sid}/chat            {"message": ...}  -> {state, answer, images, tables}
  GET  /sessions/{sid}/messages                           -> conversation history
  GET  /sessions/{sid}/artifacts/{name}                   -> chart PNG / table CSV
  GET  /health

Sessions + messages persist in data/app.db (SQLite); chart/table files are copied to
data/artifacts/<sid>/ so they survive restarts. A session is rehydrated from the DB on the
first request after a restart (re-profiling the stored CSV, rebuilding conversation memory).
Run with:  uvicorn src.api:app --reload   (from the data_analyst/ directory)
"""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from src import db
from src.chat import ChatSession
from src.logging_setup import generic, setup_logging
from src.models import get_models
from src.profiler import profile_csv
from src.sandbox import Sandbox

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
ARTIFACTS_DIR = PROJECT_ROOT / "data" / "artifacts"

setup_logging()
db.init_db()
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


def _table_json(path, name, max_rows: int = 100) -> dict:
    """Read a generated CSV table into JSON-safe {columns, rows} for the UI."""
    df = pd.read_csv(path)
    payload = json.loads(str(df.head(max_rows).to_json(orient="split")))
    return {
        "name": name,
        "columns": [str(c) for c in payload["columns"]],
        "rows": payload["data"],
        "totalRows": int(len(df)),
        "truncated": len(df) > max_rows,
    }


def _open_session(sid, profile, csv_path, filename, user_id) -> dict:
    """Create the in-memory ChatSession and persist the session row."""
    _SESSIONS[sid] = {
        "session": ChatSession(profile, Sandbox(data_path=csv_path), get_models()),
        "artifacts": {},
    }
    db.save_session(sid, user_id, filename, csv_path, _profile_json(profile, filename))
    return _SESSIONS[sid]


def _get_or_load(sid) -> dict | None:
    """Return the in-memory session, rehydrating from the DB after a restart."""
    if sid in _SESSIONS:
        return _SESSIONS[sid]
    row = db.get_session(sid)
    if not row:
        return None
    csv = Path(row["csv_path"])
    if not csv.exists():
        raise HTTPException(410, "the data file for this session is no longer available")

    cs = ChatSession(profile_csv(csv), Sandbox(data_path=csv), get_models())
    turn = None
    for m in db.get_messages(sid):  # rebuild conversation memory from stored messages
        if m["role"] == "user":
            turn = {"q": m["text"], "a": "", "code": ""}
            cs.history.append(turn)
        elif turn is not None:
            turn["a"], turn["code"] = m["text"], m.get("code") or ""
            turn = None

    artifacts = {}
    adir = ARTIFACTS_DIR / sid
    if adir.exists():
        for f in adir.iterdir():
            if f.is_file():
                artifacts[f.name] = str(f)

    _SESSIONS[sid] = {"session": cs, "artifacts": artifacts}
    generic().info("rehydrated session %s (%d past turns)", sid, len(cs.history))
    return _SESSIONS[sid]


@app.post("/sessions")
def create_session(file: UploadFile = File(...), x_user_id: str = Header("local")):
    """Upload a CSV -> profile it -> open a session."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    sid = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{sid}_{file.filename}"
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)
    try:
        profile = profile_csv(dest)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"could not read CSV: {e}")
    fname = file.filename or "upload.csv"
    _open_session(sid, profile, dest, fname, x_user_id)
    generic().info("session %s from %s (%d x %d)", sid, fname, profile.n_rows, profile.n_cols)
    return {"session_id": sid, "profile": _profile_json(profile, fname)}


@app.post("/sessions/sample")
def create_sample_session(x_user_id: str = Header("local")):
    """Open a session on the bundled Telco sample (no upload needed)."""
    csv = PROJECT_ROOT / "data" / "telco_churn.csv"
    if not csv.exists():
        raise HTTPException(404, "sample dataset not found")
    profile = profile_csv(csv)
    sid = uuid.uuid4().hex[:12]
    _open_session(sid, profile, csv, "telco_churn.csv", x_user_id)
    return {"session_id": sid, "profile": _profile_json(profile, "telco_churn.csv")}


@app.get("/sessions")
def list_sessions(x_user_id: str = Header("local")):
    """List this user's previous chats (most recent first)."""
    return db.list_sessions(x_user_id)


@app.post("/sessions/{sid}/chat")
def chat(sid: str, body: ChatIn):
    """Run one chat turn through the state machine; persist the exchange."""
    sess = _get_or_load(sid)
    if not sess:
        raise HTTPException(404, "unknown session_id")

    end, ctx = sess["session"].ask(body.message)
    answer = ctx.data.get("answer") or end.data.get("reason", "")

    images, tables = [], []
    result = ctx.data.get("exec_result")
    if result and result.artifacts:
        adir = ARTIFACTS_DIR / sid
        adir.mkdir(parents=True, exist_ok=True)
        for p in result.artifacts:
            name = Path(p).name
            durable = adir / name
            try:
                shutil.copyfile(p, durable)  # survive restarts
            except OSError:
                durable = Path(p)
            sess["artifacts"][name] = str(durable)
            low = name.lower()
            if low.endswith(".png"):
                images.append(name)
            elif low.endswith(".csv"):
                try:
                    tables.append(_table_json(durable, name))
                except Exception:  # noqa: BLE001 — a bad table shouldn't break chat
                    pass

    db.add_message(sid, "user", body.message)
    db.add_message(sid, "assistant", answer, images=images, tables=tables,
                   code=ctx.data.get("code", ""))
    return {"state": end.name, "answer": answer, "images": images, "tables": tables}


@app.get("/sessions/{sid}/messages")
def get_session_messages(sid: str):
    """The stored conversation for a session (to resume a previous chat)."""
    if not db.get_session(sid):
        raise HTTPException(404, "unknown session_id")
    return db.get_messages(sid)


@app.get("/sessions/{sid}")
def get_session_info(sid: str):
    """Stored profile + meta for a session (to reopen a previous chat)."""
    row = db.get_session(sid)
    if not row:
        raise HTTPException(404, "unknown session_id")
    return {
        "session_id": sid,
        "filename": row["filename"],
        "created_at": row["created_at"],
        "profile": json.loads(row["profile_json"]),
    }


@app.get("/sessions/{sid}/artifacts/{name}")
def get_artifact(sid: str, name: str):
    sess = _get_or_load(sid)
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
    from fastapi.testclient import TestClient

    client = TestClient(app)
    H = {"X-User-Id": "demo"}
    sid = client.post("/sessions/sample", headers=H).json()["session_id"]
    print("session:", sid)

    for msg in ["Give me a table of churn rate by contract type",
                "Show churn count by contract type as a bar chart"]:
        r = client.post(f"/sessions/{sid}/chat", json={"message": msg}).json()
        print(f"  chat {msg!r:55} -> images={r['images']} tables={[t['name'] for t in r['tables']]}")

    listed = client.get("/sessions", headers=H).json()
    print("list ->", [(s["id"], s["message_count"], s["last_user_message"]) for s in listed])
    print("messages ->", len(client.get(f"/sessions/{sid}/messages").json()))

    # simulate a server restart: drop all in-memory sessions
    _SESSIONS.clear()
    print("\n-- restart (in-memory cleared) --")
    msgs = client.get(f"/sessions/{sid}/messages").json()
    print("history still available ->", len(msgs), "messages")
    img = next((m["images"][0] for m in msgs if m["images"]), None)
    if img:
        ar = client.get(f"/sessions/{sid}/artifacts/{img}")
        print(f"old artifact {img} served ->", ar.status_code, ar.headers.get("content-type"))
    r = client.post(f"/sessions/{sid}/chat", json={"message": "which contract has the highest churn rate?"}).json()
    print("resumed chat ->", r["state"], "|", r["answer"][:90])
