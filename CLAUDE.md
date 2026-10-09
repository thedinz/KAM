# KAM: instructions for Claude

## Project handbook

Before anything else, read `standards.md` and `KAM.md` in the owner's private `project-notes` repo. The SessionStart hook in `.claude/settings.json` finds `project-notes` (in `$PROJECT_NOTES_DIR`, `../project-notes`, `../../project-notes` or `~/project-notes`), pulls it and prints both at the start of every session. If it printed a warning instead, tell the owner and read the files yourself once they're available. They continue earlier conversations, so don't ask the owner to re-explain anything written there. Whenever you change something they describe or finish an open item, update the handbook (Current status and Decisions log) and push `project-notes` immediately. Never put anything from `project-notes` into this repo.

## Conventions

- Every commit, merge, tag and PR is authored and committed as `thedinz <68015411+thedinz@users.noreply.github.com>`. Check `git config user.name` / `user.email` before committing. Never add Co-Authored-By trailers or "Generated with" lines for any AI.
- Merge pull requests locally with `git merge --no-ff`, not GitHub's merge button.
- Feature and fix branches merge into `dev`; releases merge `dev` into `main` and are tagged `vX.Y.Z`. Every push to `main` rebuilds the public `ghcr.io/thedinz/kam:latest` image.
- KAM is a FastAPI backend (`app/`) with a React + Vite frontend (`frontend/`). `app/web/` is build output; don't commit it beyond the files already tracked there.

## Build and test

The Tests workflow runs pytest (Python 3.11) and vitest plus the build (Node 20) on every pull request; merge only when it passes.

```bash
pip install -r requirements.txt pytest httpx
pytest
```

```bash
cd frontend
npm ci
npx vitest run
npm run build
```

Release: bump `KAM_VERSION_NUMBER` in `frontend/src/version.js` and add a `CHANGELOG.md` entry.
