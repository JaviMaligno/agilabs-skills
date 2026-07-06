---
name: spotify-upload
description: >
  Upload podcast episodes to Spotify for Creators using browser automation.
  Use this skill whenever the user asks to upload, publish, or manage episodes
  on Spotify for Creators, or mentions uploading MP3s to their podcast.
  Handles the full wizard flow: file upload, metadata entry, review, and publish.
---

# Spotify Episode Upload Skill

Upload episodes to Spotify for Creators via browser automation (claude-in-chrome).

## Prerequisites

- Chrome browser with Claude extension connected
- User logged into https://creators.spotify.com
- Episode metadata file at `ensayo/audiobook/episodios_spotify.md`
- MP3 files in `ensayo/audiobook/`

## Episode Data

Read `ensayo/audiobook/episodios_spotify.md` to get the episode table. Each row has:
- `#` — upload order (1 = first uploaded, 21 = last uploaded)
- `Archivo` — MP3 filename
- `Titulo` — episode title for Spotify
- `Descripcion` — episode description for Spotify

### Episode numbering

There are 21 episodes total. The Spotify "episode number" is the episode's position
in the logical sequence (from chapter 00 to chapter 15), NOT the upload order.

Mapping (upload order # → Spotify episode number):

| # | Archivo | Spotify Ep # |
|---|---------|-------------|
| 1 | 15_conclusion.mp3 | 21 |
| 2 | 14_navegacion_individual.mp3 | 20 |
| 3 | 13_implicaciones_eticas.mp3 | 19 |
| 4 | 12_educacion_soberania.mp3 | 18 |
| 5 | 11b_evidencia_ley.mp3 | 17 |
| 6 | 11a_evidencia_ley.mp3 | 16 |
| 7 | 10_desinformacion_lenguaje.mp3 | 15 |
| 8 | 09_psicologia_dogma.mp3 | 14 |
| 9 | 08_no_volver_atras.mp3 | 13 |
| 10 | 07c_casos_limite.mp3 | 12 |
| 11 | 07b_casos_limite.mp3 | 11 |
| 12 | 07a_casos_limite.mp3 | 10 |
| 13 | 06_criterios_operativos.mp3 | 9 |
| 14 | 05b_sistemas_complejos.mp3 | 8 |
| 15 | 05a_sistemas_complejos.mp3 | 7 |
| 16 | 04_ciencia_decreto_descubrimiento.mp3 | 6 |
| 17 | 03b_dogmas_sesgos.mp3 | 5 |
| 18 | 03a_dogmas_sesgos.mp3 | 4 |
| 19 | 02_conocimiento_previo.mp3 | 3 |
| 20 | 01_ciencia_formalizacion.mp3 | 2 |
| 21 | 00_introduccion.mp3 | 1 |

Season is always **1**.

## Determining which episodes are already uploaded

Before starting, navigate to the episodes list page and read all published episode titles.
Compare against the full list to determine which remain. Process them in upload order
(highest upload # first among remaining).

## Workflow per episode

The Spotify for Creators URL is:
`https://creators.spotify.com/pod/show/<SHOW_ID>`

### Step 1: Navigate to wizard

Go to: `{base_url}/episode/wizard`

Wait for the page to load. You'll see "Subir audio o video" with a file upload area.

### Step 2: Request file from user (MANDATORY — cannot be automated)

Browser automation CANNOT interact with the native OS file picker dialog.
You must ask the user to select the file manually.

Tell the user:
> "Selecciona el archivo `{filename}` de `ensayo/audiobook/`"

Wait for the user to confirm they've selected the file. Do NOT proceed until confirmed.

### Step 3: Fill in Details

After file upload, the page automatically advances to the "Detalles" step.
Wait 3 seconds for the upload to complete if needed (check for upload progress bar).

#### Title
1. Click the title input field
2. Type the title directly — `type` works fine for titles

#### Description (CRITICAL — special handling required)

The description field is a rich text editor (contenteditable div), not a regular input.
Direct `type` action produces garbled text with encoding issues.
JavaScript `innerHTML` sets visible text but the form doesn't detect the change
(character counter stays at 0, validation fails, "Siguiente" button won't work).

**The only reliable method is clipboard paste:**

1. Use `javascript_tool` to copy text to clipboard:
   ```javascript
   navigator.clipboard.writeText('Your description text here')
   ```
2. Click inside the description editor area
3. Use `key` action: `cmd+a` to select any existing content
4. Use `key` action: `Backspace` to clear
5. Use `key` action: `cmd+v` to paste

Verify the character counter updates (should show > 0 / 4000). If it still shows 0,
the paste didn't register — click inside the editor and try cmd+v again.

#### Scroll down to additional fields

After title and description, scroll down to find:

- **Contenido explicito**: Leave as "No" (default)
- **Contenido promocional**: Leave as "No" (default)
- **Tipo de episodio**: Should be "Completo" (default radio, verify it's selected)
- **Numero de la temporada**: Type `1`
- **Numero del episodio**: Type the Spotify episode number (see mapping table above)

### Step 4: Click "Siguiente"

The "Siguiente" button is a sticky footer element at the bottom-right of the viewport.
Use `read_page` with `filter: interactive` to find the submit button (usually `type="submit"`),
then click it by ref.

If the page doesn't advance to "Revisar":
- Scroll up to check for validation errors (red borders, "Obligatorio" labels)
- The most common issue is the description not being detected — redo the clipboard paste method
- Verify character counter shows > 0

### Step 5: Review and Publish

The "Revisar" page shows a summary. Verify:
- Title is correct
- Description is correct
- Season = 1
- Episode number is correct

Scroll up to see the "Programar" section:
1. Select the "Ahora" radio button
2. Click "Publicar"

### Step 6: Handle post-publish banner

After publishing, a modal/banner appears with "Se ha publicado el episodio!" and
marketing content (follower stats, sharing buttons, etc.).

Close it by clicking the X button (usually top-right of the modal).

### Step 7: Continue to next episode

Navigate back to the wizard for the next episode:
`{base_url}/episode/wizard`

Repeat from Step 2.

## Error recovery

- **Page not loading**: Wait 3 seconds and take a screenshot to diagnose
- **Banner/popup blocking**: Look for close (X) buttons or "Listo" buttons and click them
- **Upload stuck**: Ask user to re-select the file
- **Form validation fails**: Check each required field; most likely the description needs re-pasting

## Communication style

Keep the user informed of progress:
- "Episodio X/21 publicado: {title}. Siguiente: {next_title}"
- When requesting file selection, be specific: "Selecciona `{filename}`"
- If something goes wrong, explain what happened and what you'll try next
