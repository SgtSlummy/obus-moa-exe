import pytest
from backend.main import load_state, save_state

@pytest.fixture
def client():
    # Reset state before each test
    load_state().clear()
    save_state({})
    from httpx import AsyncClient
    from backend.main import app
    return AsyncClient(app=app, base_url="http://test")
