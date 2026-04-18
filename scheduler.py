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
