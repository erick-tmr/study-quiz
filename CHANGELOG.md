# Changelog

All notable changes to this plugin are documented here. Versions follow
[semver](https://semver.org/); the version lives in `.claude-plugin/plugin.json`.

## [0.3.0] - 2026-11-26

### Added
- Topics inside study groups: `<group>/<topic>/<quiz>/`, quiz keys `topic/quiz`,
  `topic.json` metadata, `sq.py topic [new|set]`, index and page grouped by topic.
  Legacy flat quizzes still load (listed under "Other").
- Creating a study group asks: git? GitHub repo? public or private? name?
  `sq.py init-repo --github OWNER/NAME --visibility public|private` creates the
  repo with `gh` and pushes.
- Study groups: one workspace (and optional git repo) per subject. `sq.py group
  [new|use|none] NAME`, skill commands `group <name>` / `groups` / `group none`.
- Per-group git preference (asked once per group).
- `sq.py status` JSON summary used by the skill.
- Server follows the active group live when started without `--workspace`;
  `/api/health` reports `group` and `follows_active_group`.

## [0.2.0] - 2026-11-26

### Added
- Standalone `index.html` per quiz, stamped from the shared template (no HTML is
  written by Claude). Open questions are self-checked offline against the key points.
- Optional git versioning of the quiz workspace: asked once and remembered per
  installation in `~/.config/study-quiz/config.json`; commits each new/changed quiz,
  auto-pushes when a remote exists, keeps `attempts.json` out of git.
- Generated workspace `README.md` index of all quizzes.
- `app/sq.py` helper CLI (`workspace`, `config`, `check`, `build`, `index`,
  `init-repo`, `save`) with `quiz.json` validation.
- Skill commands: `git on|off`, `init-repo [remote]`, `config`.

### Changed
- `server/` renamed to `app/`; shared code moved to `app/common.py`.
- Workspace can also be set with the `workspace` config key.

## [0.1.0] - 2026-11-26

### Added
- `quiz` skill: generate multiple-choice + open-ended quizzes from a topic, notes,
  files or URLs; `from mistakes <slug>` review mode.
- `grade` skill: rubric-based grading of open answers against key points and the
  quiz's source material, with prompt-injection resistance.
- Local stdlib-only server (`server/server.py`) serving the interactive quiz page and
  grading through headless `claude -p` with structured JSON output.
- Interactive page: flashcards, Claude grading with hit/missed key points, summary,
  retry missed, light/dark themes, keyboard shortcuts.
