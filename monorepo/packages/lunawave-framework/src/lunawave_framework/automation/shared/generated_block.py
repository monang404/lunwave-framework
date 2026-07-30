"""
Module: automation.shared.generated_block

Purpose:
    Provide replace_marker_block() to update <!-- BEGIN/END:GENERATED -->
    sections in Markdown files.

Responsibilities:
    - Regex-replace content between paired BEGIN/END markers in a string.
    - Return the original string unchanged if markers are absent.

Depends on:
    None

Subscribes to:
    None

Publishes:
    None

Thread Safety:
    Stateless.
"""

from __future__ import annotations

import re

_DEFAULT_BEGIN = "<!-- BEGIN:GENERATED -->"
_DEFAULT_END = "<!-- END:GENERATED -->"


def replace_marker_block(
    original: str,
    block: str,
    begin: str = _DEFAULT_BEGIN,
    end: str = _DEFAULT_END,
) -> str:
    """Ganti isi di antara marker BEGIN/END:GENERATED dengan *block* baru.

    Mengasumsikan marker sudah ada di *original*. Jika belum ada, kembalikan
    *original* tidak berubah — logika fallback untuk kasus tersebut diserahkan
    ke caller masing-masing.

    Args:
        original: string isi file lengkap.
        block: konten baru yang akan disisipkan di antara marker.
        begin: string marker pembuka (default: <!-- BEGIN:GENERATED -->).
        end: string marker penutup (default: <!-- END:GENERATED -->).

    Returns:
        String dengan blok di antara marker sudah diganti.
    """
    if begin not in original:
        return original

    pattern = re.compile(
        re.escape(begin) + r".*?" + re.escape(end),
        re.DOTALL,
    )
    new_block = f"{begin}\n{block}\n{end}"
    return pattern.sub(new_block, original)
