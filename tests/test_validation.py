"""Validación de entradas: contratos Pydantic, UUIDs, tamaños y extensiones."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.errors import PayloadTooLargeError, ValidationError as AppValidationError
from app.core.security import validate_extension, validate_payload_size, validate_uuid
from app.models.evidence import Evidence
from app.models.opportunity import OpportunityCreate


def test_opportunity_create_requires_min_lengths():
    with pytest.raises(ValidationError):
        OpportunityCreate(title="ab", problem="problema suficientemente largo")  # título demasiado corto
    with pytest.raises(ValidationError):
        OpportunityCreate(title="Título válido", problem="corto")  # problema demasiado corto


def test_opportunity_rejects_extra_fields():
    with pytest.raises(ValidationError):
        OpportunityCreate(title="T", problem="Problema de longitud suficiente aquí.", extra="no permitido")


def test_evidence_rejects_bad_type():
    with pytest.raises(ValidationError):
        Evidence(opportunity_id="a", evidence_type="hack", summary="x")


def test_evidence_rejects_bad_url_scheme():
    with pytest.raises(ValidationError):
        Evidence(opportunity_id="a", evidence_type="other", summary="x", source_url="javascript:alert(1)")


def test_evidence_reliability_range():
    with pytest.raises(ValidationError):
        Evidence(opportunity_id="a", evidence_type="other", summary="x", reliability_score=1.5)


def test_validate_uuid_rejects_bad_values():
    with pytest.raises(AppValidationError):
        validate_uuid("../../etc/passwd")
    with pytest.raises(AppValidationError):
        validate_uuid("not-a-uuid")
    assert validate_uuid("a" * 32) == "a" * 32


def test_payload_size_limit():
    with pytest.raises(PayloadTooLargeError):
        validate_payload_size(2_000_000, max_bytes=1_000_000)
    validate_payload_size(500, max_bytes=1_000_000)


def test_extension_whitelist():
    with pytest.raises(AppValidationError):
        validate_extension("malware.py", (".json",))
    with pytest.raises(AppValidationError):
        validate_extension("sin_extension", (".json",))
    assert validate_extension("data.json", (".json",)) == ".json"


def test_api_rejects_invalid_uuid(client):
    resp = client.get("/api/opportunities/not-a-uuid")
    assert resp.status_code == 422
    resp = client.get("/api/opportunities/" + "z" * 32)
    assert resp.status_code == 422
    resp = client.get("/api/opportunities/" + "a" * 32)  # uuid válido pero inexistente
    assert resp.status_code == 404


def test_api_rejects_invalid_decision(client):
    resp = client.post("/api/opportunities/" + "0" * 32 + "/decision", json={"decision": "hack"})
    assert resp.status_code == 422


def test_api_rejects_oversized_import(client):
    payload = {
        "opportunity": {
            "title": "Import grande",
            "problem": "Problema de importación con demasiado contenido.",
        },
        "evidences": [{"summary": "x" * 1000} for _ in range(200)],
    }
    import json as _json

    body = _json.dumps(payload)
    resp = client.post("/api/import", content=body, headers={"Content-Type": "application/json"})
    assert resp.status_code == 413
