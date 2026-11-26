# Changelog

All notable changes to this plugin are documented here. Versions follow
[semver](https://semver.org/); the version lives in `.claude-plugin/plugin.json`.

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
