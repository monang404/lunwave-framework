"""
Module: tests.automation.test_patchlog

Purpose:
    Regression tests untuk automation/patchlog.py (format v2, field-based,
    lihat PATCHLOG_REDESIGN.md dan migrasi v1->v2). Tool ini pernah
    menyebabkan data-loss nyata di docs/PATCHLOG.md (format v1) dan sekarang
    jadi dependency context_pack.py/find_owner.py/hotspot.py -- kontrak
    "id" + "files" di setiap entry hasil parse_entries() WAJIB tetap stabil
    lintas perubahan format.

Responsibilities:
    - Pastikan parse_entries() tahan terhadap variasi format (manual entry
      tanpa baris kosong presisi, field multi-baris) -- bug nyata v1 yang
      menghilangkan entry diam-diam, regresi harus tetap tertutup di v2.
    - Pastikan verify() mendeteksi entry yang gagal parse DAN entry dengan
      nilai enum (Type/Priority/Breaking Change/Regression Risk/Status)
      yang tidak valid.
    - Pastikan penomoran ID berikutnya tidak tabrakan walau ada entry lama
      yang gagal parse (heading tetap dihitung meski body rusak).
    - Pastikan add_entry() menghasilkan entry yang field-order-nya konsisten
      dan tetap bisa di-parse balik oleh parse_entries().
    - Pastikan query symbol/history tetap bekerja terhadap field baru
      (Changed Symbols).

Depends on:
    - lunawave_framework.automation.patchlog

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless (tiap test independen, tidak menyentuh docs/PATCHLOG.md asli).
"""

import importlib

import pytest


@pytest.fixture()
def patchlog(monkeypatch, tmp_path):
    """Import lunawave_framework.automation.patchlog dengan PATCHLOG dialihkan ke file
    sementara, supaya test tidak pernah menyentuh docs/PATCHLOG.md asli."""
    import lunawave_framework.automation.patchlog as pl

    importlib.reload(pl)
    fake_path = tmp_path / "PATCHLOG.md"
    monkeypatch.setattr(pl, "PATCHLOG", fake_path)
    return pl


CANONICAL_TWO_ENTRIES = """---
latest_patch_id: PATCH-2026-01-01-002
total_entries: 2
---

> **Format:** entri baru wajib diawali ID unik.

---

## PATCH-2026-01-01-002

**Tanggal:** 2026-01-02
**Timestamp:** 10:00
**Git Branch:** main
**Git Commit:** abc1234
**Type:** Feature
**Area:** Backend
**Priority:** Medium
**Title:** Entry kedua

**Reason:** Kebutuhan fitur baru

**Root Cause:**
-

**Solution:**
Implementasi fitur B.

**Changed Files:**
- `b.py`

**Changed Symbols:**
- `do_b()`

**Tests:** pytest (3/3)

**Breaking Change:** No

**Regression Risk:** Low

**Related Patch:** -

**Status:** Merged

**Notes:**
Deskripsi entry kedua.

---

## PATCH-2026-01-01-001

**Tanggal:** 2026-01-01
**Timestamp:** 09:00
**Git Branch:** main
**Git Commit:** def5678
**Type:** Feature
**Area:** Backend
**Priority:** Low
**Title:** Entry pertama

**Reason:** Setup awal

**Root Cause:**
-

**Solution:**
Implementasi fitur A.

**Changed Files:**
- `a.py`

**Changed Symbols:**
- (tidak ada)

**Tests:** -

**Breaking Change:** No

**Regression Risk:** Low

**Related Patch:** -

**Status:** Merged

**Notes:**
Deskripsi entry pertama.

---
"""


# Entry manual TANPA baris kosong presisi (persis bug nyata yang ditemukan
# di PATCHLOG.md project format v1: entry hilang karena separator "---"
# tidak diikuti baris kosong, dan field multi-baris ditulis rapat). Regresi
# ini harus tetap tertutup walau format field-nya sudah berubah ke v2.
MALFORMED_MANUAL_ENTRY = """---
latest_patch_id: PATCH-2026-01-01-002
total_entries: 2
---

## PATCH-2026-01-01-002

**Tanggal:** 2026-01-02
**Timestamp:** -
**Git Branch:** -
**Git Commit:** -
**Type:** Fix
**Area:** Frontend
**Priority:** Medium
**Title:** Entry rapi

**Reason:** -

**Root Cause:**
-

**Solution:**
-

**Changed Files:**
- `b.py`

**Changed Symbols:**
- (tidak ada)

**Tests:** -

**Breaking Change:** No

**Regression Risk:** Low

**Related Patch:** -

**Status:** Merged

**Notes:**
Entry yang formatnya benar.

---
## PATCH-2026-01-01-001
**Tanggal:** 2026-01-01
**Timestamp:** -
**Git Branch:** -
**Git Commit:** -
**Type:** Unclassified
**Area:** Unclassified
**Priority:** Unclassified
**Title:** Entry ditulis manual, format berantakan
**Reason:** -
**Root Cause:**
-
**Solution:**
-
**Changed Files:**
- `a.py` — catatan tambahan setelah backtick
**Changed Symbols:**
- (tidak ada)
**Tests:** -
**Breaking Change:** Unclassified
**Regression Risk:** Unclassified
**Related Patch:** -
**Status:** Unclassified
**Notes:**
Baris pertama notes.
Baris kedua notes lanjutan.

---
"""


