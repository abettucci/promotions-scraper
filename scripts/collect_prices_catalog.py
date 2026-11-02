"""Recolección manual acotada. Sin notificaciones ni llamadas a modelos de IA."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prices.basket import load_basket, run_basket
from prices.history import PriceHistory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-queries", type=int, default=10, help="Máximo de búsquedas de la canasta (1 a 200)")
    parser.add_argument("--groups", type=int, default=12, help="Productos conservados por búsqueda (1 a 30)")
    args = parser.parse_args()
    if not 1 <= args.max_queries <= 200 or not 1 <= args.groups <= 30:
        parser.error("Usá entre 1 y 200 búsquedas y entre 1 y 30 grupos")
    result = run_basket(PriceHistory(), basket=load_basket()[:args.max_queries],
                        groups_per_query=args.groups, mark_complete=False)
    return 0 if result["products"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
