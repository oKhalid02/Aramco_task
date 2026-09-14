"""Step 4: map free-text invoice descriptions to contracted services (deterministic part).

A description matches a service when every description token can be assigned to a *different* word of
the service name, where a token abbreviates a word if it is equal to it, a prefix of it, or a
same-first-letter subsequence of it ("Spclst" -> "specialist"), plus one domain abbreviation
("Ent" -> otolaryngologic). Service words may be missing from the description (dropped words).

Certainty levels:
  exact      the only service with all its words present
  strong     the only service consistent with the tokens, some of its words dropped
  ambiguous  two or more services are consistent with every token
  none       no service explains every token (candidate unknown_service)
Price is never used here (Phase 2 principle 4).
"""

import re
from functools import lru_cache

DOMAIN_ABBREVIATIONS = {"ent": {"otolaryngologic"}}  # ear-nose-throat; the only token not derivable by rule


def tokens(description: str):
    text = re.sub(r"/[A-Z]{2}-\d+", " ", description)  # hospital noise codes: /NG-3022, /RM-1234 ...
    return tuple(re.findall(r"[a-z]+", text.lower()))


def _subsequence(token: str, word: str) -> bool:
    if token[0] != word[0]:
        return False
    it = iter(word)
    return all(ch in it for ch in token)


@lru_cache(maxsize=None)
def match_quality(token: str, word: str) -> int:
    """3 exact, 2 prefix, 1 subsequence/domain abbreviation, 0 no match."""
    if token == word:
        return 3
    if word.startswith(token):
        return 2
    if word in DOMAIN_ABBREVIATIONS.get(token, ()) or _subsequence(token, word):
        return 1
    return 0


def best_assignment(toks, words):
    """Injective token->word assignment maximising total match quality; None if impossible."""
    best = None

    def search(i, used, score):
        nonlocal best
        if i == len(toks):
            if best is None or score > best:
                best = score
            return
        for j, w in enumerate(words):
            if j not in used:
                q = match_quality(toks[i], w)
                if q:
                    search(i + 1, used | {j}, score + q)

    search(0, frozenset(), 0)
    return best


class Matcher:
    def __init__(self, services, tie_rule="any_multiple"):
        self.services = {name: tuple(name.lower().split()) for name in services}
        self.tie_rule = tie_rule  # "fewest_missing" reproduces the first Phase 3 run

    @lru_cache(maxsize=None)
    def match(self, description: str):
        toks = tokens(description)
        scored = []
        for name, words in self.services.items():
            if len(toks) > len(words):
                continue
            quality = best_assignment(toks, words)
            if quality is not None:
                scored.append((len(words) - len(toks), -quality, name))
        if not toks or not scored:
            return {"service": None, "certainty": "none", "candidates": []}
        scored.sort()
        exact = [s[2] for s in scored if s[0] == 0]
        if len(exact) == 1:
            return {"service": exact[0], "certainty": "exact", "candidates": exact}
        if self.tie_rule == "fewest_missing":
            candidates = [s[2] for s in scored if s[0] == scored[0][0]]
        else:
            candidates = [s[2] for s in scored]
        if len(candidates) > 1:
            # Several services explain every token. Dropping fewer words is not evidence (it only favours
            # shorter names: "Emer Ortho" fits a Consultation and a Rehabilitation Programme), so it is a tie.
            return {"service": None, "certainty": "ambiguous", "candidates": candidates}
        return {"service": candidates[0], "certainty": "strong", "candidates": candidates}
