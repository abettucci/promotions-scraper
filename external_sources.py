"""Ejecución aislada y durable de fuentes externas en Railway."""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import tempfile
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import config
from database import Database
from scrapers.santander_scraper import SantanderScraper
from scrapers.visa_scraper import VisaScraper

_SOURCES = {"santander": SantanderScraper, "visa": VisaScraper}
_THREAD_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path, fallback: Dict) -> Dict:
    try:
        with path.open(encoding="utf-8") as source:
            value = json.load(source)
        return value if isinstance(value, dict) else fallback
    except (OSError, json.JSONDecodeError):
        return fallback


def _atomic_json_write(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ExternalSourcesRunner:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()
        self.snapshot_path = config.EXTERNAL_SOURCES_SNAPSHOT_PATH
        self.status_path = config.EXTERNAL_SOURCES_STATUS_PATH
        self.lock_path = config.EXTERNAL_SOURCES_LOCK_PATH

    def status(self) -> Dict:
        return _read_json(self.status_path, {"running": False, "sources": {}})

    def hydrate(self) -> Dict:
        """Restaura al DB efímero el último snapshot exitoso del Volume."""
        snapshot, hydrated = _read_json(self.snapshot_path, {"sources": {}}), {}
        for source, entry in (snapshot.get("sources") or {}).items():
            promotions = entry.get("promotions") if isinstance(entry, dict) else None
            if source in _SOURCES and isinstance(promotions, list) and promotions:
                hydrated[source] = self._publish(source, promotions)
        return hydrated

    def run(self, sources: Optional[Iterable[str]] = None) -> Dict:
        requested = list(sources or _SOURCES.keys())
        invalid = sorted(set(requested) - set(_SOURCES))
        if invalid:
            raise ValueError(f"Fuentes no permitidas: {', '.join(invalid)}")
        if not _THREAD_LOCK.acquire(blocking=False):
            return {"status": "already_running"}
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.lock_path.open("a+") as lock_file:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {"status": "already_running"}
                try:
                    return self._run_locked(requested)
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            _THREAD_LOCK.release()

    def _run_locked(self, requested: List[str]) -> Dict:
        old_status = self.status()
        _atomic_json_write(self.status_path, {**old_status, "running": True, "started_at": _now()})
        snapshot = _read_json(self.snapshot_path, {"version": 1, "sources": {}})
        results = {}
        for source in requested:
            try:
                promotions = self._current_promotions(asyncio.run(_SOURCES[source]().scrape()))
                if not promotions:
                    raise RuntimeError("la fuente no devolvió promociones publicables")
                inserted = self._publish(source, promotions)
                if not inserted:
                    raise RuntimeError("no se pudo persistir ninguna promoción")
                snapshot.setdefault("sources", {})[source] = {"updated_at": _now(), "promotions": promotions}
                results[source] = {"status": "success", "promotions": inserted, "updated_at": _now()}
            except Exception as exc:
                results[source] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "updated_at": _now()}
        if any(result["status"] == "success" for result in results.values()):
            _atomic_json_write(self.snapshot_path, snapshot)
        status = {**old_status, "running": False, "finished_at": _now(), "sources": {**old_status.get("sources", {}), **results}}
        _atomic_json_write(self.status_path, status)
        return {"status": "completed", "sources": results}

    @staticmethod
    def _current_promotions(promotions: List[Dict]) -> List[Dict]:
        """No guarda como nuevo snapshot una campaña que ya venció."""
        today = date.today().isoformat()
        current, seen = [], set()
        for promo in promotions:
            if promo.get("valid_until") and promo["valid_until"] < today:
                continue
            # Santander puede publicar variantes idénticas para una misma
            # marca. La DB las unifica; hacerlo antes vuelve honestos los
            # conteos del status y reduce escrituras.
            key = (tuple(promo.get("merchant_brands") or ()), promo.get("title"), promo.get("bank") or "")
            if key not in seen:
                current.append(promo)
                seen.add(key)
        return current

    def _publish(self, source: str, promotions: List[Dict]) -> int:
        """Reemplaza sólo filas de ``source``; nunca toca otros scrapers."""
        grouped: Dict[tuple, List[Dict]] = {}
        for promo in promotions:
            for merchant in promo.get("merchant_brands") or []:
                grouped.setdefault((merchant, promo.get("merchant_category") or "supermarket"), []).append(promo)
        inserted = 0
        for (merchant, category), items in grouped.items():
            supermarket_id = self.db.insert_supermarket(merchant, items[0].get("url") or "", category, update_existing=False)
            self.db.deactivate_for_source(supermarket_id, source)
            for promo in items:
                promotion_id = self.db.insert_promotion(supermarket_id, {**promo, "source": source})
                if not promotion_id:
                    continue
                self.db.insert_terms(promotion_id, {
                    "raw_text": promo.get("terms_raw", ""), "exclusions": promo.get("exclusions", []),
                    "requirements": promo.get("requirements", []), "max_discount": promo.get("tope", ""),
                    "min_purchase": promo.get("min_purchase", ""), "valid_days": [promo.get("valid_days", "")],
                    "payment_methods": [promo.get("payment_method", "")],
                })
                inserted += 1
            self.db.update_supermarket_scraped(supermarket_id)
            self.db.insert_scrape_history(supermarket_id, "success", len(items), f"External source: {source}")
        return inserted
