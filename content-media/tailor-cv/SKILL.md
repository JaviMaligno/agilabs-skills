---
name: tailor-cv
description: Use when adapting a CV or writing a cover letter for a specific job posting, role description, or recruiter message. Handles job analysis, project matching, and document generation in markdown, DOCX, and PDF.
---

# Tailor CV and Cover Letter

Adapt a candidate's CV and generate a cover letter tailored to a specific role.

The skill is **profile-driven**: it keeps the candidate's stable details (contact,
work history, education, languages, portfolio) in a profile file and reuses them on
every run. The first time you run it — or whenever a required field is missing — it
asks the user for the gaps and saves them, so subsequent runs need only the job posting.

## Candidate profile (ask once, reuse forever)

**Profile location:** `~/.claude/tailor-cv/profile.md`

**Step 0 — load or create the profile:**

1. Read `~/.claude/tailor-cv/profile.md`.
2. If it does not exist, or any REQUIRED field below is blank/placeholder, ask the user
   for the missing fields (one concise batch of questions), then write them to the
   profile file. Do not invent values — ask.
3. On later runs, reuse the profile silently. Offer a one-line "profile still current?"
   check only if the user hints something changed (new job, moved city).

**Required fields:**
- Full name
- Location (and work-authorization note if relevant, e.g. "London, UK (EU/Schengen)")
- Contact: email, and any public links (personal site, GitHub, LinkedIn)
- Work history: for each role — title, organization, dates, and 2–3 achievement notes
- Education: degrees, institutions, years
- Languages and levels
- Portfolio source: where the projects/experience detail lives — a file path
  (e.g. a `projects` data file), an existing résumé, or pasted text

**Profile file template** (`~/.claude/tailor-cv/profile.md`):

```markdown
# CV Profile

- Name: <full name>
- Location: <city, country (work-authorization note)>
- Email: <email>
- Links: <site> | <github> | <linkedin>

## Work history
### <Title> — <Organization> (<start> – <end|Present>)
- <achievement note>
- <achievement note>

## Education
- <Degree> — <Institution> (<years>)

## Languages
- <Language> (<level>)

## Portfolio source
- <path to projects/experience data, or "pasted below">
```

## Inputs (per run)

One of:
- **Job URL** — fetched and analyzed via WebFetch
- **Job description text** — pasted directly by user
- **Recruiter message** — extracted requirements from an informal message

Plus optional user instructions (e.g., "emphasize observability experience", "focus on Python").

## Workflow

1. **Load profile** (Step 0 above) and **read portfolio context** from the profile's
   Portfolio source. If the user provides additional context about unlisted experience,
   incorporate it.

2. **Analyze job requirements**
   - If URL: fetch with WebFetch and extract requirements
   - If text/message: parse directly
   - Extract: role title, company, must-have skills, nice-to-have skills, domain, language requirements, location constraints

3. **Match and strategize**
   - Rank the top 3–4 projects/roles by relevance
   - Identify which skills to highlight (e.g., Python vs TypeScript, AWS vs GCP)
   - Determine the CV "angle" (e.g., "Agentic AI Engineer", "MLOps Engineer", "Full-Stack AI")
   - Note any user-specific instructions for emphasis

4. **Generate CV** as `docs/cvs/<LastName>_<Role>_<Company>.md`
5. **Generate Cover Letter** as `docs/cvs/Cover_Letter_<Role>_<Company>.md`
6. **Convert to DOCX and PDF** using pandoc

## CV Template

Fill every `<...>` from the profile; fill every `[...]` from the job analysis.

```markdown
# <FULL NAME>

**<Location>** | <email> | [<site>](<site-url>) | [<github handle>](<github-url>)

---

## SUMMARY

**[Tailored Role Title]** with [2-3 lines matching key requirements]. [Unique differentiator].

---

## EXPERIENCE

### [Tailored Title] — <Most recent organization>
**<start> – Present**

- [4-5 bullets tailored to job requirements, using STAR-lite format]
- Each bullet: **Bold keyword:** Action + measurable result

### [Tailored Title] — <Previous organization>
**<dates>**

- [3-4 bullets relevant to role]

### <Earlier role title> — <Earlier organization>
**<dates>**

- [1-2 bullets relevant to role]

---

## TECHNICAL SKILLS

**[Category matching role]:**
- [Grouped by relevance, most important first]
- **Bold** the exact technologies mentioned in the job posting

**[Second category]:**
- [...]

---

## EDUCATION

- **<Degree>** — <Institution> (<years>)

---

## LANGUAGES

- <Language> (<level>)
```

## Cover Letter Template

```markdown
Dear [Hiring Manager/Recruiter name if known],

[Opening: Why this specific role excites you - reference company/project]

[Body 1: Most relevant experience mapped to their top requirement]

[Body 2: Second key match, with concrete outcomes/metrics]

[Body 3: Cultural/team fit - language skills, remote experience, collaboration style]

[Closing: Call to action, availability]

Best regards,
<Full name>
<site>
```

## Tailoring Rules

- **Mirror job language**: Use their exact terminology (e.g., "observability" not "monitoring" if that's what they say)
- **Lead with matches**: The first bullet under the most recent role should directly address the #1 job requirement
- **Quantify outcomes**: Use concrete metrics from the profile's achievements (">95% accuracy", "40% cost reduction", "processing under 2 min/doc")
- **Bold matching tech**: If the job says "Langfuse", bold **Langfuse** in skills and bullets
- **Adapt title**: Match role title to the job (AI Engineer, MLOps, GenAI Consultant, etc.)
- **Location**: Show the work-authorization note when a location/authorization requirement is relevant
- **Languages section**: Move it up if a multilingual requirement is mentioned

## Document Conversion

### DOCX

```bash
cd docs/cvs && pandoc "<LastName>_<Role>_<Company>.md" -o "<LastName>_<Role>_<Company>.docx" && pandoc "Cover_Letter_<Role>_<Company>.md" -o "Cover_Letter_<Role>_<Company>.docx"
```

### PDF

Uses xelatex for proper font rendering and link styling. CV uses tighter margins (1.5cm), cover letter uses wider margins (2cm).

```bash
cd docs/cvs && pandoc "<LastName>_<Role>_<Company>.md" -o "<LastName>_<Role>_<Company>.pdf" --pdf-engine=xelatex -V geometry:margin=1.5cm -V fontsize=11pt -V mainfont="Helvetica" -V colorlinks=true -V linkcolor=blue -V urlcolor=blue && pandoc "Cover_Letter_<Role>_<Company>.md" -o "Cover_Letter_<Role>_<Company>.pdf" --pdf-engine=xelatex -V geometry:margin=2cm -V fontsize=11pt -V mainfont="Helvetica" -V colorlinks=true -V linkcolor=blue -V urlcolor=blue
```

## Checklist

- [ ] Profile loaded (or missing fields collected and saved to `~/.claude/tailor-cv/profile.md`)
- [ ] Portfolio context read from the profile's Portfolio source
- [ ] Job requirements extracted and listed
- [ ] Top 3-4 projects/roles matched with justification
- [ ] CV generated with tailored summary, experience bullets, and skills
- [ ] Cover letter generated
- [ ] Both converted to DOCX
- [ ] Both converted to PDF
- [ ] User-specific emphasis incorporated
```
