# agilabs-skills

Reusable [agent skills](https://docs.claude.com/en/docs/claude-code/skills) I use in
day-to-day work, packaged so they run in any project. Each skill is a self-contained
folder with a `SKILL.md` (and any supporting scripts/references) that Claude Code — or
any agent that understands the skills format — can load on demand.

These are the portable, general-purpose ones. Product- and client-specific skills stay
private. More about my work: [javieraguilar.ai](https://javieraguilar.ai).

## Install

Copy any skill folder into your skills directory:

```bash
cp -R content-media/demo-video ~/.claude/skills/demo-video
```

Then invoke it from Claude Code (the skill's `description` controls when it triggers).

## Skills

### Content & media
| Skill | What it does |
|---|---|
| [demo-video](content-media/demo-video) | Records narrated product-demo and verification videos of any web app by driving a real browser and assembling beat-narrated MP4s. |
| [blog-writer](content-media/blog-writer) | Writes bilingual (EN/ES) blog articles end-to-end: structure, frontmatter and translations. |
| [spotify-upload](content-media/spotify-upload) | Uploads and publishes podcast episodes to Spotify for Creators via browser automation. |
| [tailor-cv](content-media/tailor-cv) | Adapts a CV and drafts a tailored cover letter for a role, exporting to Markdown, DOCX and PDF. Profile-driven: asks for your details once and reuses them. |

### Dev workflow
| Skill | What it does |
|---|---|
| [feature-dev](dev-workflow/feature-dev) | Guides new-feature development: architecture planning, implementation and PR creation. |
| [code-review](dev-workflow/code-review) | Reviews diffs and PRs for correctness, security and performance, with actionable suggestions. |
| [commit-pr](dev-workflow/commit-pr) | Creates well-structured commits and pull requests with clear messages and branch handling. |

### QA & testing
| Skill | What it does |
|---|---|
| [playwright-cli](qa-testing/playwright-cli) | Automates browser interactions for testing, form filling, screenshots and data extraction. |

## License

[MIT](LICENSE) © 2026 Javier Aguilar
