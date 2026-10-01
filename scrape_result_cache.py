"""Caché persistente de resultados normalizados del scraper.

No reutiliza HTML ni evita verificar las fuentes: las promociones pueden cambiar
sin previo aviso. Su objetivo es evitar el trabajo posterior cuando la fuente
devolvió exactamente el mismo resultado: escrituras SQLite, commits de la base
y redeploys innecesarios.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


_SCHEMA_VERSION = 1


def _json_value(value: Any) -> Any:
    """Convierte valores de scraper a una forma JSON estable y comparable."""
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, set):
        normalized_items = [_json_value(item) for item in value]
        return sorted(normalized_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def promotions_fingerprint(promotions: list[dict]) -> str:
    """Huella independiente del orden en que una fuente entrega sus tarjetas."""
    canonical_promotions = [
        json.dumps(_json_value(promotion), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for promotion in promotions
    ]
    payload = "\n".join(sorted(canonical_promotions)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ScrapeResultCache:
    """Estado local sin PII, pensado para restaurarse entre jobs de GitHub."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._records = self._load()

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        if not isinstance(data, dict) or data.get("version") != _SCHEMA_VERSION:
            return {}
        records = data.get("records")
        if not isinstance(records, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in records.items()
            if isinstance(key, str) and isinstance(value, str) and len(value) == 64
        }

    def unchanged(self, source_key: str, promotions: list[dict]) -> bool:
        return self._records.get(source_key) == promotions_fingerprint(promotions)

    def remember(self, source_key: str, promotions: list[dict]) -> None:
        fingerprint = promotions_fingerprint(promotions)
        if self._records.get(source_key) == fingerprint:
            return
        self._records[source_key] = fingerprint
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": _SCHEMA_VERSION, "records": self._records},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ) + "\n"
        # El replace atómico evita dejar un JSON corrupto si el job se corta.
        fd, temporary_path = tempfile.mkstemp(prefix="scrape-results-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temporary_path, self.path)
        except Exception:
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            raise
