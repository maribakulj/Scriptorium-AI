"""
Tests du générateur de Manifest IIIF 3.0 (Sprint 3 — Session C).

Vérifie :
- @context, id, type présents et corrects
- 1 Canvas par page dans l'ordre sequence (liste hors ordre)
- Dimensions Canvas = master.image.width / height
- Canvas contient 1 AnnotationPage avec 1 Annotation painting
- Image body : id = original_url, format = image/jpeg
- Annotation target = canvas id
- Manifest id contient base_url + manuscript_id
- Canvas id contient base_url + manuscript_id + page_id
- Label du manifest porte la langue et le titre
- Métadonnées optionnelles présentes si fournies, absentes sinon
- Manuscrit vide → ValueError explicite
- Champs obligatoires manquants → ValueError explicite
- JSON round-trip : json.loads(json.dumps(manifest)) sans perte
- write_manifest → data/corpora/{slug}/iiif/manifest.json
- Scénarios réalistes : Beatus HR+BR, Grandes Chroniques
"""
# 1. stdlib
import json
from datetime import datetime, timezone
from pathlib import Path

# 2. third-party
import pytest

# 3. local
from app.schemas.page_master import EditorialInfo, EditorialStatus, OCRResult, PageMaster, ProcessingInfo
from app.services.export.iiif import generate_manifest, write_manifest

_BASE_URL = "https://scriptorium-ai.example.com"
_IIIF_CONTEXT = "http://iiif.io/api/presentation/3/context.json"


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_page(
    page_id: str,
    folio_label: str,
    sequence: int,
    original_url: str = "",
    width: int = 1500,
    height: int = 2000,
) -> PageMaster:
    return PageMaster(
        page_id=page_id,
        corpus_profile="medieval-illuminated",
        manuscript_id="ms-test",
        folio_label=folio_label,
        sequence=sequence,
        image={
            "original_url": original_url or f"https://example.com/{folio_label}.jpg",
            "derivative_web": f"/data/deriv/{folio_label}.jpg",
            "thumbnail": f"/data/thumb/{folio_label}.jpg",
            "width": width,
            "height": height,
        },
        layout={"regions": []},
        editorial=EditorialInfo(status=EditorialStatus.MACHINE_DRAFT),
    )


def _base_meta(
    manuscript_id: str = "ms-test-001",
    label: str = "Test Manuscript",
    corpus_slug: str = "test-ms",
    **kwargs,
) -> dict:
    return {"manuscript_id": manuscript_id, "label": label, "corpus_slug": corpus_slug, **kwargs}


@pytest.fixture
def beatus_pages():
    return [
        _make_page(
            "beatus-lat8878-hr-f233", "f233-hr", 233,
            original_url="https://gallica.bnf.fr/iiif/ark:/12148/btv1b52505441p/f233/full/full/0/native.jpg",
            width=3543, height=4724,
        ),
        _make_page(
            "beatus-lat8878-br-f233", "f233-br", 234,
            original_url="https://gallica.bnf.fr/iiif/ark:/12148/btv1b52505441p/f233/full/600,/0/native.jpg",
            width=600, height=800,
        ),
    ]


@pytest.fixture
def beatus_meta():
    return {
        "manuscript_id": "BnF-Latin-8878",
        "label": "Beatus de Saint-Sever",
        "corpus_slug": "beatus-lat8878",
        "language": "la",
        "repository": "Bibliothèque nationale de France",
        "shelfmark": "Latin 8878",
        "date_label": "XIe siècle",
        "institution": "BnF",
    }


@pytest.fixture
def chroniques_pages():
    return [
        _make_page(
            "chroniques-btv1b84472995-f16", "f16", 16,
            original_url="https://gallica.bnf.fr/iiif/ark:/12148/btv1b84472995/f16/full/full/0/native.jpg",
            width=2952, height=3969,
        ),
    ]


@pytest.fixture
def chroniques_meta():
    return {
        "manuscript_id": "BnF-btv1b84472995",
        "label": "Grandes Chroniques de France",
        "corpus_slug": "grandes-chroniques",
        "language": "fr",
        "repository": "Bibliothèque nationale de France",
    }


@pytest.fixture
def simple_manifest(beatus_pages, beatus_meta):
    return generate_manifest(beatus_pages, beatus_meta, _BASE_URL)


# ---------------------------------------------------------------------------
# Tests — structure de premier niveau
# ---------------------------------------------------------------------------

def test_manifest_is_dict(simple_manifest):
    assert isinstance(simple_manifest, dict)


