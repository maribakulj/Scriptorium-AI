---
title: Scriptorium AI
emoji: 📜
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# Scriptorium AI

Plateforme générique de génération d'éditions savantes augmentées pour documents
patrimoniaux numérisés : manuscrits médiévaux, incunables, cartulaires, archives,
chartes, papyri — tout type de document, toute époque, toute langue.

---

## Structure du dépôt

```
scriptorium-ai/
├── backend/            # API FastAPI + pipeline Python
│   ├── app/
│   │   ├── api/v1/     # endpoints REST (/api/v1/...)
│   │   ├── models/     # tables SQLAlchemy (SQLite async)
│   │   ├── schemas/    # modèles Pydantic v2
│   │   └── services/   # ingest / image / ai / export / search
│   ├── tests/          # suite pytest (477 tests)
│   └── pyproject.toml
├── profiles/           # 4 profils de corpus JSON
├── prompts/            # templates de prompts par profil
├── infra/              # Dockerfile + docker-compose (dev local)
├── Dockerfile          # copie du Dockerfile pour HuggingFace Spaces
└── data/               # artefacts runtime — NON versionné
```

---

## Lancer en local (Docker)

```bash
# 1. Cloner le dépôt
git clone https://github.com/<org>/scriptorium-ai && cd scriptorium-ai

# 2. Définir les variables d'environnement
cp .env.example .env          # puis renseigner les clés dans .env

# 3. Démarrer le service
docker compose -f infra/docker-compose.yml up --build

# 4. Vérifier
curl http://localhost:7860/api/v1/profiles
```

L'API est accessible sur `http://localhost:7860`. La documentation interactive
Swagger est disponible sur `http://localhost:7860/docs`.

---

## Lancer les tests

```bash
cd backend
pip install -e ".[dev]"
pytest tests/ -v --cov=app
```

Résultat attendu : **477 passed, 3 skipped**.

---

## Profils disponibles

| Profil | Description |
|--------|-------------|
| `medieval-illuminated` | Manuscrits médiévaux enluminés (OCR diplomatique, iconographie, commentaire) |
| `medieval-textual`     | Manuscrits médiévaux textuels (OCR, traduction, commentaire savant) |
| `early-modern-print`   | Imprimés anciens (incunables, livres des XVIe–XVIIIe siècles) |
| `modern-handwritten`   | Documents manuscrits modernes (cursive, archives, chartes) |

```bash
# Lister les profils via l'API
curl http://localhost:7860/api/v1/profiles
```

---

## Providers Google AI

Trois modes d'authentification sont supportés. Sélectionner via `AI_PROVIDER`.

| Provider | Variable `AI_PROVIDER` | Variables d'environnement requises |
|----------|------------------------|-------------------------------------|
| Google AI Studio (clé API) | `google_ai_studio` | `GOOGLE_AI_STUDIO_API_KEY` |
| Google AI API (legacy) | `google_ai_api` | `GOOGLE_AI_API_KEY` |
| Google Vertex AI | `google_vertex` | `GOOGLE_VERTEX_PROJECT`, `GOOGLE_VERTEX_LOCATION` |

Les clés ne doivent **jamais** figurer dans le code, les commits ou l'image Docker.
Sur HuggingFace Spaces, les renseigner dans **Settings → Repository secrets**.

---

## Déploiement HuggingFace Spaces

Ce dépôt est configuré pour HuggingFace Spaces (SDK Docker, port 7860).
Les artefacts de traitement (images, JSON maîtres, exports XML) sont stockés
sur HuggingFace Datasets — pas dans l'image Docker.

Voir `.huggingface/README.md` pour la configuration spécifique du Space.
