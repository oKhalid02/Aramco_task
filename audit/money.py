"""Integer-cent arithmetic. No floats anywhere: percentages and multipliers are Fractions."""

from fractions import Fraction


def to_fraction(value: str) -> Fraction:
    """'1.05' -> Fraction(21, 20). Accepts ints and decimal strings only."""
    return Fraction(str(value))


def round_half_up(amount: Fraction) -> int:
    """Nearest whole cent, exact halves away from zero (contract §3.1 in every agreement)."""
    sign = -1 if amount < 0 else 1
    a = abs(amount)
    return sign * ((a.numerator * 2 + a.denominator) // (2 * a.denominator))


def apply_multiplier(cents: int, multiplier: Fraction) -> int:
    return round_half_up(Fraction(cents) * multiplier)


def apply_uplift(cents: int, pct: str) -> int:
    return apply_multiplier(cents, 1 + to_fraction(pct) / 100)


def apply_discount(cents: int, pct: str) -> int:
    return apply_multiplier(cents, 1 - to_fraction(pct) / 100)


def gbp_to_cents(text: str) -> int:
    """'GBP 1,301.25' or '1,301.25' -> 130125."""
    digits = text.replace("GBP", "").replace(",", "").strip()
    pounds, pence = digits.split(".")
    assert len(pence) == 2, text
    return int(pounds) * 100 + int(pence)
