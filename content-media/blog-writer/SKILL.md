---
name: blog-writer
description: Write bilingual blog articles for the personal website. Use when creating a new blog post, article, or writing content for the blog. Handles EN/ES translations, frontmatter, and content structure.
---

# Blog Article Writer

Create bilingual (English/Spanish) blog articles for javieraguilar.ai.

## File Locations

- English: `src/content/blog/en/[slug].md`
- Spanish: `src/content/blog/es/[slug].md`
- Images: `public/blog/[image-name].png` (referenced as `/blog/[image-name].png`)

## Required Frontmatter Format

Both EN and ES files must include this exact frontmatter:

```yaml
---
title: "Article Title Here"
description: "A concise description for SEO and preview cards (1-2 sentences)."
pubDate: YYYY-MM-DD
tags: ["Tag1", "Tag2", "Tag3"]
lang: en  # or es
translationKey: article-slug
heroImage: "/blog/article-slug.png"
---
```

### Field Requirements

| Field | Required | Notes |
|-------|----------|-------|
| `title` | Yes | Translated per language |
| `description` | Yes | Translated, SEO-friendly, 1-2 sentences |
| `pubDate` | Yes | Same date for both languages |
| `tags` | Yes | Translated (e.g., "AI" → "IA") |
| `lang` | Yes | Must be `en` or `es` |
| `translationKey` | Yes | Same value for EN/ES pair (kebab-case) |
| `heroImage` | Yes | Path to thumbnail (e.g., `/blog/my-article.png`). Generate with script below. |

### LinkedIn Automation (Optional)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `linkedinImage` | string | Ruta a imagen para LinkedIn (ej: `/blog/linkedin-card.png`) |

**Notas:**
- Campo opcional
- Solo se usa para auto-publicación en LinkedIn
- Si se omite, el post en LinkedIn será solo texto
- Ruta debe apuntar a archivo en `public/blog/`
- Formatos: PNG, JPG, WEBP
- Tamaño recomendado: 1200x627px

**Ejemplo:**
```yaml
---
title: "Mi Artículo"
description: "Descripción del artículo"
pubDate: 2026-01-07
tags: ["AI", "Automation"]
lang: en
translationKey: mi-articulo
heroImage: "/blog/mi-articulo.png"
linkedinImage: /blog/linkedin-card.png  # Opcional
---
```

## Hero Image Generation

Every article must have a `heroImage`. Generate it using Codex CLI, which has access to OpenAI's image generation models (gpt-image-2).

### How to Generate

```bash
codex exec --full-auto "Generate an image with this prompt and save it to public/blog/article-slug.png: 'YOUR PROMPT HERE'"
```

Codex will use its built-in `image_gen` tool, generate the image, and copy it to the specified path in the project.

### Prompt Guidelines

Use this consistent style across all articles:

```
A minimalist isometric illustration on a dark background. [SCENE DESCRIPTION].
Style: clean tech diagram aesthetic, neon blue and [ACCENT COLOR] accents on deep navy, no photorealism, no humans.
```

- **Always start with**: "A minimalist isometric illustration on a dark background"
- **Always end with**: "Style: clean tech diagram aesthetic, neon [color] accents on deep navy, no photorealism, no humans"
- **Scene**: Describe the core concept of the article as a visual metaphor using tech icons, nodes, terminals, diagrams
- **Accent colors**: Pick one that fits the article's theme (amber, red, green, purple, orange, teal, gold)
- **Avoid**: photorealism, humans, text-heavy prompts

### Workflow

1. After writing the article content, craft an image prompt based on the article's core concept
2. Run Codex to generate the image
3. **Show the generated image to the user for review** (use Read tool on the PNG)
4. If approved, add `heroImage: "/blog/article-slug.png"` to **both** EN and ES frontmatter
5. If not approved, adjust the prompt and regenerate
6. Codex image quality is trusted — no need for comparison with other generators

### Requirements

- Codex CLI installed (`codex` command available)
- OpenAI API key configured in Codex

## Bilingual Workflow

1. **Always create both files** with matching `translationKey`
2. Use the same `pubDate` for synchronized release
3. Translate tags appropriately (common: AI→IA, Automation→Automatización)
4. Keep `translationKey` identical in both files

## Content Structure

Follow this pattern:

