# Scriptorium AI — image de production (multi-stage)
# Ce fichier est utilisé par HuggingFace Spaces (SDK docker, détection automatique).
# Il doit rester synchronisé avec infra/Dockerfile.
#
# Build depuis la racine du dépôt :
#   docker build -t scriptorium-ai .

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
    && pip install --no-cache-dir --upgrade /tmp/build/ \
    && rm -rf /tmp/build

# ── Layer dédié mistralai — garantit v1.x même si le cache pip résout autrement ──
# Layer séparé pour s'assurer que mistralai>=1.0 est bien installé.
# Sans cette ligne, une résolution de dépendances conflictuelle peut installer v0.x.
RUN pip install --no-cache-dir 'mistralai>=1.0,<2.0'

# ── Code source backend ────────────────────────────────────────────────────
COPY backend/app ./backend/app
COPY profiles/ ./profiles/
COPY prompts/ ./prompts/

# ── Frontend buildé ────────────────────────────────────────────────────────
COPY --from=frontend-builder /frontend/dist ./static

# ── Répertoire des artefacts (vide dans l'image ; monté en volume) ─────────
RUN mkdir -p /app/data

# ── Secrets : JAMAIS dans l'image (R06) ────────────────────────────────────
# Passer au runtime via les Secrets HuggingFace Spaces :
#   GOOGLE_AI_STUDIO_API_KEY, MISTRAL_API_KEY, VERTEX_SERVICE_ACCOUNT_JSON

# PYTHONPATH permet l'import `app.main:app` depuis /app/backend/app/
ENV PYTHONPATH=/app/backend
ENV PROFILES_DIR=/app/profiles
ENV PROMPTS_DIR=/app/prompts
ENV DATA_DIR=/app/data

EXPOSE 7860

# 1 worker au MVP — pas de Gunicorn, pas de multiprocessing
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
