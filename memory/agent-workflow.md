# Agent Workflow Notes

- Persistent notes live in `memory/`.
- Keep note files in Markdown only.
- Favor concise decision logs over raw dumps.
- When a repo rule changes, update `AGENTS.md` and leave a short note here if it affects future work.

## Current repo-specific rules

- Use `selectolax` instead of Beautiful Soup for HTML parsing.
- Prefer an Audiolibrix internal API if a stable one is discovered later; otherwise keep the current HTML parsing path.
- Keep result filtering strict when an exact normalized title match exists, but do not let a wrong-author exact-title beat a strong author-matched prefixed title such as `Jack Reacher: Volný pád`.
- Treat punctuation-only title splits as equivalent for matching, for example `Tchajpan` vs `Tchaj-pan`, and ignore Audiolibrix collapse-toggle links like `další interpreti (1)` when extracting narrator names.
