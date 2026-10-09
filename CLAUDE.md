# KAM: instructions for Claude

Before anything else, read `../project-notes/KAM.md` if it exists. It is the private handbook and continues earlier conversations, so don't ask the owner to re-explain anything written there. A SessionStart hook pulls `project-notes` and loads the handbook automatically. If it's missing, clone `thedinz/project-notes` next to this repo.

Whenever you change something it describes or finish an open item, update it (Current status and Decisions log) and push `project-notes` immediately. Never put anything from it into this repo: this repo is public.

## Conventions

- Every commit, merge, tag and PR is authored and committed as `thedinz <68015411+thedinz@users.noreply.github.com>`. Check `git config user.name` / `user.email` before committing. Never add Co-Authored-By trailers or "Generated with" lines for any AI.
- Merge pull requests locally with `git merge --no-ff`, not GitHub's merge button.
- Feature and fix branches merge into `dev`; releases merge `dev` into `main` and are tagged `vX.Y.Z`. Every push to `main` rebuilds the public `ghcr.io/thedinz/kam:latest` image.
- KAM is a FastAPI backend (`app/`) with a React + Vite frontend (`frontend/`). `app/web/` is build output; don't commit it beyond the files already tracked there.

## Build and test

CI only builds the Docker image, so run the tests locally before merging code changes.

```bash
pip install -r requirements.txt pytest httpx
pytest
```

```bash
cd frontend
npm install
npm test
npm run build
```

Release: bump `KAM_VERSION_NUMBER` in `frontend/src/version.js` and add a `CHANGELOG.md` entry.
