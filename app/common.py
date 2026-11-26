"""Shared helpers for the study-quiz server and CLI (standard library only)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = APP_DIR.parent
TEMPLATE = APP_DIR / "quiz.html"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DEFAULT_WORKSPACE = "~/study-quizzes"


# ------------------------------------------------------------------ config
# Per-installation settings live outside the plugin folder (the plugin cache is
# replaced on update), in $XDG_CONFIG_HOME/study-quiz/config.json.

def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "study-quiz" / "config.json"


def load_config() -> dict:
    try:
        data = json.loads(config_path().read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + "\n")


def workspace(override: str | None = None) -> Path:
    """CLI flag > STUDY_QUIZ_DIR > config 'workspace' > ~/study-quizzes."""
    raw = override or os.environ.get("STUDY_QUIZ_DIR") or load_config().get("workspace") or DEFAULT_WORKSPACE
    return Path(raw).expanduser().resolve()


# ------------------------------------------------------------------ quizzes

def load_quiz(ws: Path, slug: str) -> dict | None:
    if not SLUG_RE.match(slug):
        return None
    try:
        return json.loads((ws / slug / "quiz.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def iter_quizzes(ws: Path):
    if not ws.is_dir():
        return
    for d in sorted(ws.iterdir()):
        if d.is_dir():
            q = load_quiz(ws, d.name)
            if q:
                yield d.name, q


def validate_quiz(q: dict) -> list[str]:
    """Return a list of problems (empty if the quiz is well-formed)."""
    errs = []
    if not isinstance(q.get("title"), str) or not q["title"].strip():
        errs.append("missing title")
    qs = q.get("questions")
    if not isinstance(qs, list) or not qs:
        return errs + ["questions must be a non-empty list"]
    seen = set()
    for i, x in enumerate(qs):
        where = f"questions[{i}] ({x.get('id', '?')})"
        qid = x.get("id")
        if not isinstance(qid, str) or not re.match(r"^[A-Za-z0-9_-]{1,32}$", qid):
            errs.append(f"{where}: bad id")
        elif qid in seen:
            errs.append(f"{where}: duplicate id")
        seen.add(qid)
        if not str(x.get("prompt", "")).strip():
            errs.append(f"{where}: missing prompt")
        if x.get("type") == "mc":
            opts = x.get("options")
            if not isinstance(opts, list) or not 2 <= len(opts) <= 8:
                errs.append(f"{where}: mc needs 2-8 options")
            elif not isinstance(x.get("answer"), int) or not 0 <= x["answer"] < len(opts):
                errs.append(f"{where}: answer must be a valid 0-based option index")
        elif x.get("type") == "open":
            kp = x.get("key_points")
            if not isinstance(kp, list) or not kp:
                errs.append(f"{where}: open needs key_points")
            if not str(x.get("reference_answer", "")).strip():
                errs.append(f"{where}: open needs reference_answer")
        else:
            errs.append(f"{where}: type must be 'mc' or 'open'")
    return errs
