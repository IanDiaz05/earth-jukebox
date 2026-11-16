# AI-agent ingestion skill

**Skill:** `spotiearth-timelapse-ingest`

The project includes a custom skill that lets an AI agent run the full data
ingestion process with the CLI tools in `scripts/`. Given a directory of frame
folders and a Markdown or text description file, the agent can generate and
insert every playlist and track: it chooses profiles, writes slugs, titles,
descriptions, categories, and playback order, then calls the ingest CLIs.

## Skill location

The canonical copy is:

```text
.agents/skills/spotiearth-timelapse-ingest/SKILL.md
```

Copies for specific tools are kept in sync:

```text
.claude/skills/spotiearth-timelapse-ingest/SKILL.md
.cursor/skills/spotiearth-timelapse-ingest/SKILL.md
```

When the skill changes, update the canonical copy and sync the other two.

## What the skill provides

The skill is an operating procedure, not a separate program. It gives the agent:

- **The input contract.** One immediate child folder with images is one track;
  all frames must share dimensions and visualization; only frame formats are
  accepted; frames are ordered by their numeric filenames.
- **The description-file contract.** The agent reads the whole file, matches
  descriptions to folders by name, slug, heading, or an explicit `folder:` field,
  and treats supplied facts as the source of truth.
- **The output contract.** For each track the agent decides the directory,
  profile, slug, title, description, playlist, sequence order, optional event
  date, and optional public frame URL/extension.
- **The profile catalog.** Only the 15 IDs in `PROFILES` may be used. If a
  visualization has no profile, the agent stops and reports that a code change is
  required.
- **Editorial standards.** Slugs are lowercase ASCII kebab-case and globally
  unique; titles are short and factual; descriptions are 1–3 plain-text
  sentences; categories use the canonical values; order is preserved or assigned
  contiguously.
- **The workflow.** Preflight, inventory, map descriptions, choose profiles,
  generate metadata, dry-run, create playlists, ingest sequentially, verify, and
  report.
- **Safety guardrails.** The rules below are mandatory, not suggestions.

## Agent workflow with the CLIs

1. **Preflight.** Run from the repository root and check the database and the
   available profiles:

   ```bash
   python scripts/ingest_playlist.py list --limit 100
   python -c "from app.cv_engine import PROFILES; print('\n'.join(sorted(PROFILES)))"
   ```

2. **Inventory.** List the immediate folders and count frames. Inspect the first,
   middle, and last frame of each track to confirm the visualization and order.

3. **Map descriptions and build a plan.** For every folder record the profile,
   playlist, slug, title, sequence order, event date, and any public frames URL.

4. **Dry-run every track.** Use `--dry-run --out` and review the JSON before any
   database write:

   ```bash
   python scripts/ingest_timelapse.py \
     --dir "$TRACK_DIR" \
     --profile "$PROFILE" \
     --slug "$TRACK_SLUG" \
     --title "$TRACK_TITLE" \
     --description "$TRACK_DESCRIPTION" \
     --playlist-slug "$PLAYLIST_SLUG" \
     --sequence-order "$ORDER" \
     --dry-run \
     --out "/tmp/opencode/ingest/$TRACK_SLUG.json"
   ```

5. **Create or reuse playlists.**

   ```bash
   python scripts/ingest_playlist.py show --slug "$PLAYLIST_SLUG"
   python scripts/ingest_playlist.py create \
     --slug "$PLAYLIST_SLUG" \
     --title "$PLAYLIST_TITLE" \
     --category "$CATEGORY" \
     --description "$PLAYLIST_DESCRIPTION"
   ```

6. **Ingest tracks sequentially.** Run the same dry-run command without
   `--dry-run` and `--out`. Do not run concurrent writers against one playlist.

7. **Verify.** Use `ingest_playlist.py show` and, when the API is running, fetch
   the playlist and track endpoints.

8. **Report.** Return the playlist slug, ID, title, category, and track count;
   each track's slug, ID, profile, frame count, and order; engine warnings;
   skipped folders and the reason; and any generated descriptions or assumptions.

## Safety guardrails

The skill requires the agent to:

- Dry-run every track before writing.
- Create the playlist before ingesting its tracks.
- Use only the registered profiles and never improvise a new one.
- Never invent titles, descriptions, dates, locations, units, or measurements.
- Never use `--replace` blindly; it overwrites content and can move a track to
  another playlist.
- Never delete a playlist without explicit user confirmation; deletion removes
  all of its tracks.
- Keep slugs stable after ingestion.
- Keep descriptions plain text, with no Markdown, bullets, links, or line breaks.
- Ingest sequentially.
- Use the CLIs instead of raw SQL for playlist and track writes.
- Never edit engine code, profiles, or color tables during ingestion.

There is no CLI to update or delete a single track. Re-measuring an existing track
uses `--replace`; removing one track requires direct database work or a new
endpoint, with explicit user approval.

## Editorial defaults

| Item | Default |
|---|---|
| Language | English, unless the description file or the user asks otherwise |
| Slugs and categories | Always English lowercase ASCII |
| Track slug | Profile or variable plus a scope, such as `sst-anomaly-2003-2026` |
| Track title | What the visualization shows plus scope, Title Case, no trailing period |
| Description | 1–3 factual sentences, usually 120–320 characters |
| Playlist grouping | One category playlist when all tracks share a category, otherwise `earth-timelapses` |
| Sequence order | Preserve the file order, or assign contiguous integers starting at `0` |
| Event date | ISO date only when known; never the ingestion date |
| Featured flag | `false` unless explicitly requested |

The skill treats the engine's profile `label` and `hints.words` as Spanish
frontend text, not as editorial titles or descriptions.

## Why the skill exists

Ingestion can overwrite tracks and delete whole playlists, and its quality depends
on consistent editorial decisions. The skill makes the process repeatable for an
agent:

- The same input layout and description format are handled the same way.
- Every measurement is validated before a write.
- Metadata follows fixed limits and naming rules.
- Destructive operations require explicit confirmation.
- The final report states exactly what was created, skipped, or assumed.

For the underlying commands and data flow, see
[ingestion.md](ingestion.md). For the service that stores the result, see
[services-ingestion.md](services-ingestion.md).
