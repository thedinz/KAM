# Changelog

## 7.2.0 — 2026-08-30

- Extend **Orphaned Assets** and **Duplicate Folders** cleanup to mapped collection
  roots while keeping collection and normal-library audits safely separated.
- Preserve collection context throughout cleanup navigation and use library-neutral
  asset labels and counts on movie, TV, and collection pages.
- Switch KAM to a newly retained collection folder before deleting its verified
  alternatives, including staged **Process all** resolutions.
- Scope persistent orphan exclusions to either normal assets or collections so the
  same folder name can be reviewed independently in both roots.
- Fix duplicate resolution for distinct filesystem folders whose exact names compare
  equal case-insensitively or contain otherwise invisible differences.

## 7.1.0 — 2026-08-30

- Add a per-library **Orphaned Assets** audit that compares asset folders with
  current Plex items and rechecks matches before permanent deletion.
- Protect valid title, year, and edition folder variations from orphan cleanup,
  including conservative handling for ambiguous remakes.
- Let users exclude known orphan false positives, review those exclusions later,
  and restore them to the audit without removing their artwork.
- Add a **Duplicate Folders** workflow for choosing the folder to retain while
  switching KAM to that folder before deleting verified alternatives.
- Support staging retained-folder choices across the full duplicate list and
  processing them together with library-neutral asset labels and result counts.

## 7.0.0 — 2026-08-29

- Redesign the KAM interface around a responsive application sidebar, updated
  branding, clearer page hierarchy, and refreshed library, detail, settings,
  mapping, and status surfaces.
- Replace duplicate library selectors with navigation generated from mapped
  Plex libraries, including nested per-library Collections views.
- Consolidate readiness progress into a contextual **Needs Attention** workflow
  that preserves movie, TV, and collection scope, counts, navigation, and return
  paths.
- Refine series and season artwork layouts, including expanded season cards and
  more consistent poster, background, title-card, and action placement.
- Improve route synchronization, initial sidebar library loading, collection
  hierarchy connectors, detail header alignment, responsive behavior, and the
  KAM favicon.

## 6.2.0 — 2026-08-21

- Add username-and-password built-in authentication with username configuration
  in Settings.
- Migrate password-only installations by prompting for a username on the first
  login while retaining compatibility with password-only login API clients.

## 6.1.0 — 2026-07-29

- Add optional automatic Plex artwork updates after uploads.
- Add manual **Send to Plex** controls for movies, collections, series, seasons,
  backgrounds, and episode title cards.
- Preserve successful asset uploads when an automatic Plex update fails.

## 1.8.1 — 2025-09-28
- Fix: Bulk 'Import Assets' for **Movies** now imports both `poster.jpg` and `background.jpg` via new `/api/import/movie`.
- UI: `index.html` now calls the combined endpoint (better progress message too).
- Backend: Adds `/api/import/movie`, reuses existing helpers; `/api/import/poster` and `/api/import/background` still available.
- No breaking or config changes.
