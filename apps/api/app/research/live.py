"""Score-conditioned win probabilities, not a trained live-state predictor."""
from functools import lru_cache
import math

VERSION = "live:markov:v1"


def probability(value):
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Probability must be finite and in [0, 1]")
    return value


def map_winner(a, b):
    if any(type(s) is not int or not 0 <= s <= 200 for s in (a, b)):
        raise ValueError("Invalid round score")
    if max(a, b) > 13 and (min(a, b) < 12 or abs(a-b) > 2):
        raise ValueError("Unreachable overtime score")
    if max(a, b) >= 13 and abs(a-b) >= 2:
        return int(a > b)
    return None


def map_probability(a, b, round_probability, *, defending_probability=None,
                    first_side=None, overtime_first_side=None):
    """12-round halves; overtime alternates sides and must be won by two.

    Side probabilities are optional scenario inputs. Production uses one inferred
    round probability: no unmeasured side advantage is invented.
    """
    attack = probability(round_probability)
    defend = attack if defending_probability is None else probability(defending_probability)
    if attack != defend and (first_side not in {"attack", "defend"}
                            or overtime_first_side not in {"attack", "defend"}):
        raise ValueError("Side-specific probabilities require both starting sides")
    terminal = map_winner(a, b)
    if terminal is not None:
        return float(terminal)

    def next_round(n):
        if n < 24:
            attacking = (first_side != "defend") == (n < 12)
        else:
            attacking = (overtime_first_side != "defend") == ((n-24) % 2 == 0)
        return attack if attacking else defend

    x, y = next_round(24), next_round(25)
    win, loss = x*y, (1-x)*(1-y)
    if win+loss == 0:
        raise ValueError("Degenerate side model never resolves overtime")
    deuce = win/(win+loss)

    @lru_cache(None)
    def solve(i, j):
        if max(i, j) >= 13 and abs(i-j) >= 2:
            return float(i > j)
        if min(i, j) >= 12:
            if i == j:
                return deuce
            p = next_round(i+j)
            return p+(1-p)*deuce if i > j else p*deuce
        p = next_round(i+j)
        return p*solve(i+1, j)+(1-p)*solve(i, j+1)
    return solve(a, b)


def series_probability(a, b, best_of, remaining):
    if best_of not in (1, 3, 5) or any(type(s) is not int or s < 0 for s in (a, b)):
        raise ValueError("Invalid series format or map score")
    target = best_of//2+1
    if a > target or b > target or (a == target and b == target):
        raise ValueError("Impossible series score")
    if a == target or b == target:
        return float(a == target)
    if len(remaining) != best_of-a-b:
        raise ValueError("A probability is required for every remaining map")
    ps = tuple(probability(p) for p in remaining)

    @lru_cache(None)
    def solve(x, y, n):
        if x == target or y == target:
            return float(x == target)
        return ps[n]*solve(x+1, y, n+1)+(1-ps[n])*solve(x, y+1, n+1)
    return solve(a, b, 0)


def invert_probability(target, function):
    probability(target)
    low, high = 0.0, 1.0
    for _ in range(45):
        mid = (low+high)/2
        if function(mid) < target:
            low = mid
        else:
            high = mid
    return (low+high)/2


def round_prior(series_prior, best_of):
    """Preserve the pre-match series prior exactly under exchangeable maps."""
    map_prior = invert_probability(series_prior, lambda p: series_probability(0, 0, best_of, [p]*best_of))
    return invert_probability(map_prior, lambda p: map_probability(0, 0, p))


def live_probability(series_prior, best_of, maps_a, maps_b, rounds=None):
    q = round_prior(series_prior, best_of)
    p_map = map_probability(0, 0, q)
    remaining = best_of-maps_a-maps_b
    current = map_probability(*rounds, q) if rounds is not None else p_map
    ps = [current] + [p_map]*max(0, remaining-1)
    return {"team1_win_probability": series_probability(maps_a, maps_b, best_of, ps),
            "current_map_probability": current if rounds is not None else None,
            "round_probability": q, "model_version": VERSION}
