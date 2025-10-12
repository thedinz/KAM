FROM node:20 AS frontend-build
WORKDIR /workspace
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
COPY app/web/fallback.png ./app/web/fallback.png
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
COPY --from=frontend-build /workspace/app/web /app/app/web
ENV PYTHONPATH=/app
EXPOSE 8000

# IMPORTANT: use the package, not the (renamed) kam_runner.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