class TestParseEntries:
    def test_parses_canonical_format(self, patchlog):
        entries = patchlog.parse_entries(CANONICAL_TWO_ENTRIES)
        ids = [e["id"] for e in entries]
        assert ids == ["PATCH-2026-01-01-002", "PATCH-2026-01-01-001"]
        assert entries[0]["files"] == ["b.py"]
        assert entries[0]["notes"] == "Deskripsi entry kedua."
        assert entries[0]["symbols"] == ["do_b()"]
        assert entries[0]["type"] == "Feature"
        assert entries[0]["status"] == "Merged"

    def test_parses_malformed_manual_entry_without_blank_lines(self, patchlog):
        """Regresi langsung dari bug v1: entry manual tanpa baris kosong di
        sekitar '---' dan dengan field multi-baris rapat harus TETAP
        ke-parse, bukan hilang diam-diam."""
        entries = patchlog.parse_entries(MALFORMED_MANUAL_ENTRY)
        ids = {e["id"] for e in entries}
        assert "PATCH-2026-01-01-001" in ids, "entry manual yang malformed hilang dari hasil parse"
        assert "PATCH-2026-01-01-002" in ids

        malformed = next(e for e in entries if e["id"] == "PATCH-2026-01-01-001")
        assert "Baris pertama notes." in malformed["notes"]
        assert "Baris kedua notes lanjutan." in malformed["notes"]
        assert malformed["files"] == ["a.py"]

    def test_ignores_chunks_without_id(self, patchlog):
        text = "Beberapa teks pembuka tanpa ID sama sekali.\n\n---\n\n" + CANONICAL_TWO_ENTRIES
        entries = patchlog.parse_entries(text)
        assert len(entries) == 2


class TestVerify:
    def test_ok_when_all_entries_parse(self, patchlog):
        report = patchlog.verify(CANONICAL_TWO_ENTRIES)
        assert report["ok"] is True
        assert report["unparsed_ids"] == []
        assert report["invalid_enum_values"] == []
        assert report["total_ids_found"] == report["total_parsed"] == 2

    def test_detects_unparsed_entry(self, patchlog):
        # Rusak lebih jauh: hapus baris "**Changed Files:**" dari entry 001
        # supaya benar-benar tidak mungkin ke-parse, walau splitter sudah
        # ditoleransi.
        broken = MALFORMED_MANUAL_ENTRY.replace("**Changed Files:**\n- `a.py` — catatan tambahan setelah backtick", "")
        report = patchlog.verify(broken)
        assert report["ok"] is False
        assert "PATCH-2026-01-01-001" in report["unparsed_ids"]

    def test_detects_invalid_enum_value(self, patchlog):
        broken = CANONICAL_TWO_ENTRIES.replace("**Type:** Feature", "**Type:** BukanEnumValid", 1)
        report = patchlog.verify(broken)
        assert report["ok"] is False
        assert any("PATCH-2026-01-01-002" in item and "Type" in item for item in report["invalid_enum_values"])

    def test_unclassified_is_valid_enum_value(self, patchlog):
        """Entry hasil migrasi v1->v2 pakai 'Unclassified' di beberapa
        field enum -- ini harus dianggap SAH, bukan error, supaya migrasi
        tidak membuat seluruh riwayat lama gagal verify."""
        report = patchlog.verify(MALFORMED_MANUAL_ENTRY)
        unclassified_flagged = [
            item for item in report["invalid_enum_values"] if "Unclassified" in item
        ]
        assert unclassified_flagged == []


