import pytest

from tv_core.driver import build_registry, list_brands, select_driver


class _StubDriver:
    def __init__(self, name, label):
        self.name = name
        self.label = label


def test_build_registry_keys_drivers_by_name():
    driver = _StubDriver("lg", "LG (webOS)")
    assert build_registry([driver]) == {"lg": driver}


def test_list_brands_exposes_id_and_label():
    registry = build_registry([_StubDriver("lg", "LG (webOS)")])
    assert list_brands(registry) == [{"id": "lg", "label": "LG (webOS)"}]


def test_select_driver_returns_registered_driver():
    driver = _StubDriver("lg", "LG (webOS)")
    assert select_driver(build_registry([driver]), "lg") is driver


def test_select_driver_rejects_unknown_brand():
    with pytest.raises(ValueError):
        select_driver({}, "samsung")
