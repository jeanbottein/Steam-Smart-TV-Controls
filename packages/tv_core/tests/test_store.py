from tv_core.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "store.json"))


def test_selected_defaults_to_empty(tmp_path):
    assert _store(tmp_path).selected == ""


def test_set_selected_persists_across_instances(tmp_path):
    path = tmp_path / "store.json"
    Store(str(path)).set_selected("10.0.0.5")
    assert Store(str(path)).selected == "10.0.0.5"


def test_removing_selected_tv_clears_selection(tmp_path):
    store = _store(tmp_path)
    store.upsert_tv("10.0.0.5", "Living room", "lg", "key")
    store.set_selected("10.0.0.5")
    store.remove_tv("10.0.0.5")
    assert store.selected == ""


def test_removing_other_tv_keeps_selection(tmp_path):
    store = _store(tmp_path)
    store.upsert_tv("10.0.0.5", "Living room", "lg", "key")
    store.upsert_tv("10.0.0.6", "Bedroom", "lg", "key")
    store.set_selected("10.0.0.5")
    store.remove_tv("10.0.0.6")
    assert store.selected == "10.0.0.5"
