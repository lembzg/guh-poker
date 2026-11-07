"""Postflop placeholder: check when free, otherwise call or fold on pot odds.

This is a hook, not a strategy. It never bets or raises. Replace
``postflop_action`` to plug in real postflop play; bot.py only depends on that
signature.
"""

from __future__ import annotations

from collections import Counter

from player_sdk.models import Response

RANKS = "23456789TJQKA"


def _rank(card: str) -> int:
    return RANKS.index(card[0]) + 2


def rough_equity(hole, board) -> float:
    """A crude equity guess from the made hand and draws. Not a solver."""
    hole_ranks = [_rank(card) for card in hole]
    board_ranks = [_rank(card) for card in board]
    counts = Counter(hole_ranks + board_ranks)
    board_counts = Counter(board_ranks)
    suits = Counter(card[1] for card in list(hole) + list(board))
    hole_suits = {card[1] for card in hole}

    best = max(counts.values())
    pairs = [rank for rank, n in counts.items() if n >= 2]
    flush = any(n >= 5 and s in hole_suits for s, n in suits.items())
    flush_draw = len(board) < 5 and any(
        n == 4 and s in hole_suits for s, n in suits.items()
    )
    wheel_ace = [1] if 14 in counts else []
    values = sorted(set(hole_ranks + board_ranks + wheel_ace))
    run = longest = 1
    for previous, current in zip(values, values[1:]):
        run = run + 1 if current == previous + 1 else 1
        longest = max(longest, run)

    if best >= 3 and any(n >= 2 for r, n in counts.items() if n < 3):
        return 0.92
    if best == 4 or flush or longest >= 5:
        return 0.88
    if best == 3 and max(board_counts.values()) < 3:
        return 0.82
    own_pairs = [rank for rank in pairs if rank in hole_ranks]
    if len(own_pairs) >= 2:
        return 0.75
    if own_pairs:
        rank = own_pairs[0]
        top = max(board_ranks)
        if rank > top or rank == top:
            return 0.60
        middle = sorted(board_ranks)[len(board_ranks) // 2]
        return 0.42 if rank >= middle else 0.32
    if flush_draw or (longest == 4 and len(board) < 5):
        return 0.30
    return 0.14 + max(hole_ranks) / 140


def versus_bet(raw: float) -> float:
    """Equity once a bet comes in from an opponent who rarely bets.

    Such a bet is mostly value, so one pair and worse lose most of their
    showdown equity. Two pair or better keep theirs.
    """
    if raw >= 0.75:
        return raw
    if raw >= 0.60:
        return 0.27  # top pair: continues against 1/2 pot, not 2/3 pot
    if raw >= 0.42:
        return 0.18
    if raw >= 0.32:
        return 0.14
    if raw >= 0.30:
        return 0.24  # a draw's equity doesn't depend on the bet being a bluff
    return 0.08


def postflop_action(state, loosen: float = 0.0) -> Response:
    """Check when free, otherwise call or fold on pot odds.

    ``loosen`` runs from 0 (their bets are value) to 1 (they bet so often that
    the raw showdown estimate applies).
    """
    if state.call_amount == 0:
        return Response.call()
    price = state.call_amount / (state.pot_size + state.call_amount)
    raw = rough_equity(state.hole_cards, state.community_cards)
    equity = versus_bet(raw) + (raw - versus_bet(raw)) * loosen
    return Response.call() if equity >= price else Response.fold()
