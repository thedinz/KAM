# Changelog

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
