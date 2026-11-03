"""Validación de códigos GTIN/EAN antes de consultar catálogos."""

def valid_gtin(value: str) -> bool:
    if len(value) not in (8, 12, 13, 14) or not value.isdigit() or set(value) == {"0"}:
        return False
    total = sum(int(digit) * (3 if index % 2 == 0 else 1)
                for index, digit in enumerate(reversed(value[:-1])))
    return (10 - total % 10) % 10 == int(value[-1])
