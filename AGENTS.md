# AGENTS.md

## Purpose
`agilabs-skills` is a public collection (GitHub, MIT) of portable, general-purpose
agent skills. Each skill is a self-contained folder with a `SKILL.md` plus optional
supporting scripts and references, loadable by Claude Code or any agent that
understands the skills format. Product- and client-specific skills are kept private
and must not be added here.

## Structure
Skills are grouped by category folder; each skill lives at `<category>/<skill>/`:

- `content-media/` — demo-video, blog-writer, spotify-upload, tailor-cv
- `dev-workflow/` — feature-dev, code-review, commit-pr, release-tag,
  microservice-scaffold, codegen-validation-loop, spec-driven-development
- `qa-testing/` — playwright-cli, authenticated-api-probe, deployment-verification,
  qa-design, qa-execution
- `governance/` — responsible-ai-audit
- `ops/` — render-development
- `productivity/` — email-cleanup

Inside a skill folder:
- `SKILL.md` — YAML frontmatter (`name`, `description`, optional `allowed-tools`)
  followed by the instructions. The `description` decides when the skill triggers.
- Supporting files as needed: `references/`, `scripts/`, `prompts/`, extra `*.md`
  (e.g. `PATTERNS.md`, `CONVENTIONS.md`, `SECURITY_CHECKLIST.md`), JSON data
  (`checklist.json`), and `evals/evals.json` (prompt + assertion list for testing
  the skill).

The root `README.md` has one table per category listing every skill with a
one-line summary.

## Commands
There is no build, test or lint tooling. Installation is copying a skill folder:

```bash
cp -R content-media/demo-video ~/.claude/skills/demo-video
```

Scripts under `content-media/demo-video/scripts/` (Python/JS) are runtime helpers
invoked by that skill, not a project build.

## Conventions
- Keep skills portable: no hardcoded company hostnames, credentials, cluster
  names, internal URLs, Slack/Jira IDs or personal data. Environment-specific
  details go into a user-side **profile** that the skill asks for once and reuses
  (pattern used by release-tag, deployment-verification, authenticated-api-probe,
  tailor-cv, responsible-ai-audit; e.g.
  `~/.claude/release-tag/profiles/<repo-name>.md`). email-cleanup instead keeps
  user-editable lists in a "Configure these lists" section of its own `SKILL.md`.
- When adding, renaming or removing a skill, update the matching table in
  `README.md` so it stays in sync with the folders.
- `name` in the frontmatter must match the skill folder name.
- Most skills are written in English; a few older ones (feature-dev, code-review,
  commit-pr) are in Spanish. Match the language of the skill being edited.
- Commit messages follow the existing style: `feat: ...` short imperative summary.
