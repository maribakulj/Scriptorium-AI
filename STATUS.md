# STATUS.md

## Sprint en cours : 1 — Session A
## Dernière mise à jour : [date]

## Ce qui est fait
- [x] Repo créé, arborescence en place
- [x] CLAUDE.md créé
- [ ] Schémas Pydantic
- [ ] Tests pytest

## Ce qui bloque
Rien.

## Objectif de la prochaine session
Créer les modèles Pydantic dans backend/app/schemas/.
Voir section "Tâches" ci-dessous.

## Tâches (dans l'ordre)
1. corpus_profile.py — CorpusProfile + enums
2. page_master.py — Region, PageMaster + validators
3. annotation.py — AnnotationLayer
4. tests/test_schemas.py — 20+ tests
5. Lancer pytest → 0 failed

## Critère de done
pytest 100%. Les 4 profils JSON chargés sans erreur.

## Décisions récentes
- bbox : [x, y, w, h] pixels absolus (voir R03 dans CLAUDE.md)
- SQLite retenu pour MVP HuggingFace

## Ne pas faire dans cette session
Aucun appel Google AI. Aucune API FastAPI.
```