def test_manifest_context(simple_manifest):
    assert simple_manifest["@context"] == _IIIF_CONTEXT


def test_manifest_type(simple_manifest):
    assert simple_manifest["type"] == "Manifest"


def test_manifest_id_contains_base_url(simple_manifest):
    assert simple_manifest["id"].startswith(_BASE_URL)


def test_manifest_id_contains_manuscript_id(simple_manifest):
    assert "BnF-Latin-8878" in simple_manifest["id"]


def test_manifest_id_matches_endpoint(simple_manifest):
    """L'id suit le pattern /api/v1/manuscripts/{id}/iiif-manifest."""
    assert simple_manifest["id"] == (
        f"{_BASE_URL}/api/v1/manuscripts/BnF-Latin-8878/iiif-manifest"
    )


def test_manifest_has_label(simple_manifest):
    assert "label" in simple_manifest
    assert isinstance(simple_manifest["label"], dict)


def test_manifest_label_value(simple_manifest):
    label = simple_manifest["label"]
    # La valeur est dans une liste sous la clé langue
    all_values = [v for values in label.values() for v in values]
    assert "Beatus de Saint-Sever" in all_values


def test_manifest_has_metadata_key(simple_manifest):
    assert "metadata" in simple_manifest
    assert isinstance(simple_manifest["metadata"], list)


def test_manifest_has_items(simple_manifest):
    assert "items" in simple_manifest
    assert isinstance(simple_manifest["items"], list)


# ---------------------------------------------------------------------------
# Tests — label et langue
# ---------------------------------------------------------------------------

def test_manifest_label_uses_language_key(simple_manifest):
    """Le manifest Beatus (language='la') utilise 'la' comme clé de label."""
    assert "la" in simple_manifest["label"]


def test_manifest_label_without_language_uses_none():
    """Sans champ language, la clé de label est 'none'."""
    pages = [_make_page("ms-0001r", "0001r", 1)]
    meta = _base_meta()  # pas de language
    manifest = generate_manifest(pages, meta, _BASE_URL)
    assert "none" in manifest["label"]


def test_manifest_label_fr(chroniques_pages, chroniques_meta):
    manifest = generate_manifest(chroniques_pages, chroniques_meta, _BASE_URL)
    assert "fr" in manifest["label"]
    assert "Grandes Chroniques de France" in manifest["label"]["fr"]


# ---------------------------------------------------------------------------
# Tests — métadonnées
# ---------------------------------------------------------------------------

def test_manifest_metadata_repository(simple_manifest):
    labels = [
        entry["label"]["en"][0]
        for entry in simple_manifest["metadata"]
    ]
    assert "Repository" in labels


def test_manifest_metadata_shelfmark(simple_manifest):
    labels = [e["label"]["en"][0] for e in simple_manifest["metadata"]]
    assert "Shelfmark" in labels


def test_manifest_metadata_date(simple_manifest):
    labels = [e["label"]["en"][0] for e in simple_manifest["metadata"]]
    assert "Date" in labels


def test_manifest_metadata_value_content(simple_manifest):
    for entry in simple_manifest["metadata"]:
        if entry["label"]["en"][0] == "Repository":
            assert "nationale de France" in entry["value"]["none"][0]


def test_manifest_no_metadata_when_optional_absent():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    meta = _base_meta()  # aucun champ optionnel
    manifest = generate_manifest(pages, meta, _BASE_URL)
    assert manifest["metadata"] == []


def test_manifest_metadata_only_present_fields():
    """Seuls les champs fournis génèrent des entrées de métadonnée."""
    pages = [_make_page("ms-0001r", "0001r", 1)]
    meta = _base_meta(repository="BnF")  # uniquement repository
    manifest = generate_manifest(pages, meta, _BASE_URL)
    assert len(manifest["metadata"]) == 1
    assert manifest["metadata"][0]["label"]["en"][0] == "Repository"


# ---------------------------------------------------------------------------
# Tests — Canvas (1 par page, ordre sequence)
# ---------------------------------------------------------------------------

def test_one_canvas_per_page(simple_manifest):
    assert len(simple_manifest["items"]) == 2


def test_one_canvas_single_page():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    manifest = generate_manifest(pages, _base_meta(), _BASE_URL)
    assert len(manifest["items"]) == 1


