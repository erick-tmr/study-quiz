---
name: quiz
description: Generate a study quiz (multiple-choice flashcards plus open-ended questions graded by Claude) from a topic, notes, files or URLs, and serve it as an interactive local HTML page, optionally versioned in a git repo. Use when the user wants to study, review or test themselves on something, or asks for flashcards, a quiz, practice questions or exam prep. Also "from mistakes <slug>" to target weak spots, "group <name>" to create or switch study groups (one workspace/repo per subject), and "git on|off" / "init-repo" to manage quiz versioning.
argument-hint: <topic | notes path | url> [n=10] [mix=6mc/4open] | from mistakes <slug> | group [name] | git on|off | init-repo [remote]
version: 0.3.0
---

# Generate a study quiz

Arguments: `$ARGUMENTS`

You write **only `quiz.json` and `sources/`**. Never write HTML. The helper
`sq.py` turns the quiz into a page from the shared template, keeps the index, and
handles git.

## 1. Resolve paths

- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`. If that is empty, use two directories
  above this skill's base directory (`<base>/../..`).
- **Helper**: `SQ="python3 <plugin root>/app/sq.py"`.
- **Workspace**: run `$SQ status`. It prints JSON with the active study `group`,
  the `workspace` path (`STUDY_QUIZ_DIR` > active group > config >
  `~/study-quizzes`), the `git` setting, `is_repo`, `remote` and the existing
  quizzes. Mention the active group when there is one.

## 2. Settings commands (handle these and stop)

- `git on` → `$SQ config git true`. If the workspace isn't a repo yet, continue
  with `init-repo`.
- `git off` → `$SQ config git false`. Nothing else changes; an existing repo is
  left as it is.
- `init-repo [remote-url]` → `$SQ init-repo [--remote URL]`. If the user wants a
  GitHub remote but has no URL, offer to create a **private** repo with
  `gh repo create <name> --private` (suggest the group name) and confirm the name first. Never make it
  public unless they ask.
- `config` → show `$SQ config`.
- `groups` → `$SQ group` (lists groups; `*` marks the active one).
- `group <name>` → if it exists, `$SQ group use <name>`. If it doesn't, confirm
  with the user and run `$SQ group new <name>` (it lives in
  `~/study-quizzes/<name>` unless they want a path, `--path`). A new group has
  its own git preference, so continue with step 3 for it.
- `group none` → `$SQ group none`.

A **study group** is a separate workspace, and optionally a separate git repo, per
subject (for example `ai-engineer`, `networking`). Generated quizzes go to the active
group. Inside a group, place quizzes in the group (don't ask which group) unless
the topic clearly belongs to a different existing group; then ask.

## 3. Git preference (once per installation)

Read `$SQ config git`:
- `true` / `false`: respect it silently.
- `null` (never asked, for this group or the top-level workspace): **ask the user
  once**, before generating: "Do you want your quizzes versioned in a git repo at
  `<workspace>`? Each new quiz gets a
  commit, a browsable README index, and an automatic push if the repo has a
  remote. Answer history stays local." Then:
  - yes → `$SQ init-repo` (plus the remote offer from step 2)
  - no → `$SQ config git false`

  Mention that `/study-quiz:quiz git on|off` changes it later.

## 4. Work out what to quiz on

- Arguments can be a topic, file paths, a folder, URLs, or a mix, plus optional
  `n=<count>` (default 10) and `mix=<mc>mc/<open>open` (default about 60% MC).
- **Files/folders**: read them. **URLs**: fetch them. **A bare topic**: use your
  own knowledge, and if the topic is specialised or fast-moving, say so and offer
  to use the user's notes instead.
- If the request is ambiguous (scope, level, exam focus), ask one short question.
  Otherwise go ahead.
- **from mistakes `<slug>`**: read `<workspace>/<slug>/quiz.json` and
  `attempts.json`. Collect wrong MC questions and the `points_missed` of
  partial/wrong open answers. Build a new quiz, `<slug>-review-N`, that tests
  those ideas again from **new angles** (rephrased, different scenario), not the
  same questions. Copy the original `sources/`.

## 5. Create the quiz folder

Pick a short kebab-case slug (`[a-z0-9-]`, ≤ 40 chars). If the slug already
exists, add `-2`, `-3`, and so on. Never overwrite another quiz.

Put the material into `<workspace>/<slug>/sources/` as Markdown or text: copy the
user's notes, or save cleaned extracts of fetched pages with the URL at the top.
For a bare topic, write `sources/overview.md`: a concise, accurate study summary
covering every concept the quiz tests. The grader relies on these files, so they
must contain the facts that back each answer.

## 6. Write `<workspace>/<slug>/quiz.json`

```json
{
  "slug": "<slug>",
  "title": "Human title",
  "created": "YYYY-MM-DD",
  "language": "en",
  "sources": ["sources/notes.md"],
  "questions": [
    { "id": "q1", "type": "mc", "prompt": "…", "options": ["…", "…", "…", "…"],
      "answer": 0, "explanation": "Why the answer is right and the tempting wrong option is wrong." },
    { "id": "q2", "type": "open", "prompt": "…",
      "reference_answer": "A model answer in 2–5 sentences.",
      "key_points": ["Atomic idea 1", "Atomic idea 2", "Atomic idea 3"],
      "source_refs": ["sources/notes.md"], "difficulty": "easy | medium | hard" }
  ]
}
```

Quality rules:
- **Language**: match the source material (or the user's request) and set
  `language` to it.
- **Coverage**: spread the questions across the material. Prefer the important
  concepts over trivia.
- **MC**: 3–5 options with exactly one correct one. Distractors should be plausible
  misconceptions, not jokes. Vary the position of the correct answer. Avoid
  "all of the above". `answer` is the 0-based index.
- **Open**: ask for explanation, comparison, application or "why" questions,
  not recall of a single word. 2–5 `key_points`, each one independently gradable
  idea. Together they define a full-score answer.
- Mix difficulties. Ids are `q1…qN` in order.

## 7. Save

Run `$SQ save <slug>`. It validates `quiz.json` (fix any errors it reports and
run it again), writes the standalone page `<slug>/index.html`, regenerates the
workspace `README.md`, and, if git is on, commits and pushes when a remote
exists. Report what it printed about git, including any push failure.

## 8. Serve it

Check for a running server with `curl -s localhost:8765/api/health`:
- It answers with `"app": "study-quiz"` and either the same `workspace` or
  `"follows_active_group": true`: reuse it. A server started without
  `--workspace` follows the active group live.
- Nothing answers: start it in the background (keep it running, don't wait on it):
  `python3 "<plugin root>/app/server.py"`. Don't pass `--workspace`, so it
  follows group switches.
- Something else answers, or a study-quiz server for a different workspace: start
  one with `--port 8766` (or the next free port), use that port in the URL, and
  tell the user why.

Then tell the user, briefly:
- the URL `http://localhost:8765/quiz/<slug>` (Claude grades open answers there,
  about 15–40s each, on their own Claude Code login; the model is set by
  `STUDY_QUIZ_GRADER_MODEL`, default `sonnet`)
- the offline page `<workspace>/<slug>/index.html` (open answers are self-checked)
- the MC/open question counts, and the git result
- that `/study-quiz:quiz from mistakes <slug>` builds a review quiz after a session
