"""
Background scheduler — runs the scraper periodically inside the Railway container.
Starts as a daemon thread from api.py so the API stays responsive.
"""
import subprocess
import threading
import time
import os

SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "24"))
SCRAPE_DELAY_SECONDS = int(os.getenv("SCRAPE_DELAY_SECONDS", "60"))


def _run_scraper():
    print(f"[scheduler] Arrancando scraper...")
    try:
        result = subprocess.run(
            ["python", "scraper.py", "--notify"],
            capture_output=True,
            text=True,
            timeout=2400,  # 40 min max
        )
        print(f"[scheduler] Scraper terminó (exit code {result.returncode})")
        if result.stdout:
            # últimas líneas del output
            lines = result.stdout.strip().split("\n")
            for line in lines[-20:]:
                print(f"  {line}")
        if result.returncode != 0 and result.stderr:
            for line in result.stderr.strip().split("\n")[-10:]:
                print(f"  [err] {line}")
    except subprocess.TimeoutExpired:
        print("[scheduler] Scraper cortado por timeout (40 min)")
    except Exception as e:
        print(f"[scheduler] Error corriendo scraper: {e}")


def start():
    """Inicia el thread de scheduling en background."""
    def loop():
        # Esperar a que la API arranque antes del primer scrape
        time.sleep(SCRAPE_DELAY_SECONDS)
        while True:
            _run_scraper()
            print(f"[scheduler] Próximo scrape en {SCRAPE_INTERVAL_HOURS}h")
            time.sleep(SCRAPE_INTERVAL_HOURS * 3600)

    t = threading.Thread(target=loop, daemon=True, name="scraper-scheduler")
    t.start()
    print(f"[scheduler] Scraper programado cada {SCRAPE_INTERVAL_HOURS}h (primer run en {SCRAPE_DELAY_SECONDS}s)")


# ── Canasta diaria de precios + alertas ──────────────────────────────────────
# Opt-in (ENABLE_PRICES_JOB): consulta ~90 productos en ~13 tiendas por día.
PRICES_TICK_SECONDS = int(os.getenv("PRICES_TICK_SECONDS", "1800"))
PRICES_BASKET_EVERY_HOURS = float(os.getenv("PRICES_BASKET_EVERY_HOURS", "20"))
PRICE_ALERTS_EVERY_HOURS = float(os.getenv("PRICE_ALERTS_EVERY_HOURS", "6"))


def _prices_tick(history, user_db, notifier):
    """Una pasada: corre la canasta y/o revisa alertas si les toca."""
    from datetime import datetime, timedelta
    from prices.alerts import check_alerts
    from prices.basket import due, run_basket

    if due(history, PRICES_BASKET_EVERY_HOURS):
        print("[prices] Corriendo canasta diaria...")
        run_basket(history, log=lambda line: print(f"[prices]{line}"))
    last = history.get_meta("alerts_last_check")
    if not last or datetime.now() - datetime.fromisoformat(last) >= timedelta(hours=PRICE_ALERTS_EVERY_HOURS):
        stats = check_alerts(user_db, lambda chat_id, text: notifier.send_message_to(chat_id, text, parse_mode="HTML"))
        history.set_meta("alerts_last_check", datetime.now().isoformat(timespec="seconds"))
        print(f"[prices] Alertas: {stats}")


def start_prices():
    """Hilo en background para la canasta de precios y las alertas."""
    from database import UserDatabase
    from notifier import TelegramNotifier
    from prices.history import PriceHistory

    def loop():
        time.sleep(120)  # que la API termine de arrancar
        history, user_db, notifier = PriceHistory(), UserDatabase(), TelegramNotifier()
        while True:
            try:
                _prices_tick(history, user_db, notifier)
            except Exception as error:  # el hilo no puede morir por una pasada fallida
                print(f"[prices] Error: {type(error).__name__}: {error}")
            time.sleep(PRICES_TICK_SECONDS)

    threading.Thread(target=loop, daemon=True, name="prices-scheduler").start()
    print(f"[prices] Canasta cada {PRICES_BASKET_EVERY_HOURS}h y alertas cada {PRICE_ALERTS_EVERY_HOURS}h")
