# Scriptorium AI — image de production
# Build depuis la racine du dépôt :
#   docker build -f infra/Dockerfile -t scriptorium-ai .
#
# Structure attendue dans l'image :
#   /app/backend/app/   ← source Python (importable via PYTHONPATH)
#   /app/profiles/      ← profils JSON
#   /app/prompts/       ← templates de prompts
#   /app/data/          ← créé vide ; à monter en volume pour les artefacts

FROM python:3.11-slim

WORKDIR /app

# ── Dépendances système (lxml utilise des wheels binaires pré-compilés ;
#    aucun outil de build requis sur cette image) ─────────────────────────────
# Aucun paquet système supplémentaire nécessaire.

# ── Dépendances Python ─────────────────────────────────────────────────────
# On copie uniquement pyproject.toml pour exploiter le cache de layers Docker.
# Un stub app/__init__.py satisfait setuptools (discover packages) sans avoir
# besoin de copier tout le code source à ce stade.
COPY backend/pyproject.toml /tmp/build/
RUN mkdir -p /tmp/build/app \
    && touch /tmp/build/app/__init__.py \
    && pip install --no-cache-dir /tmp/build/ \
    && rm -rf /tmp/build

# ── Code source ────────────────────────────────────────────────────────────
# Copié APRÈS l'installation des dépendances pour conserver le cache.
COPY backend/app ./backend/app
COPY profiles/ ./profiles/
COPY prompts/ ./prompts/

# ── Répertoire des artefacts (vide dans l'image ; monté en volume) ─────────
RUN mkdir -p /app/data

# ── Secrets Google AI : JAMAIS dans l'image (R06) ─────────────────────────
# Passer au runtime via -e ou docker-compose environment :
#   AI_PROVIDER, GOOGLE_AI_STUDIO_API_KEY, GOOGLE_AI_API_KEY,
#   GOOGLE_VERTEX_PROJECT, GOOGLE_VERTEX_LOCATION

# PYTHONPATH permet l'import `app.main:app` depuis /app/backend/app/
ENV PYTHONPATH=/app/backend

EXPOSE 7860

# 1 worker au MVP — pas de Gunicorn, pas de multiprocessing
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
