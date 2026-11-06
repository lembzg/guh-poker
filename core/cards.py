"""Card helpers. A card is a 2-char string: rank + suit, e.g. "As", "Td"."""
from __future__ import annotations

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def full_deck() -> list[str]:
    """All 52 cards, in a fixed order."""
    return [rank + suit for rank in RANKS for suit in SUITS]


def hand_class(hole: tuple[str, str]) -> str:
    """Starting-hand class, high rank first: "AKs", "T9o", "77"."""
    first, second = hole
    high, low = sorted((first[0], second[0]), key=RANKS.index, reverse=True)
    if high == low:
        return high + low
    return high + low + ("s" if first[1] == second[1] else "o")
