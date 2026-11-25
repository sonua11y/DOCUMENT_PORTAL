# tests/test_unit_cases.py

import pytest
from fastapi.testclient import TestClient
from api.main import _root_cause_message, app
from exception.custom_exception import DocumentPortalException

client = TestClient(app)

def test_home():
    response = client.get("/")
    assert response.status_code == 200
    assert "Document Portal" in response.text


def test_root_cause_message_hides_wrapper_traceback():
    try:
        try:
            raise ValueError("Embedding model was not found")
        except ValueError as cause:
            raise DocumentPortalException("Indexing failed", cause) from cause
    except DocumentPortalException as error:
        assert _root_cause_message(error) == "Embedding model was not found"
