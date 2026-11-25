import pytest

from utils.model_loader import ApiKeyManager


def test_api_key_manager_allows_unused_provider_key_to_be_absent(monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    manager = ApiKeyManager()

    assert manager.get("GOOGLE_API_KEY") == "test-google-key"
    with pytest.raises(KeyError):
        manager.get("GROQ_API_KEY")
