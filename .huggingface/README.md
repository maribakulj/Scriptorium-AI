---
title: Scriptorium AI
emoji: 📜
colorFrom: blue
colorTo: gold
sdk: docker
app_port: 7860
pinned: false
---

## Configuration HuggingFace Spaces

Ce Space utilise le SDK Docker. L'image est construite depuis le `Dockerfile`
à la racine du dépôt au moment du push.

### Secrets à configurer

Dans **Settings → Repository secrets**, renseigner selon le provider choisi :

| Secret | Description |
|--------|-------------|
| `AI_PROVIDER` | `google_ai_studio` \| `google_ai_api` \| `google_vertex` |
| `GOOGLE_AI_STUDIO_API_KEY` | Clé API Google AI Studio (si `AI_PROVIDER=google_ai_studio`) |
| `GOOGLE_AI_API_KEY` | Clé API Google AI (si `AI_PROVIDER=google_ai_api`) |
| `GOOGLE_VERTEX_PROJECT` | ID du projet GCP (si `AI_PROVIDER=google_vertex`) |
| `GOOGLE_VERTEX_LOCATION` | Région Vertex (défaut : `us-central1`) |

### Stockage des artefacts

Les images, JSON maîtres et exports XML sont stockés sur un **HuggingFace Dataset**
associé (pas dans l'image Docker). Le volume `/app/data` doit être monté via
le Dataset persistant du Space ou un Dataset dédié.

### Endpoints de vérification

```
GET /api/v1/profiles      → liste les 4 profils de corpus disponibles
GET /docs                 → documentation Swagger interactive
GET /api/v1/corpora       → liste des corpus ingérés
```