class TestAddEntryNumbering:
    def test_next_id_uses_max_existing_sequence_not_parsed_count(self, patchlog):
        """Bug nyata v1 yang tetap harus tertutup di v2: sebelumnya next ID
        dihitung dari `len(parse_entries(...)) + 1`. Kalau parser kehilangan
        entry, next ID akan TABRAKAN dengan ID yang sudah dipakai. Next ID
        harus selalu > NNN tertinggi dari SEMUA heading yang ada di file,
        terlepas dari berapa banyak yang berhasil di-parse penuh.
        """
        text = CANONICAL_TWO_ENTRIES.replace(
            "## PATCH-2026-01-01-002", "## PATCH-2026-01-01-099"
        )
        # Buat entry 099 gagal parse penuh (hapus Changed Files-nya) supaya
        # hanya 1 dari 2 ID yang berhasil di-parse -- persis kondisi bug.
        text = text.replace("**Changed Files:**\n- `b.py`", "")
        patchlog.PATCHLOG.write_text(text, encoding="utf-8")

        entries = patchlog.parse_entries(text)
        assert len(entries) == 1, "sanity check: entry 099 memang gagal parse penuh"

        next_id = patchlog._next_id()
        # len(entries) + 1 == 2 -> akan jadi -002 yang TABRAKAN dengan ID
        # yang sudah ada (099). Next ID yang benar harus > 099.
        seq = int(next_id.rsplit("-", 1)[1])
        assert seq == 100, f"expected seq 100 (max existing heading + 1), got {seq}"

    def test_add_entry_produces_canonical_parseable_format(self, patchlog):
        patchlog.PATCHLOG.write_text(CANONICAL_TWO_ENTRIES, encoding="utf-8")
        new_id = patchlog.add_entry(
            type_="Fix",
            area="Backend",
            title="Test entry baru",
            reason="Regression test",
            files=["c.py", "d.py"],
            priority="High",
            symbols=["do_c()"],
            tests="pytest",
            breaking="No",
            risk="Low",
            status="Merged",
            related="-",
            root_cause="Contoh root cause.",
            solution="Contoh solution.",
            notes="Contoh notes.",
        )

        text = patchlog.PATCHLOG.read_text(encoding="utf-8")
        entries = patchlog.parse_entries(text)
        ids = [e["id"] for e in entries]
        assert new_id in ids
        newest = next(e for e in entries if e["id"] == new_id)
        assert newest["files"] == ["c.py", "d.py"]
        assert newest["symbols"] == ["do_c()"]
        assert newest["type"] == "Fix"
        assert newest["priority"] == "High"
        assert newest["status"] == "Merged"

        # add_entry harus tidak merusak frontmatter YAML pembuka.
        assert text.startswith("---\nlatest_patch_id:")

        # Entry baru harus selalu tampil PALING ATAS (prepend-only).
        assert ids[0] == new_id

        # Hasil harus tetap lolos verify() sendiri (dogfooding).
        report = patchlog.verify(text)
        assert report["ok"] is True

    def test_add_entry_does_not_insert_inside_frontmatter(self, patchlog):
        patchlog.PATCHLOG.write_text(CANONICAL_TWO_ENTRIES, encoding="utf-8")
        patchlog.add_entry(
            type_="Docs",
            area="Docs",
            title="Entry lain",
            reason="-",
            files=["e.py"],
        )
        text = patchlog.PATCHLOG.read_text(encoding="utf-8")
        # frontmatter tetap 3 baris (buka --- / 2 field / tutup ---) diikuti
        # blockquote format-notice sebelum entry pertama muncul.
        fm_end = text.index("\n---", 3)
        frontmatter = text[: fm_end + 4]
        assert "## PATCH-" not in frontmatter

    def test_add_entry_defaults_when_optional_fields_omitted(self, patchlog):
        """Field manual yang tidak diberikan (Root Cause/Solution/Notes/
        Symbols/dll.) harus tetap menghasilkan entry yang valid & terparse,
        bukan error -- CLI mengisi default "-" / list kosong."""
        patchlog.PATCHLOG.write_text(CANONICAL_TWO_ENTRIES, encoding="utf-8")
        new_id = patchlog.add_entry(
            type_="Cleanup",
            area="Tooling",
            title="Minimal entry",
            reason="-",
            files=["f.py"],
        )
        entries = patchlog.parse_entries(patchlog.PATCHLOG.read_text(encoding="utf-8"))
        newest = next(e for e in entries if e["id"] == new_id)
        assert newest["symbols"] == []
        assert newest["priority"] == "Medium"  # default


class TestQueries:
    def test_symbol_query_matches_changed_symbols_field_only(self, patchlog):
        entries = patchlog.parse_entries(CANONICAL_TWO_ENTRIES)
        matches = [e for e in entries if "do_b()" in e["symbols"]]
        assert len(matches) == 1
        assert matches[0]["id"] == "PATCH-2026-01-01-002"

    def test_history_query_matches_changed_files(self, patchlog):
        entries = patchlog.parse_entries(CANONICAL_TWO_ENTRIES)
        matches = [e for e in entries if "a.py" in e["files"]]
        assert len(matches) == 1
        assert matches[0]["id"] == "PATCH-2026-01-01-001"


class TestSuggestArea:
    def test_suggests_frontend_for_web_static_js(self, patchlog):
        assert patchlog.suggest_area(["web/static/js/store.js"]) == "Frontend"

    def test_suggests_backend_for_server(self, patchlog):
        assert patchlog.suggest_area(["server/handlers/websocket.py"]) == "Backend"

    def test_returns_none_for_unknown_prefix(self, patchlog):
        assert patchlog.suggest_area(["some/unknown/path.txt"]) is None
