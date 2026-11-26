# study-quiz

A [Claude Code](https://claude.com/claude-code) plugin that turns a topic, your notes,
files or URLs into an interactive study quiz:

- **Multiple-choice flashcards** with instant right/wrong feedback and explanations.
- **Open-ended questions graded by Claude**: a score, which key ideas you hit or
  missed, feedback, and what to re-read, checked against your own study material.
- **Review loop**: past attempts are saved, and `from mistakes` builds a new quiz
  that targets your weak spots.
- **Standalone pages**: every quiz also gets a self-contained `index.html` that
  works offline (open questions are self-checked against the key points).
- **Optional git versioning**: keep your quizzes in a git repo with a browsable
  index. Each new quiz is committed, and pushed when the repo has a remote.
- **Study groups → topics → quizzes**: one workspace (and optionally one GitHub
  repo, public or private) per subject, such as `ai-engineer`. Inside it, topics such
  as `rag` and `evals` each hold several quizzes.

Everything runs locally through **your own Claude Code login**. Quiz generation
happens in your Claude Code session, and grading runs headless `claude -p` in the
background. You don't need an API key, and nothing is uploaded except what Claude
Code itself sends to Claude.

![Graded open-ended answer](docs/screenshot-grade.png)

## Requirements

- Claude Code, logged in (`claude`, then `/login`)
- Python 3.9+ (standard library only; nothing to `pip install`)

## Install

In Claude Code:

```
/plugin marketplace add erick-tmr/study-quiz
/plugin install study-quiz@study-quiz
```

Update later with `/plugin marketplace update study-quiz`.

## Usage

```
/study-quiz:quiz group ai-engineer           # create (asks: git? GitHub? public/private?) or switch
/study-quiz:quiz prompt caching strategies    # picks or proposes a topic, writes the quiz
/study-quiz:quiz ~/notes/rag.md topic=rag n=15
/study-quiz:quiz https://arxiv.org/abs/2005.11401 topic=rag mix=4mc/4open
/study-quiz:quiz from mistakes rag/chunking-basics
/study-quiz:quiz groups | topics | topic evals | git on|off | config
```

Claude writes the quiz, starts the local server if it isn't running, and gives you a
link like `http://localhost:8765/quiz/rag/chunking-basics`. Open it, answer the questions, and
type open answers in your own words. Grading takes about 15–40 seconds per answer.

You can also run the server yourself:

```
python3 ~/.claude/plugins/cache/study-quiz/study-quiz/<version>/app/server.py
```

## Where things live

```
~/study-quizzes/                  # root for study groups ("workspace" config key)
  ai-engineer/                    # a study group: its own workspace and (optional) repo
    README.md                     # generated index, grouped by topic
    rag/                          # a topic
      topic.json                  # {"title": "Retrieval-augmented generation", "description": …}
      chunking-basics/            # a quiz (key: rag/chunking-basics)
        sources/                  # the material the quiz (and the grader) is based on
        quiz.json                 # questions, answers, reference answers, key points
        index.html                # standalone page (generated from the template)
        attempts.json             # your answers and grades (never committed)
```

Claude writes only `quiz.json` and `sources/`. Pages are stamped from one shared
template by `app/sq.py`, so they stay small and consistent, and Claude spends no
tokens on HTML. If you edit a `quiz.json` by hand, run `python3 <plugin>/app/sq.py save <slug>`.

## Study groups

A study group is a separate quiz workspace for one subject, with its own optional git
repo. Creating one asks whether to version it, whether to create a GitHub repo
(via `gh`), the repo name, and whether it should be **public or private**:

```
/study-quiz:quiz group ai-engineer      # create (in ~/study-quizzes/ai-engineer) or switch
/study-quiz:quiz groups                 # list; * marks the active group
/study-quiz:quiz group none             # back to the top-level workspace
/study-quiz:quiz topics                 # topics in the active group
```

Within a group, each quiz goes into a topic. The skill reuses a matching topic or
proposes a new one, or you can pick it with `topic=<name>`.

New quizzes go to the active group. The local server follows the active group live,
so switching needs no restart. Each group has its own git preference and remote,
so `ai-engineer` can be a public GitHub repo while another group stays local.

## Versioning your quizzes (optional)

The first time you generate a quiz, the skill asks whether to keep your quizzes in
git and remembers the answer (per study group) in `~/.config/study-quiz/config.json`. That file belongs
to this installation and survives plugin updates.

- **On**: the workspace becomes a git repo (`.gitignore` excludes `attempts.json`).
  Every new or changed quiz gets a commit like `quiz: add tcp-basics — TCP basics`,
  and the commit is pushed automatically if the repo has a remote. The generated
  `README.md` makes the repo easy to browse on GitHub.
- **Off**: nothing touches git.
- Change it anytime: `/study-quiz:quiz git on|off`. Add a remote:
  `/study-quiz:quiz init-repo git@github.com:you/my-quizzes.git` (the skill can also
  create a private GitHub repo for you with `gh`).

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `STUDY_QUIZ_DIR` | active group, else config `workspace`, else `~/study-quizzes` | Quiz workspace (pins it, ignoring groups) |
| `STUDY_QUIZ_GRADER_MODEL` | `sonnet` | Model alias used for grading (`haiku` is faster, `opus` more nuanced; `""` uses your Claude Code default) |
| `STUDY_QUIZ_PORT` | `8765` | Server port |
| `STUDY_QUIZ_CLAUDE` | `claude` on `PATH` | Path to the Claude Code binary |

## How grading works

1. When a quiz is created, each open question gets a reference answer and 2–5
   **key points**, the atomic ideas a full-score answer must contain.
2. When you submit an answer, the server runs
   `claude -p … --plugin-dir <this plugin> --tools Skill,Read,Glob,Grep --json-schema …`
   in your quiz workspace. That is a read-only, headless Claude Code session that
   follows the [`grade` skill](skills/grade/SKILL.md).
3. The grader reads the question, the relevant `sources/` and your earlier attempts.
   It marks each key point as hit or missed, and returns JSON that matches
   [`grade.schema.json`](app/grade.schema.json).
4. The server appends the result to `attempts.json` and the page shows it.

Grading uses your Claude plan's usage, like any other Claude Code message. The
server listens on `127.0.0.1` only and rejects cross-site and DNS-rebinding requests.

## Customising

The behaviour lives in two plain-Markdown skills: [`skills/quiz`](skills/quiz/SKILL.md)
(generation rules) and [`skills/grade`](skills/grade/SKILL.md) (the rubric). Fork the
repo, edit them, and install your fork the same way.

For local development, without installing:

```
claude --plugin-dir ./study-quiz
```

## Versioning

Releases follow semver. The version is in
[`.claude-plugin/plugin.json`](.claude-plugin/plugin.json), each release is tagged
`vX.Y.Z`, and changes are listed in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
