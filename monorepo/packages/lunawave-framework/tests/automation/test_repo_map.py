"""
Module: tests.automation.test_repo_map

Purpose:
    Regression tests untuk automation/repo_map.py (tool baru sesi ini) --
    pastikan graph yang dihasilkan konsisten dengan index ownership yang
    mendasarinya (nodes, edges, event map).

Depends on:
    - lunawave_framework.automation.repo_map
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



@pytest.fixture()
def fake_repo(tmp_path, monkeypatch):
    import lunawave_framework.automation.shared.repo_index as ri

    importlib.reload(ri)
    monkeypatch.setattr(ri, "CACHE_PATH", tmp_path / ".cache" / "repo_index.json")
    monkeypatch.setattr(
        ri, "OWNERSHIP_CACHE_PATH", tmp_path / ".cache" / "repo_index_ownership.json"
    )

    (tmp_path / "core").mkdir()
    (tmp_path / "core" / "bus.py").write_text(
        "class EventBus:\n    def publish(self, ev):\n        pass\n"
        "    def subscribe(self, ev, handler):\n        pass\n",
        encoding="utf-8",
    )
    (tmp_path / "engine").mkdir()
    (tmp_path / "engine" / "player.py").write_text(
        "from core.bus import EventBus\n\n"
        "class DownloadCompleteEvent:\n    pass\n\n"
        "class Player:\n"
        "    def finish(self, bus):\n"
        "        bus.publish(DownloadCompleteEvent())\n",
        encoding="utf-8",
    )
    (tmp_path / "server").mkdir()
    (tmp_path / "server" / "handler.py").write_text(
        "from core.bus import EventBus\n"
        "from engine.player import DownloadCompleteEvent\n\n"
        "class Handler:\n"
        "    def setup(self, bus):\n"
        "        bus.subscribe(DownloadCompleteEvent, self.on_done)\n"
        "    def on_done(self):\n"
        "        pass\n",
        encoding="utf-8",
    )
    return tmp_path


class TestRepoMap:
    def test_graph_includes_all_files(self, fake_repo):
        import lunawave_framework.automation.repo_map as rm

        graph = rm.build_graph(fake_repo)
        nodes = set(graph["nodes"].keys())
        assert nodes == {"core/bus.py", "engine/player.py", "server/handler.py"}
        assert graph["summary"]["total_files"] == 3

    def test_edges_reflect_internal_imports_only(self, fake_repo):
        import lunawave_framework.automation.repo_map as rm

        graph = rm.build_graph(fake_repo)
        edges = {(e["from"], e["to"]) for e in graph["edges"]}
        assert ("engine/player.py", "core/bus.py") in edges
        assert ("server/handler.py", "core/bus.py") in edges
        assert ("server/handler.py", "engine/player.py") in edges

    def test_event_map_links_publisher_and_subscriber(self, fake_repo):
        import lunawave_framework.automation.repo_map as rm

        graph = rm.build_graph(fake_repo)
        ev = graph["events"]["DownloadCompleteEvent"]
        assert ev["publishers"] == ["engine/player.py"]
        assert ev["subscribers"] == ["server/handler.py"]

    def test_orphan_candidates_exclude_files_with_reverse_deps(self, fake_repo):
        import lunawave_framework.automation.repo_map as rm

        graph = rm.build_graph(fake_repo)
        # core/bus.py dipakai 2 file lain -> bukan orphan.
        assert "core/bus.py" not in graph["orphan_candidates"]
        # server/handler.py tidak diimpor siapapun -> kandidat orphan.
        assert "server/handler.py" in graph["orphan_candidates"]
