"""Model registry — loads config/models.yaml and resolves alias → config."""

from __future__ import annotations

import pathlib
import yaml

_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "models.yaml"

_registry: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _registry
    if _registry is None:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        _registry = data["models"]
    return _registry


def get_model_config(alias: str) -> dict:
    registry = _load()
    if alias not in registry:
        available = ", ".join(sorted(registry))
        raise KeyError(f"Model alias '{alias}' not found. Available: {available}")
    return dict(registry[alias])


def list_models() -> list[str]:
    return list(_load().keys())


def is_reasoning_model(alias: str) -> bool:
    config = get_model_config(alias)
    return bool(config.get("is_reasoning", False))
