#!/usr/bin/env python3
"""study-quiz local server.

Serves the interactive quiz page and grades open-ended answers by running
headless Claude Code (`claude -p`) with the plugin's `grade` skill. Grading uses
whatever account `claude` is logged into, so no API key is needed.

Standard library only. Binds to 127.0.0.1.

    python3 server.py [--port 8765] [--workspace ~/study-quizzes]

Environment / config (see common.py):
    STUDY_QUIZ_DIR           quiz workspace (else the active study group, else config
                             "workspace", else ~/study-quizzes). Without --workspace or
                             STUDY_QUIZ_DIR the server follows the active group live.
    STUDY_QUIZ_GRADER_MODEL  model alias for grading (default: sonnet)
    STUDY_QUIZ_CLAUDE        path to the claude binary (default: claude on PATH)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import common
from urllib.parse import unquote

from common import PLUGIN_ROOT, TEMPLATE

SCHEMA = (common.APP_DIR / "grade.schema.json").read_text()
QID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MAX_ANSWER = 8000
GRADE_TIMEOUT = 180

_attempts_lock = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Config:
    fixed_workspace: Path | None = None
    model: str
    claude_bin: str | None

    @property
    def workspace(self) -> Path:
        # Re-resolved per request so `sq.py group use X` takes effect without a restart.
        return self.fixed_workspace or common.workspace()


CFG = Config()


# --------------------------------------------------------------------------- data

# A quiz is addressed by its key: "<topic>/<slug>" (or a legacy flat "<slug>").

def quiz_dir(key: str) -> Path | None:
    return common.quiz_dir(CFG.workspace, key)


def load_quiz(key: str) -> dict | None:
    return common.load_quiz(CFG.workspace, key)


def list_topics() -> list[dict]:
    return [{"topic": t, **meta} for t, meta in common.iter_topics(CFG.workspace)]


def list_quizzes() -> list[dict]:
    out = []
    for slug, q in common.iter_quizzes(CFG.workspace):
        qs = q.get("questions", [])
        out.append({
            "slug": slug,
            "topic": slug.split("/")[0] if "/" in slug else None,
            "title": q.get("title", slug),
            "created": q.get("created", ""),
            "mc": sum(1 for x in qs if x.get("type") == "mc"),
            "open": sum(1 for x in qs if x.get("type") == "open"),
            "attempts": len(read_attempts(slug)),
        })
    return out


def read_attempts(slug: str) -> list:
    p = CFG.workspace / slug / "attempts.json"
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def append_attempt(slug: str, record: dict) -> None:
    p = CFG.workspace / slug / "attempts.json"
    with _attempts_lock:
        data = read_attempts(slug)
        data.append(record)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp.replace(p)


# ------------------------------------------------------------------------ grading

class GradeError(Exception):
    pass


def grade(slug: str, qid: str, answer: str) -> dict:
    if not CFG.claude_bin:
        raise GradeError("The `claude` CLI was not found on PATH. Install Claude Code and run `claude` once to log in.")
    # Neutralise any attempt to close the answer tag early.
    safe_answer = answer.replace("</student_answer>", "</student_answer_>")
    prompt = (
        "Use the study-quiz:grade skill to grade this answer.\n"
        f"Quiz: {slug}\nQuestion id: {qid}\n"
        f"<student_answer>\n{safe_answer}\n</student_answer>"
    )
    tools = "Skill,Read,Glob,Grep"
    cmd = [
        CFG.claude_bin, "-p", prompt,
        "--plugin-dir", str(PLUGIN_ROOT),
        "--tools", tools, "--allowedTools", tools,
        "--max-turns", "10",
        "--output-format", "json",
        "--json-schema", SCHEMA,
        "--no-session-persistence",
    ]
    if CFG.model:
        cmd += ["--model", CFG.model]
    try:
        proc = subprocess.run(
            cmd, cwd=CFG.workspace, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=GRADE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise GradeError(f"Grading timed out after {GRADE_TIMEOUT}s. Try again.")
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        msg = (proc.stderr or proc.stdout or "").strip()[-600:]
        if "login" in msg.lower() or "auth" in msg.lower():
            msg += "\nRun `claude` in a terminal and use /login."
        raise GradeError(f"claude exited with code {proc.returncode}: {msg}")
    if out.get("is_error"):
        raise GradeError(f"claude reported an error ({out.get('subtype')}): {str(out.get('result'))[:600]}")
    result = out.get("structured_output")
    if result is None:
        try:
            result = json.loads(out.get("result") or "")
        except json.JSONDecodeError:
            raise GradeError("The grader did not return valid JSON.")
    result["_meta"] = {
        "duration_ms": out.get("duration_ms"),
        "num_turns": out.get("num_turns"),
        "model": CFG.model or "default",
    }
    return result


# ------------------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = "study-quiz/0.1"

    def log_message(self, fmt, *args):  # quieter log
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status: int = 200) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _error(self, status: int, msg: str) -> None:
        self._json({"error": msg}, status)

    def _body(self) -> dict | None:
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 64_000:
                return None
            return json.loads(self.rfile.read(n) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return None

    def _same_origin(self) -> bool:
        # Block cross-site POSTs from other pages open in the browser, and
        # DNS-rebinding (a foreign hostname resolving to 127.0.0.1).
        host = self.headers.get("Host", "")
        if host.rsplit(":", 1)[0] not in ("localhost", "127.0.0.1"):
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin == f"http://{host}"

    @staticmethod
    def _group() -> str | None:
        return None if CFG.fixed_workspace else common.active_group()

    # GET ----------------------------------------------------------------------
    def do_GET(self):
        if self.headers.get("Host", "").rsplit(":", 1)[0] not in ("localhost", "127.0.0.1"):
            return self._error(403, "unexpected Host header")
        path = unquote(self.path.split("?", 1)[0]).rstrip("/") or "/"
        if path in ("/", "/quiz"):
            return self._send(200, TEMPLATE.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/quizzes":
            return self._json({"workspace": str(CFG.workspace), "group": self._group(),
                               "topics": list_topics(), "quizzes": list_quizzes()})
        if path == "/api/health":
            return self._json({"ok": True, "app": "study-quiz", "workspace": str(CFG.workspace),
                               "group": self._group(), "follows_active_group": CFG.fixed_workspace is None,
                               "claude": bool(CFG.claude_bin), "model": CFG.model or "default"})
        m = re.match(r"^/api/quiz/(.+)/attempts$", path)
        if m:
            if not quiz_dir(m.group(1)):
                return self._error(404, "quiz not found")
            return self._json(read_attempts(m.group(1)))
        m = re.match(r"^/quiz/(.+)$", path)
        if m:
            if not quiz_dir(m.group(1)):
                return self._error(404, "quiz not found")
            return self._send(200, TEMPLATE.read_bytes(), "text/html; charset=utf-8")
        m = re.match(r"^/api/quiz/(.+)$", path)
        if m:
            q = load_quiz(m.group(1))
            if q is None:
                return self._error(404, "quiz not found")
            q["slug"] = m.group(1)
            if "/" in m.group(1):
                q["topic_title"] = common.topic_meta(CFG.workspace, m.group(1).split("/")[0])["title"]
            return self._json(q)
        self._error(404, "not found")

    # POST ---------------------------------------------------------------------
    def do_POST(self):
        if not self._same_origin():
            return self._error(403, "cross-origin request refused")
        body = self._body()
        if body is None:
            return self._error(400, "invalid JSON body")
        slug, qid = str(body.get("slug", "")), str(body.get("qid", ""))
        quiz = load_quiz(slug)
        if quiz is None:
            return self._error(404, "quiz not found")
        if not QID_RE.match(qid):
            return self._error(400, "invalid question id")
        question = next((q for q in quiz.get("questions", []) if q.get("id") == qid), None)
        if question is None:
            return self._error(404, "question not found")

        if self.path == "/api/grade":
            if question.get("type") != "open":
                return self._error(400, "only open questions are graded by Claude")
            answer = str(body.get("answer", "")).strip()
            if not answer:
                return self._error(400, "empty answer")
            if len(answer) > MAX_ANSWER:
                return self._error(400, f"answer too long (max {MAX_ANSWER} chars)")
            try:
                result = grade(slug, qid, answer)
            except GradeError as e:
                return self._error(502, str(e))
            append_attempt(slug, {"ts": now_iso(), "qid": qid, "type": "open",
                                  "answer": answer, "grade": {k: v for k, v in result.items() if k != "_meta"}})
            return self._json(result)

        if self.path == "/api/attempt":
            if question.get("type") != "mc":
                return self._error(400, "only mc attempts are recorded here")
            try:
                choice = int(body.get("choice"))
            except (TypeError, ValueError):
                return self._error(400, "invalid choice")
            correct = choice == question.get("answer")
            append_attempt(slug, {"ts": now_iso(), "qid": qid, "type": "mc",
                                  "choice": choice, "correct": correct})
            return self._json({"correct": correct})

        self._error(404, "not found")


def main() -> None:
    ap = argparse.ArgumentParser(description="study-quiz local server")
    ap.add_argument("--port", type=int, default=int(os.environ.get("STUDY_QUIZ_PORT", "8765")))
    ap.add_argument("--workspace", default=None, help="default: STUDY_QUIZ_DIR, config, ~/study-quizzes")
    ap.add_argument("--model", default=os.environ.get("STUDY_QUIZ_GRADER_MODEL", "sonnet"),
                    help='model alias for grading; "" uses your Claude Code default')
    args = ap.parse_args()

    fixed = args.workspace or os.environ.get("STUDY_QUIZ_DIR")
    CFG.fixed_workspace = common.workspace(fixed) if fixed else None
    CFG.workspace.mkdir(parents=True, exist_ok=True)
    CFG.model = args.model
    CFG.claude_bin = os.environ.get("STUDY_QUIZ_CLAUDE") or shutil.which("claude")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as e:
        raise SystemExit(f"cannot listen on 127.0.0.1:{args.port} ({e}); try --port {args.port + 1}")
    print(f"study-quiz serving {CFG.workspace}" + ("" if CFG.fixed_workspace else " (follows the active study group)"))
    print(f"open http://localhost:{args.port}/")
    if not CFG.claude_bin:
        print("warning: `claude` not found on PATH; open-ended grading will fail")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
