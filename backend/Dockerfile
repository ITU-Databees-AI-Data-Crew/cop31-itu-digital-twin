# Backend: FastAPI + agent + simulation engine, with the year of data generated at build time.
# Build from the repo root (it needs data/inputs/):  docker compose build backend

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Same layout as the repo (/srv = repo root), because the code finds data/ relative to itself.
WORKDIR /srv/backend

# Dependencies first, so code changes don't reinstall them.
COPY backend/pyproject.toml ./
RUN mkdir app && touch app/__init__.py && pip install -e . && rm -rf app

COPY backend/app ./app
COPY data/inputs /srv/data/inputs

# Generate data/generated/campus.db (seeded: same data every build).
RUN python -m app.generator

# What-ifs live here; docker-compose mounts a volume so they survive restarts.
RUN mkdir -p /srv/data/state
VOLUME /srv/data/state

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
