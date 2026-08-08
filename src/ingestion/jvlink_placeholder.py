from __future__ import annotations

from pathlib import Path


class JvLinkDataSource:
    """Pointer to the Windows JV-Link importer bundled with this repository."""

    @staticmethod
    def usage_guide() -> Path:
        return Path(__file__).resolve().parents[2] / "jvlink_importer" / "README.md"
