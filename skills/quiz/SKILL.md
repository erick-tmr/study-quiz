---
name: quiz
description: Generate a study quiz (multiple-choice flashcards plus open-ended questions graded by Claude) from a topic, notes, files or URLs, and serve it as an interactive local HTML page. Use when the user wants to study, review or test themselves on something, or asks for flashcards, a quiz, practice questions or exam prep. Also "quiz from mistakes <slug>" to target weak spots from past attempts.
argument-hint: <topic | notes path | url> [n=10] [mix=6mc/4open] | from mistakes <slug>
version: 0.1.0
---

# Generate a study quiz

Arguments: `$ARGUMENTS`

## 1. Resolve paths

- **Workspace**: `$STUDY_QUIZ_DIR` if set, else `~/study-quizzes`. Get the absolute
  path with
  `python3 -c 'import os;print(os.path.abspath(os.path.expanduser(os.environ.get("STUDY_QUIZ_DIR") or "~/study-quizzes")))'`
  and create it if it doesn't exist.
- **Plugin root**: `${CLAUDE_PLUGIN_ROOT}`. If that is empty, use two directories
  above this skill's base directory (`<base>/../..`). The server is at
  `<plugin root>/server/server.py`.

## 2. Work out what to quiz on

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

## 3. Create the quiz folder

Pick a short kebab-case slug (`[a-z0-9-]`, ≤ 40 chars). If the slug already
exists, add `-2`, `-3`, and so on. Never overwrite another quiz.

```
<workspace>/<slug>/
  sources/      # the study material the grader will consult
  quiz.json
```

Put the material into `sources/` as Markdown or text: copy the user's notes, or
save cleaned extracts of fetched pages with the URL at the top. For a bare topic,
write `sources/overview.md`: a concise, accurate study summary covering every
concept the quiz tests. The grader relies on these files, so they must contain
the facts that back each answer.

## 4. Write quiz.json

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
- Validate the result: `python3 -m json.tool <file> > /dev/null`.

## 5. Serve it

Check for a running server with `curl -s localhost:8765/api/health`:
- It answers with `"app": "study-quiz"` and the same `workspace`: reuse it.
- Nothing answers: start it in the background (keep it running, don't wait on it):
  ```
  python3 "<plugin root>/server/server.py" --workspace "<workspace>"
  ```
- Something else answers, or a study-quiz server for a different workspace: start
  one with `--port 8766` (or the next free port), use that port in the URL, and
  tell the user why.

Then tell the user:
- the URL `http://localhost:8765/quiz/<slug>`
- how many MC and open questions there are
- that open answers are graded by Claude through their own Claude Code login
  (about 15–40s each, using their plan's usage), with the grader model set by
  `STUDY_QUIZ_GRADER_MODEL` (default `sonnet`)
- that after a session, `/study-quiz:quiz from mistakes <slug>` builds a review
  quiz.
