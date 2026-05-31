from __future__ import annotations


class JvLinkDataSource:
    """Future adapter for JRA-VAN JV-Link ingestion."""

    def fetch(self) -> None:
        raise NotImplementedError("JV-Link ingestion will be implemented in a future phase.")
