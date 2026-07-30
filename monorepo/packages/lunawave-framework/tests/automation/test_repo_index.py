"""
Module: tests.automation.test_repo_index

Purpose:
    Regression tests untuk automation/shared/repo_index.py — hampir semua
    tool automation/ lain (find_owner, context_pack, event_graph, hotspot,
    architecture_lint) bergantung pada index ini, jadi kalau ini salah
    semuanya ikut salah dengan percaya diri tinggi.

Responsibilities:
    - Pastikan build_index()/load_index() konsisten (cache hit tidak
      mengubah hasil vs full rebuild).
    - Pastikan load_ownership_index() ikut meng-index file di dalam
      automation/ dan tests/ (cakupan yang sengaja BEDA dari load_index()).
    - Pastikan cache ter-invalidasi saat file berubah (mtime-based).

Depends on:
    - lunawave_framework.automation.shared.repo_index

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (tiap test pakai tmp_path terisolasi, tidak menyentuh
    .cache/ repo asli).
"""

import importlib
import os
import time
from pathlib import Path

import pytest



@pytest.fixture()
def repo_index(monkeypatch, tmp_path):
    import lunawave_framework.automation.shared.repo_index as ri

    importlib.reload(ri)
    monkeypatch.setattr(ri, "CACHE_PATH", tmp_path / ".cache" / "repo_index.json")
    monkeypatch.setattr(
        ri, "OWNERSHIP_CACHE_PATH", tmp_path / ".cache" / "repo_index_ownership.json"
    )
    return ri


def _make_fake_repo(root):
    (root / "core").mkdir()
    (root / "core" / "state.py").write_text(
        "class State:\n    pass\n", encoding="utf-8"
    )
    (root / "engine").mkdir()
    (root / "engine" / "player.py").write_text(
        "from core.state import State\n\nclass Player:\n    def play(self):\n        pass\n",
        encoding="utf-8",
    )
    (root / "automation").mkdir()
    (root / "automation" / "toolx.py").write_text(
        "class ToolX:\n    pass\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "test_player.py").write_text(
        "from engine.player import Player\n", encoding="utf-8"
    )


class TestAppScopeIndex:
    def test_excludes_automation_and_tests(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        idx = repo_index.build_index(tmp_path)
        files = set(idx["files"].keys())
        assert "core/state.py" in files
        assert "engine/player.py" in files
        assert "automation/toolx.py" not in files
        assert "tests/test_player.py" not in files

    def test_reverse_deps_computed(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        idx = repo_index.build_index(tmp_path)
        assert "engine/player.py" in idx["files"]["core/state.py"]["reverse_deps"]

    def test_load_index_uses_cache_on_second_call(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        first = repo_index.build_index(tmp_path)
        assert repo_index.CACHE_PATH.exists()
        second = repo_index.load_index(tmp_path)
        assert first["files"].keys() == second["files"].keys()

    def test_cache_invalidates_on_file_change(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        repo_index.build_index(tmp_path)

        # Ubah file dan majukan mtime eksplisit (beberapa filesystem CI
        # resolusi mtime-nya kasar / sub-detik tidak reliable).
        target = tmp_path / "core" / "state.py"
        target.write_text("class State:\n    pass\n\nclass NewClass:\n    pass\n", encoding="utf-8")
        new_time = time.time() + 5
        os.utime(target, (new_time, new_time))

        updated = repo_index.load_index(tmp_path)
        assert "NewClass" in updated["files"]["core/state.py"]["classes"]


class TestOwnershipScopeIndex:
    def test_includes_automation_and_tests(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        idx = repo_index.build_ownership_index(tmp_path)
        files = set(idx["files"].keys())
        assert "automation/toolx.py" in files
        assert "tests/test_player.py" in files
        assert "core/state.py" in files

    def test_ownership_cache_is_separate_file_from_app_cache(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        repo_index.build_index(tmp_path)
        repo_index.build_ownership_index(tmp_path)
        assert repo_index.CACHE_PATH != repo_index.OWNERSHIP_CACHE_PATH
        assert repo_index.CACHE_PATH.exists()
        assert repo_index.OWNERSHIP_CACHE_PATH.exists()

    def test_ownership_index_reused_on_second_load(self, repo_index, tmp_path):
        _make_fake_repo(tmp_path)
        first = repo_index.build_ownership_index(tmp_path)
        second = repo_index.load_ownership_index(tmp_path)
        assert first["files"].keys() == second["files"].keys()
