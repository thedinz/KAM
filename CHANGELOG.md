# Changelog

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
