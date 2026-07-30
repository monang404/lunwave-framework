"""
Module: tests.automation.test_find_owner_and_context_pack

Purpose:
    Regression tests untuk automation/find_owner.py dan
    automation/context_pack.py, memakai fake repo kecil di tmp_path supaya
    tidak bergantung pada isi repo LunaWave asli (yang bisa berubah).

Responsibilities:
    - Pastikan resolve_target() bekerja untuk path file, nama class, dan
      nama fungsi.
    - Pastikan context_pack.py TIDAK lagi diam-diam mengembalikan
      deps/reverse_deps/event_flow kosong saat target berupa nama class
      (bug PATCH-2026-07-17-075).
    - Pastikan find_owner.py bisa menemukan file di dalam automation/ dan
      tests/ (regresi dari bug SKIP_DIRS_FOR_OWNERSHIP sebelumnya).

Depends on:
    - lunawave_framework.automation.find_owner
    - lunawave_framework.automation.context_pack
    - lunawave_framework.automation.shared.repo_index

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (fake repo terisolasi per test via tmp_path).
"""

import importlib
from pathlib import Path

import pytest



def _make_fake_repo(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "docs" / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    (root / "docs" / "PATCHLOG.md").write_text(
        "---\nlatest_patch_id: PATCH-2026-01-01-001\ntotal_entries: 1\n---\n\n"
        "## PATCH-2026-01-01-001\n\n"
        "**Tanggal:** 2026-01-01\n**Timestamp:** -\n**Git Branch:** -\n**Git Commit:** -\n"
        "**Type:** Feature\n**Area:** Backend\n**Priority:** Medium\n"
        "**Title:** Buat DownloadManager\n\n"
        "**Reason:** -\n\n**Root Cause:**\n-\n\n**Solution:**\n-\n\n"
        "**Changed Files:**\n- `engine/download_manager.py`\n\n"
        "**Changed Symbols:**\n- (tidak ada)\n\n"
        "**Tests:** -\n\n**Breaking Change:** No\n\n**Regression Risk:** Low\n\n"
        "**Related Patch:** -\n\n**Status:** Merged\n\n"
        "**Notes:**\nBuat DownloadManager.\n\n---\n",
        encoding="utf-8",
    )
    (root / "engine").mkdir()
    (root / "engine" / "download_manager.py").write_text(
        "class DownloadManager:\n"
        "    def start(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    (root / "main.py").write_text(
        "from engine.download_manager import DownloadManager\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "unit").mkdir()
    (root / "tests" / "unit" / "engine").mkdir()
    (root / "tests" / "unit" / "engine" / "test_download_manager.py").write_text(
        "from engine.download_manager import DownloadManager\n", encoding="utf-8"
    )
    (root / "automation").mkdir()
    (root / "automation" / "own_tool.py").write_text(
        "class OwnTool:\n    pass\n", encoding="utf-8"
    )


@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    import lunawave_framework.automation.shared.repo_index as ri

    importlib.reload(ri)
    monkeypatch.setattr(ri, "CACHE_PATH", tmp_path / ".cache" / "repo_index.json")
    monkeypatch.setattr(
        ri, "OWNERSHIP_CACHE_PATH", tmp_path / ".cache" / "repo_index_ownership.json"
    )
    _make_fake_repo(tmp_path)
    return tmp_path


class TestFindOwnerResolution:
    def test_resolves_by_file_path(self, fake_repo):
        import lunawave_framework.automation.find_owner as fo

        info = fo.get_owner_info("engine/download_manager.py", fake_repo)
        assert info is not None
        assert info["resolved_path"] == "engine/download_manager.py"
        assert "DownloadManager" in info["classes"]

    def test_resolves_by_class_name(self, fake_repo):
        import lunawave_framework.automation.find_owner as fo

        info = fo.get_owner_info("DownloadManager", fake_repo)
        assert info is not None
        assert info["resolved_path"] == "engine/download_manager.py"

    def test_finds_file_inside_automation_dir(self, fake_repo):
        """Regresi: find_owner.py sebelumnya sempat tidak bisa menemukan
        file miliknya sendiri di dalam automation/ karena SKIP_DIRS_FOR_OWNERSHIP
        salah mengecualikan folder itu."""
        import lunawave_framework.automation.find_owner as fo

        info = fo.get_owner_info("automation/own_tool.py", fake_repo)
        assert info is not None
        assert "OwnTool" in info["classes"]

    def test_unknown_target_returns_none(self, fake_repo):
        import lunawave_framework.automation.find_owner as fo

        assert fo.get_owner_info("TidakAda", fake_repo) is None


class TestContextPackResolution:
    def test_class_name_query_returns_same_deps_as_file_path_query(self, fake_repo):
        """Bug PATCH-2026-07-17-075: context_pack.py dulu langsung
        `index["files"].get(target, {})` -- kalau target adalah nama class,
        deps/reverse_deps/event_flow diam-diam kosong. Sekarang harus
        identik hasilnya dengan query via path file."""
        import lunawave_framework.automation.context_pack as cp

        by_path = cp.build_context_pack(fake_repo, "engine/download_manager.py")
        by_class = cp.build_context_pack(fake_repo, "DownloadManager")

        assert by_class["reverse_deps"] == by_path["reverse_deps"]
        assert by_class["deps"] == by_path["deps"]
        assert by_class["reverse_deps"], "sanity check: seharusnya ada reverse dep (main.py)"

    def test_finds_related_test_and_patchlog_history(self, fake_repo):
        import lunawave_framework.automation.context_pack as cp

        result = cp.build_context_pack(fake_repo, "engine/download_manager.py")
        assert result["related_test"] == "tests/unit/engine/test_download_manager.py"
        assert len(result["patchlog_history"]) == 1
        assert result["patchlog_history"][0]["id"] == "PATCH-2026-01-01-001"
