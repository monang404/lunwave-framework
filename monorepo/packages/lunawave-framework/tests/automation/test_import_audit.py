import textwrap

from lunawave_framework.automation.import_audit import run_audit


def test_import_audit_heuristics(tmp_path):
    # Setup dummy project in tmp_path
    (tmp_path / "server" / "handlers").mkdir(parents=True)

    # 1. Circular case: A imports B (top-level), B imports A (deferred)
    with open(tmp_path / "server" / "handlers" / "a.py", "w") as f:
        f.write(
            textwrap.dedent("""
            from server.handlers.b import something_b

            def do_a():
                pass
        """)
        )

    with open(tmp_path / "server" / "handlers" / "b.py", "w") as f:
        f.write(
            textwrap.dedent("""
            def do_b():
                from server.handlers.a import do_a
                do_a()
        """)
        )

    # 2. Safe to promote: C imports D (deferred), D doesn't import C
    with open(tmp_path / "server" / "handlers" / "c.py", "w") as f:
        f.write(
            textwrap.dedent("""
            def do_c():
                from server.handlers.d import something_d
                something_d()
        """)
        )

    with open(tmp_path / "server" / "handlers" / "d.py", "w") as f:
        f.write(
            textwrap.dedent("""
            def something_d():
                pass
        """)
        )

    # 3. Patchability: E imports F (deferred) with comment 'mock'
    with open(tmp_path / "server" / "handlers" / "e.py", "w") as f:
        f.write(
            textwrap.dedent("""
            def do_e():
                # For mock / patch in tests
                from server.handlers.f import something_f
                something_f()
        """)
        )

    with open(tmp_path / "server" / "handlers" / "f.py", "w") as f:
        f.write(
            textwrap.dedent("""
            def something_f():
                pass
        """)
        )

    results = run_audit(str(tmp_path))

    # Assertions
    b_result = [r for r in results if r["file"].endswith("b.py")][0]
    assert "CIRCULAR" in b_result["labels"]

    c_result = [r for r in results if r["file"].endswith("c.py")][0]
    assert "SAFE_TO_PROMOTE" in c_result["labels"]
    assert "PATCHABILITY" not in c_result["labels"]

    e_result = [r for r in results if r["file"].endswith("e.py")][0]
    assert "SAFE_TO_PROMOTE" in e_result["labels"]
    assert "PATCHABILITY" in e_result["labels"]
