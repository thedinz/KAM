# KAM

KAM is a FastAPI-based tool to manage posters and assets for Kometa.

## Quickstart (development on Ubuntu with Docker Compose)

```bash
# clone repo
git clone https://github.com/thedinz/KAM.git
cd KAM

# copy env template
cp .env.example .env
# edit .env with your Plex token + library paths

# build and run
docker compose build
docker compose up -d

# open
http://localhost:7171
# trigger rebuild
