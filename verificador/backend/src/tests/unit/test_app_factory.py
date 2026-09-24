"""A fábrica monta a API sem incluir regra de negócio."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI

from src.core.config import settings as settings_module
from src.core.config.settings import Settings

MAIN_FILE = Path(__file__).resolve().parents[2] / "main.py"


def load_app_module():
    spec = importlib.util.spec_from_file_location("factory_under_test", MAIN_FILE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_criar_app_monta_gateway_com_rotas_da_feat_10(monkeypatch) -> None:
    custom = Settings(
        _env_file=None, database_url="postgresql+asyncpg://db/teste", app_debug=True
    )
    mocked_settings = Mock(return_value=custom)
    monkeypatch.setattr(settings_module, "get_settings", mocked_settings)

    module = load_app_module()
    assert isinstance(module.app, FastAPI)
    assert module.app.title == "Verificador Científico"
    assert module.app.version == "0.1.0"
    assert module.app.debug is True
    assert "/health" in {route.path for route in module.app.routes}
    assert "/saude" not in {route.path for route in module.app.routes}
    assert "/verificar" in {route.path for route in module.app.routes}

    another = module.criar_app()
    assert isinstance(another, FastAPI)
    assert another is not module.app
    assert mocked_settings.call_count == 2
