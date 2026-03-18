# Scriptorium AI — image de production (multi-stage)
# Ce fichier est la copie exacte de Dockerfile (racine).
# Build depuis la racine du dépôt :
#   docker build -f infra/Dockerfile -t scriptorium-ai .
#
# Structure attendue dans l'image :
#   /app/backend/app/   ← source Python (importable via PYTHONPATH)
#   /app/profiles/      ← profils JSON
#   /app/prompts/       ← templates de prompts
#   /app/static/        ← frontend React buildé
#   /app/data/          ← créé vide ; à monter en volume pour les artefacts

# ── Stage 1 : build du frontend React ────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Installer les dépendances (cache layer séparé)
COPY frontend/package.json ./
RUN npm install

# Copier les sources et builder
COPY frontend/ ./
RUN npm run build

# ── Stage 2 : image Python finale ────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# ── Dépendances Python ─────────────────────────────────────────────────────
# On copie uniquement pyproject.toml pour exploiter le cache de layers Docker.
# Un stub app/__init__.py satisfait setuptools (discover packages) sans avoir
# besoin de copier tout le code source à ce stade.
COPY backend/pyproject.toml /tmp/build/
RUN mkdir -p /tmp/build/app \
    && touch /tmp/build/app/__init__.py \
    && pip install --no-cache-dir /tmp/build/ \
    && rm -rf /tmp/build

# ── Code source backend ────────────────────────────────────────────────────
COPY backend/app ./backend/app
COPY profiles/ ./profiles/
COPY prompts/ ./prompts/

# ── Frontend buildé ────────────────────────────────────────────────────────
COPY --from=frontend-builder /frontend/dist ./static

# ── Répertoire des artefacts (vide dans l'image ; monté en volume) ─────────
RUN mkdir -p /app/data

# ── Secrets Google AI : JAMAIS dans l'image (R06) ─────────────────────────
# Passer au runtime via -e ou docker-compose environment :
#   AI_PROVIDER, GOOGLE_AI_STUDIO_API_KEY, GOOGLE_AI_API_KEY,
#   GOOGLE_VERTEX_PROJECT, GOOGLE_VERTEX_LOCATION

# PYTHONPATH permet l'import `app.main:app` depuis /app/backend/app/
ENV PYTHONPATH=/app/backend
ENV PROFILES_DIR=/app/profiles
ENV PROMPTS_DIR=/app/prompts
ENV DATA_DIR=/app/data

EXPOSE 7860

# 1 worker au MVP — pas de Gunicorn, pas de multiprocessing
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
