# Agent Workflow Notes

- Persistent notes live in `memory/`.
- Keep note files in Markdown only.
- Favor concise decision logs over raw dumps.
- When a repo rule changes, update `AGENTS.md` and leave a short note here if it affects future work.

## Current repo-specific rules

- Use `selectolax` instead of Beautiful Soup for HTML parsing.
- Prefer an Audiolibrix internal API if a stable one is discovered later; otherwise keep the current HTML parsing path.
