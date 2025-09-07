FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

COPY . /app
ENV PYTHONPATH=/app
EXPOSE 8000

# IMPORTANT: use the package, not the (renamed) kam_runner.py
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