def test_canvas_order_respects_sequence():
    """Pages dans le désordre → Canvas dans l'ordre croissant de sequence."""
    pages = [
        _make_page("ms-f003r", "f003r", 3),
        _make_page("ms-f001r", "f001r", 1),
        _make_page("ms-f002r", "f002r", 2),
    ]
    manifest = generate_manifest(pages, _base_meta(), _BASE_URL)
    labels = [c["label"]["none"][0] for c in manifest["items"]]
    assert labels == ["Folio f001r", "Folio f002r", "Folio f003r"]


def test_canvas_order_large_sequence():
    """10 pages mélangées → ordre garanti."""
    import random
    pages = [_make_page(f"ms-f{i:03d}r", f"f{i:03d}r", i) for i in range(1, 11)]
    random.shuffle(pages)
    manifest = generate_manifest(pages, _base_meta(), _BASE_URL)
    sequences_in_label = [
        int(c["label"]["none"][0].replace("Folio f", "").replace("r", ""))
        for c in manifest["items"]
    ]
    assert sequences_in_label == list(range(1, 11))


def test_canvas_type(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert canvas["type"] == "Canvas"


def test_canvas_id_contains_base_url(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert canvas["id"].startswith(_BASE_URL)


def test_canvas_id_contains_manuscript_id(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert "BnF-Latin-8878" in canvas["id"]


def test_canvas_id_contains_page_id(simple_manifest, beatus_pages):
    canvas_ids = {c["id"] for c in simple_manifest["items"]}
    for page in beatus_pages:
        assert any(page.page_id in cid for cid in canvas_ids)


def test_canvas_id_pattern(simple_manifest, beatus_pages):
    """Canvas id = {base_url}/api/v1/manuscripts/{ms_id}/canvas/{page_id}."""
    for canvas in simple_manifest["items"]:
        assert "/api/v1/manuscripts/BnF-Latin-8878/canvas/" in canvas["id"]


def test_canvas_label(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert "label" in canvas
        # label est un dict avec clé 'none' ou langue
        label_text = next(iter(canvas["label"].values()))[0]
        assert "Folio" in label_text


def test_canvas_folio_label_in_canvas_label(beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    canvas_labels = [
        next(iter(c["label"].values()))[0]
        for c in manifest["items"]
    ]
    assert any("f233-hr" in lbl for lbl in canvas_labels)
    assert any("f233-br" in lbl for lbl in canvas_labels)


# ---------------------------------------------------------------------------
# Tests — dimensions Canvas = master.image.width/height
# ---------------------------------------------------------------------------

def test_canvas_width_matches_image(beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    for canvas in manifest["items"]:
        # Trouve la page correspondante
        page_id = canvas["id"].split("/canvas/")[-1]
        page = next(p for p in beatus_pages if p.page_id == page_id)
        assert canvas["width"] == page.image["width"]


def test_canvas_height_matches_image(beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    for canvas in manifest["items"]:
        page_id = canvas["id"].split("/canvas/")[-1]
        page = next(p for p in beatus_pages if p.page_id == page_id)
        assert canvas["height"] == page.image["height"]


def test_canvas_dimensions_beatus_hr():
    """Dimensions exactes : Beatus HR = 3543×4724."""
    page = _make_page("ms-hr", "f233-hr", 1, width=3543, height=4724)
    manifest = generate_manifest([page], _base_meta(), _BASE_URL)
    canvas = manifest["items"][0]
    assert canvas["width"] == 3543
    assert canvas["height"] == 4724


def test_canvas_dimensions_chroniques(chroniques_pages, chroniques_meta):
    """Dimensions exactes : Grandes Chroniques = 2952×3969."""
    manifest = generate_manifest(chroniques_pages, chroniques_meta, _BASE_URL)
    canvas = manifest["items"][0]
    assert canvas["width"] == 2952
    assert canvas["height"] == 3969


def test_canvas_dimensions_are_integers(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert isinstance(canvas["width"], int)
        assert isinstance(canvas["height"], int)


# ---------------------------------------------------------------------------
# Tests — AnnotationPage et Annotation painting
# ---------------------------------------------------------------------------

def test_canvas_has_items_list(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert "items" in canvas
        assert isinstance(canvas["items"], list)
        assert len(canvas["items"]) >= 1


def test_canvas_has_exactly_one_annotation_page(simple_manifest):
    for canvas in simple_manifest["items"]:
        assert len(canvas["items"]) == 1
        assert canvas["items"][0]["type"] == "AnnotationPage"


def test_annotation_page_id_derived_from_canvas_id(simple_manifest):
    for canvas in simple_manifest["items"]:
        ann_page = canvas["items"][0]
        assert ann_page["id"].startswith(canvas["id"])


def test_annotation_page_has_items(simple_manifest):
    for canvas in simple_manifest["items"]:
        ann_page = canvas["items"][0]
        assert "items" in ann_page
        assert len(ann_page["items"]) == 1


def test_annotation_type(simple_manifest):
    for canvas in simple_manifest["items"]:
        ann = canvas["items"][0]["items"][0]
        assert ann["type"] == "Annotation"


def test_annotation_motivation_painting(simple_manifest):
    """motivation doit être 'painting' pour les images principales."""
    for canvas in simple_manifest["items"]:
        ann = canvas["items"][0]["items"][0]
        assert ann["motivation"] == "painting"


def test_annotation_target_is_canvas_id(simple_manifest):
    """La cible de l'annotation est l'id du Canvas parent."""
    for canvas in simple_manifest["items"]:
        ann = canvas["items"][0]["items"][0]
        assert ann["target"] == canvas["id"]


def test_annotation_body_type_image(simple_manifest):
    for canvas in simple_manifest["items"]:
        body = canvas["items"][0]["items"][0]["body"]
        assert body["type"] == "Image"


def test_annotation_body_format_jpeg(simple_manifest):
    for canvas in simple_manifest["items"]:
        body = canvas["items"][0]["items"][0]["body"]
        assert body["format"] == "image/jpeg"


def test_annotation_body_id_is_original_url(beatus_pages, beatus_meta):
    """L'id du body Image est l'original_url du PageMaster."""
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    for canvas in manifest["items"]:
        page_id = canvas["id"].split("/canvas/")[-1]
        page = next(p for p in beatus_pages if p.page_id == page_id)
        body = canvas["items"][0]["items"][0]["body"]
        assert body["id"] == page.image["original_url"]


def test_annotation_body_contains_gallica_url(beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    bodies = [c["items"][0]["items"][0]["body"] for c in manifest["items"]]
    assert any("gallica.bnf.fr" in b["id"] for b in bodies)


def test_annotation_body_dimensions_match_canvas(simple_manifest):
    """Les dimensions du body Image correspondent aux dimensions du Canvas."""
    for canvas in simple_manifest["items"]:
        body = canvas["items"][0]["items"][0]["body"]
        assert body["width"] == canvas["width"]
        assert body["height"] == canvas["height"]


# ---------------------------------------------------------------------------
# Tests — base_url paramétrable
# ---------------------------------------------------------------------------

def test_different_base_url(beatus_pages, beatus_meta):
    alt_url = "https://my-custom-domain.org"
    manifest = generate_manifest(beatus_pages, beatus_meta, alt_url)
    assert manifest["id"].startswith(alt_url)
    for canvas in manifest["items"]:
        assert canvas["id"].startswith(alt_url)


def test_base_url_trailing_slash_stripped():
    """Un base_url avec slash final ne génère pas de double slash dans les IDs."""
    pages = [_make_page("ms-0001r", "0001r", 1)]
    manifest = generate_manifest(pages, _base_meta(), "https://example.com/")
    assert "//" not in manifest["id"].replace("://", "X")


# ---------------------------------------------------------------------------
# Tests — JSON round-trip
# ---------------------------------------------------------------------------

def test_json_roundtrip(simple_manifest):
    """Le manifest survit à json.dumps → json.loads sans perte."""
    serialized = json.dumps(simple_manifest, ensure_ascii=False)
    recovered = json.loads(serialized)
    assert recovered["@context"] == _IIIF_CONTEXT
    assert recovered["type"] == "Manifest"
    assert len(recovered["items"]) == len(simple_manifest["items"])


def test_json_roundtrip_preserves_dimensions(simple_manifest):
    serialized = json.dumps(simple_manifest)
    recovered = json.loads(serialized)
    for orig, rec in zip(simple_manifest["items"], recovered["items"]):
        assert rec["width"] == orig["width"]
        assert rec["height"] == orig["height"]


def test_json_no_non_serializable_types(simple_manifest):
    """json.dumps ne doit lever aucune exception (pas de datetime, Path, etc.)."""
    try:
        json.dumps(simple_manifest)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"Manifest non sérialisable en JSON : {exc}")


def test_json_roundtrip_chroniques(chroniques_pages, chroniques_meta):
    manifest = generate_manifest(chroniques_pages, chroniques_meta, _BASE_URL)
    recovered = json.loads(json.dumps(manifest, ensure_ascii=False))
    assert recovered["items"][0]["width"] == 2952
    assert recovered["items"][0]["height"] == 3969


# ---------------------------------------------------------------------------
# Tests — erreurs explicites
# ---------------------------------------------------------------------------

def test_empty_masters_raises():
    with pytest.raises(ValueError, match="vide"):
        generate_manifest([], _base_meta(), _BASE_URL)


def test_missing_manuscript_id_raises():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    with pytest.raises(ValueError, match="manuscript_id"):
        generate_manifest(pages, {"label": "X", "corpus_slug": "x"}, _BASE_URL)


def test_missing_label_raises():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    with pytest.raises(ValueError, match="label"):
        generate_manifest(pages, {"manuscript_id": "ms-x", "corpus_slug": "x"}, _BASE_URL)


def test_missing_corpus_slug_raises():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    with pytest.raises(ValueError, match="corpus_slug"):
        generate_manifest(pages, {"manuscript_id": "ms-x", "label": "X"}, _BASE_URL)


def test_empty_string_manuscript_id_raises():
    pages = [_make_page("ms-0001r", "0001r", 1)]
    with pytest.raises(ValueError, match="manuscript_id"):
        generate_manifest(pages, {"manuscript_id": "", "label": "X", "corpus_slug": "x"}, _BASE_URL)


# ---------------------------------------------------------------------------
# Tests — write_manifest
# ---------------------------------------------------------------------------

def test_write_manifest_creates_file(tmp_path, beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    write_manifest(manifest, "beatus-lat8878", base_data_dir=tmp_path)
    expected = tmp_path / "corpora" / "beatus-lat8878" / "iiif" / "manifest.json"
    assert expected.exists()


def test_write_manifest_creates_iiif_subdir(tmp_path, beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    write_manifest(manifest, "beatus-lat8878", base_data_dir=tmp_path)
    assert (tmp_path / "corpora" / "beatus-lat8878" / "iiif").is_dir()


def test_write_manifest_content_is_valid_json(tmp_path, beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    write_manifest(manifest, "beatus-lat8878", base_data_dir=tmp_path)
    path = tmp_path / "corpora" / "beatus-lat8878" / "iiif" / "manifest.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["type"] == "Manifest"
    assert loaded["@context"] == _IIIF_CONTEXT


def test_write_manifest_context_preserved(tmp_path, beatus_pages, beatus_meta):
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)
    write_manifest(manifest, "beatus-lat8878", base_data_dir=tmp_path)
    path = tmp_path / "corpora" / "beatus-lat8878" / "iiif" / "manifest.json"
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["@context"] == _IIIF_CONTEXT


# ---------------------------------------------------------------------------
# Tests — scénarios réalistes Sprint 2
# ---------------------------------------------------------------------------

def test_beatus_manifest_full(beatus_pages, beatus_meta):
    """Scénario complet Beatus HR + BR : 2 canvases, URLs Gallica."""
    manifest = generate_manifest(beatus_pages, beatus_meta, _BASE_URL)

    assert manifest["type"] == "Manifest"
    assert len(manifest["items"]) == 2

    # Canvas dans l'ordre (sequence 233 < 234)
    first_canvas_id = manifest["items"][0]["id"]
    assert "beatus-lat8878-hr-f233" in first_canvas_id

    # Les deux canvases ont des dimensions différentes
    widths = {c["width"] for c in manifest["items"]}
    assert len(widths) == 2  # HR = 3543, BR = 600

    # URLs Gallica
    bodies = [c["items"][0]["items"][0]["body"] for c in manifest["items"]]
    assert all("gallica.bnf.fr" in b["id"] for b in bodies)

    # Métadonnées présentes
    meta_labels = [e["label"]["en"][0] for e in manifest["metadata"]]
    assert "Repository" in meta_labels
    assert "Shelfmark" in meta_labels
    assert "Date" in meta_labels


def test_chroniques_manifest_full(chroniques_pages, chroniques_meta):
    """Scénario Grandes Chroniques : 1 canvas, langue fr, URL Gallica."""
    manifest = generate_manifest(chroniques_pages, chroniques_meta, _BASE_URL)

    assert len(manifest["items"]) == 1
    canvas = manifest["items"][0]

    # Dimensions correctes
    assert canvas["width"] == 2952
    assert canvas["height"] == 3969

    # URL Gallica dans le body
    body = canvas["items"][0]["items"][0]["body"]
    assert "btv1b84472995" in body["id"]

    # Langue française dans le label
    assert "fr" in manifest["label"]

    # Manifest sérialisable
    assert json.loads(json.dumps(manifest, ensure_ascii=False))
