FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GEOROUTE_PROMPT_RANKER=lexical \
    GEOROUTE_USER_HISTORY_PATH=data/user_histories_osm_trace.json \
    OSMNX_CACHE_FOLDER=/tmp/osmnx_cache

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-deploy.txt

COPY app app
COPY data/user_histories_osm_trace.json data/user_histories_osm_trace.json

EXPOSE 7860

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
