"""Entity names and states must fit the companion app (max. 18 characters)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

MAX_LEN = 18
BASE = Path(__file__).parents[2] / "custom_components" / "minjet"
FILES = ["strings.json", "translations/en.json", "translations/de.json"]


def _labels(data: dict) -> list[tuple[str, str]]:
    labels = []
    for platform, entities in data["entity"].items():
        for key, entity in entities.items():
            labels.append((f"{platform}.{key}", entity["name"]))
            for state_key, state in (entity.get("state") or {}).items():
                labels.append((f"{platform}.{key}.{state_key}", state))
            event_states = (
                (entity.get("state_attributes") or {})
                .get("event_type", {})
                .get("state")
            )
            for state_key, state in (event_states or {}).items():
                labels.append((f"{platform}.{key}.event.{state_key}", state))
    return labels


@pytest.mark.parametrize("file", FILES)
def test_labels_are_short(file: str) -> None:
    """Every entity name and state label has at most 18 characters."""
    data = json.loads((BASE / file).read_text(encoding="utf-8"))
    too_long = [(k, v, len(v)) for k, v in _labels(data) if len(v) > MAX_LEN]
    assert not too_long


def test_translations_have_same_keys() -> None:
    """German and English cover the same entities and states."""
    en, de = (
        {k for k, _ in _labels(json.loads((BASE / f).read_text(encoding="utf-8")))}
        for f in ("translations/en.json", "translations/de.json")
    )
    assert en == de
