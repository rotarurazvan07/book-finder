import pytest
import os
import yaml
from pathlib import Path
from book_framework.SettingsManager import SettingsManager

def test_settings_manager_load(tmp_path):
    # Setup tmp config
    (tmp_path / "config.yaml").write_text("key: value")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "sub.yaml").write_text("sub_key: sub_value")

    manager = SettingsManager(str(tmp_path))

    assert manager.get("config", "key") == "value"
    assert manager.get("nested", "sub", "sub_key") == "sub_value"
    # Test flat get (should search)
    assert manager.get("sub_key") == "sub_value"

def test_settings_manager_write_atomic(tmp_path):
    manager = SettingsManager(str(tmp_path))
    data = {"test": "data"}

    success = manager.write(str(tmp_path), "new_cfg", data)
    assert success is True

    cfg_file = tmp_path / "new_cfg.yaml"
    assert cfg_file.exists()

    with open(cfg_file, 'r') as f:
        loaded = yaml.safe_load(f)
    assert loaded == data

def test_settings_manager_delete(tmp_path):
    (tmp_path / "to_delete.yaml").write_text("foo: bar")
    manager = SettingsManager(str(tmp_path))

    success = manager.delete(str(tmp_path), "to_delete")
    assert success is True
    assert not (tmp_path / "to_delete.yaml").exists()
