# CLAUDE.md

@AGENTS.md

## Claude Code notes

- Project instructions live in `AGENTS.md`; this file only imports them.
- Project skills live in `.claude/skills/` and are synced from `.agents/skills/`.
  Use `spotiearth-standards` before architecture changes and
  `spotiearth-timelapse-ingest` before playlist or track ingestion.
- Prefer plan mode for changes that touch more than one module.
- Run `python -m unittest discover -s tests -v` before reporting work as done.