```markdown
Opening paragraph establishing context and the problem/topic.

## Section Heading

Content with clear explanations. Focus on "why" not just "how".

### Subsection (if needed)

- Bullet points for lists
- Keep them concise

## Another Section

Include practical examples:

```language
code block with syntax highlighting
```

## Conclusion/Next Steps

Wrap up with actionable takeaways or links.

---

*Footer with links to resources, repos, etc.*
```

## Writing Style

- **Tone**: Professional but conversational
- **Focus**: Practical value, real examples
- **Length**: 800-2000 words typically
- **Structure**: Clear headings, scannable sections
- **Code**: Include relevant code snippets with language identifiers
- **Images**: Always use **absolute URLs** for inline images: `https://www.javieraguilar.ai/blog/image-name.png`. Dev.to cannot resolve relative paths (`/blog/...`), and the publish script auto-converts relative paths but using absolute URLs from the start avoids issues. The `heroImage` frontmatter field can remain a relative path (it's converted by the publish script).

## Video Embeds

### For the Website (javieraguilar.ai)

Use HTML iframe embeds for video platforms. The website supports full HTML.

**Loom example:**
```html
<div style="position: relative; padding-bottom: 56.25%; height: 0;">
  <iframe src="https://www.loom.com/embed/VIDEO_ID"
          frameborder="0"
          webkitallowfullscreen
          mozallowfullscreen
          allowfullscreen
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
  </iframe>
</div>
```

**YouTube example:**
```html
<div style="position: relative; padding-bottom: 56.25%; height: 0;">
  <iframe src="https://www.youtube.com/embed/VIDEO_ID"
          frameborder="0"
          allowfullscreen
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;">
  </iframe>
</div>
```

### Dev.to Compatibility

**Important:** Dev.to filters HTML iframes for security. The publish script (`scripts/devto/publish-to-devto.js`) automatically transforms video embeds:

- **Loom iframes** → Markdown links with note
- **YouTube iframes** → Could be transformed to `{% youtube %}` liquid tags (not implemented yet)

**What gets sent to Dev.to:**
```markdown
**🎥 [Watch the video demo on Loom](https://www.loom.com/share/VIDEO_ID)**

> _Note: Interactive video player available on the [original article](CANONICAL_URL)_
```

**Best Practice:**
- Always use iframe embeds in the markdown
- The Dev.to publish script handles the transformation automatically
- Don't manually create different versions for Dev.to

## Tag Conventions

Common tag translations:

| English | Spanish |
|---------|---------|
| AI | IA |
| Automation | Automatización |
| Machine Learning | Machine Learning |
| Development | Desarrollo |
| Architecture | Arquitectura |

## Example Frontmatter Pair

**English** (`src/content/blog/en/my-new-post.md`):
```yaml
---
title: "Building Something Cool"
description: "How I built a tool that solves a real problem."
pubDate: 2025-01-03
tags: ["AI", "Automation", "Claude"]
lang: en
translationKey: my-new-post
heroImage: "/blog/my-new-post.png"
---
```

**Spanish** (`src/content/blog/es/my-new-post.md`):
```yaml
---
title: "Construyendo Algo Genial"
description: "Cómo construí una herramienta que resuelve un problema real."
pubDate: 2025-01-03
tags: ["IA", "Automatización", "Claude"]
lang: es
translationKey: my-new-post
heroImage: "/blog/my-new-post.png"
---
```

## Writing from LinkedIn Posts

When repurposing a LinkedIn post into a blog article:

1. **Fetch the post** using WebFetch to extract the content
2. **Download any images** from the post to `public/blog/`
3. **Expand the content** - LinkedIn posts are short; blog articles should:
   - Add more context and background
   - Include code examples if relevant
   - Expand on points that were condensed
   - Add sections the post didn't have room for
4. **Keep the core message** but make it more comprehensive
5. **Use original post date** as `pubDate` for authenticity

### LinkedIn Image Download

Images from LinkedIn posts should be:
- Downloaded to `public/blog/[descriptive-name].png`
- Named descriptively (e.g., `azure-content-filter-demo.png`)
- Referenced in markdown as `/blog/[name].png`

## Checklist Before Publishing

- [ ] Both EN and ES files created
- [ ] Matching `translationKey` in both
- [ ] Same `pubDate` in both
- [ ] Tags translated appropriately
- [ ] `lang` field matches file location
- [ ] Hero image generated, reviewed by user, and placed in `public/blog/`
- [ ] `heroImage` field set in both EN and ES frontmatter
- [ ] Links are valid and functional
