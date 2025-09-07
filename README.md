Perfect — here’s the tweaked version of the **install instructions** with **series posters, season posters, and background posters** included. I’ll keep it in the same style we drafted, just expanding the “Folder rules & naming” and “Usage” parts.

---

# KAM — Kometa Asset Manager

KAM is a tiny web app we built to make Kometa/Plex poster management painless. It lets you upload a poster for a movie, show, season, or collection and will:

* Convert the upload to **.jpg**
* **Replace** any existing `poster.*` or `background.*` in the matching Kometa asset folder
* Keep your asset folders in the **same structure Kometa expects**
* Provide a simple web UI to check what’s set (with a fallback image when missing)

---

## Important constraints (read this first)

> **At the current moment the app does NOT allow you to use a myriad of different asset directories, for now you need to pair 1 library with 1 directory. Example *Kids Movies* with `/assets/Kids Movies`. Similarly all collections must reside in 1 `Collections` directory.**

What this means in practice:

* Pick **one** assets root for a given library and stick with it.
* If you have multiple libraries, each one should have its **own** mapped directory.
* All Kometa **Collections** live under a single `Collections` folder within the mapped assets root.

---

## How asset mapping works

Inside the container, KAM expects an **assets root** at a path you choose (we’ll use `/assets` inside the container for clarity). You can bind-mount **any** host path to `/assets`.

Examples:

* Map your Unraid folder:
  Host: `/mnt/user/kometa/assets` → Container: `/assets`
* Or map a custom path:
  Host: `/mystuff` → Container: `/assets`

The point: **KAM doesn’t care** what the host path is, as long as you mount it into the container at the internal path you configure (examples below use `/assets`).

Typical Kometa-style structure under that mapped root:

```
/assets
  /Movies
    /The Matrix (1999)
      poster.jpg
      background.jpg
  /TV Shows
    /Breaking Bad
      poster.jpg
      background.jpg
      /Season 01
        poster.jpg
      /Season 02
        poster.jpg
  /Collections
    /Batman Collection
      poster.jpg
      background.jpg
```

KAM writes into these folders, converting to `.jpg` and replacing any existing poster/background file.

---

## Requirements

* Docker (Unraid, Linux, macOS, or Windows)
* Access to your Kometa **assets** folders (bind-mount them read/write)
* Optional: a reverse proxy (Caddy/Traefik/Nginx) if you want TLS

---

## Quick Start (Docker)

### Pull the image

```bash
docker pull ghcr.io/thedinz/kam:latest
```

### Run (simple example)

```bash
docker run -d \
  --name kam \
  -p 7171:7171 \
  -v /mnt/user/kometa/assets:/assets \
  ghcr.io/thedinz/kam:latest
```

Open: `http://<your-host>:7171/`

### Docker Compose

```yaml
services:
  kam:
    image: ghcr.io/thedinz/kam:latest
    container_name: kam
    ports:
      - "7171:7171"
    volumes:
      - /mnt/user/kometa/assets:/assets
    restart: unless-stopped
```

---

## Usage overview

* Browse to the web UI (default index page).
* Pick the library item or collection you want to update.
* Upload a poster or background image.
  KAM will:

  * Convert to `.jpg`
  * Remove any existing `poster.*` or `background.*` in that item’s asset folder
  * Save the new file

If an item has **no** artwork yet, KAM shows a **fallback** image in the UI so you can spot missing posters/backgrounds quickly.

---

## Folder rules & naming

KAM follows Kometa’s asset layout conventions:

* **Movies**:
  `Movies/<Title (Year)>/poster.jpg`
  `Movies/<Title (Year)>/background.jpg`

* **TV Shows (series)**:
  `TV Shows/<Show Name>/poster.jpg`
  `TV Shows/<Show Name>/background.jpg`

* **Seasons**:
  `TV Shows/<Show Name>/Season 01/poster.jpg`
  `TV Shows/<Show Name>/Season 02/poster.jpg`

* **Collections**:
  `Collections/<Collection Name>/poster.jpg`
  `Collections/<Collection Name>/background.jpg`

KAM **does not** invent proprietary paths. It writes exactly where Kometa expects.

**Sanitization:** KAM keeps a **sane level of filename sanitization** to avoid OS/share issues.

---

## Environment & configuration

* **Port:** Default container port is **7171**.
* **Assets root:** Mount host assets to `/assets` inside the container.

If you run multiple libraries, follow the **1 library → 1 directory** rule (e.g., separate containers or subfolders).

---

## Updates

```bash
docker pull ghcr.io/thedinz/kam:latest
docker stop kam && docker rm kam
# re-run your docker run / compose up -d
```

---

## Troubleshooting

* **Fallback shows instead of the poster/background** → upload one or verify naming (`poster.jpg`, `background.jpg`).
* **Seasons missing posters** → ensure the subfolder is named `Season 01`, `Season 02`, etc.
* **Permission errors** → check your Docker volume mapping and filesystem permissions.

---

## FAQ

**Can I use multiple asset roots at once?**
Not yet. One library ↔ one directory, all collections in one `Collections` folder.

**Can I map my assets to any path I want?**
Yes — map any host folder into the container.

**Does KAM handle backgrounds too?**
Yes — it supports both `poster.jpg` and `background.jpg` for movies, shows, and collections.

**What about seasons?**
Yes — KAM supports `poster.jpg` inside season subfolders (`Season 01`, `Season 02`, etc.).
