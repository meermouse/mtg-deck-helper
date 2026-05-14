import re
from collections import defaultdict
from models import Card, Deck, DeckStats, HealthFlag

# --- Classification keyword sets ---

_RAMP_ORACLE = [
    re.compile(r"add \{", re.IGNORECASE),
    re.compile(r"search your library for (?:up to \w+ )?(?:a basic )?(?:basic )?land", re.IGNORECASE),
]
_DRAW_ORACLE = [
    re.compile(r"draw (?:a|two|three|four|five|x|\d+) cards?", re.IGNORECASE),
    re.compile(r"draw cards equal", re.IGNORECASE),
]
_INTERACTION_ORACLE = [
    re.compile(r"destroy target", re.IGNORECASE),
    re.compile(r"exile target", re.IGNORECASE),
    re.compile(r"counter target (?:\w+ )*(?:spell|ability|activated|triggered)", re.IGNORECASE),
    re.compile(r"return target .{0,40} to (?:its|their) owner", re.IGNORECASE),
    re.compile(r"deals? \d+ damage to (?:target|any)", re.IGNORECASE),
]
_RAMP_NAME_RE = [re.compile(r"\bsignet\b", re.IGNORECASE), re.compile(r"\btalisman\b", re.IGNORECASE)]
_KNOWN_RAMP = {
    "sol ring", "arcane signet", "cultivate", "kodama's reach", "rampant growth",
    "farseek", "nature's lore", "three visits", "mind stone", "commander's sphere",
    "darksteel ingot", "chromatic lantern", "wayfarer's bauble", "expedition map",
    "skyshroud claim", "explosive vegetation", "search for tomorrow",
    "wood elves", "birds of paradise", "llanowar elves", "elvish mystic",
    "fyndhorn elves", "boreal druid", "arbor elf", "priest of titania",
    "solemn simulacrum", "burnished hart", "myriad landscape",
}
_KNOWN_DRAW = {
    "rhystic study", "phyrexian arena", "necropotence", "sylvan library",
    "consecrated sphinx", "brainstorm", "ponder", "preordain",
    "night's whisper", "read the bones", "sign in blood",
    "well of lost dreams", "mystic remora", "dig through time",
    "treasure cruise", "fact or fiction", "painful truths",
    "harmonize", "shamanic revelation", "wheel of fortune",
}
_KNOWN_INTERACTION = {
    "swords to plowshares", "path to exile", "cyclonic rift",
    "counterspell", "negate", "mana drain", "force of will",
    "generous gift", "beast within", "reality shift", "chaos warp",
    "murder", "doom blade", "go for the throat", "fatal push",
    "wrath of god", "damnation", "toxic deluge", "day of judgment",
    "vandalblast", "krosan grip", "naturalize", "disenchant",
    "vindicate", "anguished unmaking", "utter end",
}

# --- Type classification ---

_TYPE_ORDER = ["Land", "Creature", "Planeswalker", "Instant", "Sorcery", "Artifact", "Enchantment"]


def get_primary_type(type_line: str) -> str:
    for t in _TYPE_ORDER:
        if t in type_line:
            return t
    return "Other"


# --- Card classification helpers ---

def _is_land(card: Card) -> bool:
    return "Land" in card.type_line


def _is_ramp(card: Card) -> bool:
    name_lower = card.name.lower()
    if name_lower in _KNOWN_RAMP:
        return True
    if any(p.search(card.name) for p in _RAMP_NAME_RE):
        return True
    if card.oracle_text and any(p.search(card.oracle_text) for p in _RAMP_ORACLE):
        return True
    return False


def _is_draw(card: Card) -> bool:
    if card.name.lower() in _KNOWN_DRAW:
        return True
    if card.oracle_text and any(p.search(card.oracle_text) for p in _DRAW_ORACLE):
        return True
    return False


def _is_interaction(card: Card) -> bool:
    if card.name.lower() in _KNOWN_INTERACTION:
        return True
    if card.oracle_text and any(p.search(card.oracle_text) for p in _INTERACTION_ORACLE):
        return True
    return False


def _count_color_pips(mana_cost: str) -> dict[str, int]:
    pips: dict[str, int] = defaultdict(int)
    for symbol in re.findall(r"\{([WUBRG])\}", mana_cost):
        pips[symbol] += 1
    return dict(pips)


# --- Health flags ---

def _land_flag(count: int) -> HealthFlag:
    if count >= 36:
        return HealthFlag("Lands", "ok", f"Land count is good ({count})")
    if count >= 33:
        return HealthFlag("Lands", "warning", f"Land count is a bit low ({count}, recommended 36–38)")
    return HealthFlag("Lands", "error", f"Land count is too low ({count}, recommended 36–38)")


def _ramp_flag(count: int) -> HealthFlag:
    if count >= 10:
        return HealthFlag("Ramp", "ok", f"Ramp count is good ({count})")
    if count >= 7:
        return HealthFlag("Ramp", "warning", f"Ramp is slightly low ({count}, recommended ≥10)")
    return HealthFlag("Ramp", "error", f"Ramp is too low ({count}, recommended ≥10)")


def _draw_flag(count: int) -> HealthFlag:
    if count >= 12:
        return HealthFlag("Card Draw", "ok", f"Card draw is good ({count})")
    if count >= 8:
        return HealthFlag("Card Draw", "warning", f"Card draw is slightly low ({count}, recommended ≥12)")
    return HealthFlag("Card Draw", "error", f"Card draw is too low ({count}, recommended ≥12)")


def _interaction_flag(count: int) -> HealthFlag:
    if count >= 10:
        return HealthFlag("Interaction", "ok", f"Interaction is good ({count})")
    if count >= 6:
        return HealthFlag("Interaction", "warning", f"Interaction is slightly low ({count}, recommended ≥10)")
    return HealthFlag("Interaction", "error", f"Interaction is too low ({count}, recommended ≥10)")


def _cmc_flag(avg: float) -> HealthFlag:
    if avg <= 3.5:
        return HealthFlag("Average CMC", "ok", f"Average CMC is good ({avg:.2f})")
    return HealthFlag("Average CMC", "warning", f"Average CMC is high ({avg:.2f}, recommended ≤3.5)")


# --- Main analysis function ---

def analyze(deck: Deck) -> DeckStats:
    expanded = [card for card in deck.cards for _ in range(card.quantity)]

    lands = [c for c in expanded if _is_land(c)]
    non_lands = [c for c in expanded if not _is_land(c)]

    land_count = len(lands)
    avg_cmc = sum(c.cmc for c in non_lands) / len(non_lands) if non_lands else 0.0

    curve: dict[int, int] = defaultdict(int)
    for c in non_lands:
        curve[min(int(c.cmc), 7)] += 1

    type_counts: dict[str, int] = defaultdict(int)
    for c in expanded:
        type_counts[get_primary_type(c.type_line)] += 1

    color_pips: dict[str, int] = defaultdict(int)
    for c in expanded:
        for color, count in _count_color_pips(c.mana_cost).items():
            color_pips[color] += count

    ramp_count = sum(1 for c in expanded if not _is_land(c) and _is_ramp(c))
    draw_count = sum(1 for c in expanded if not _is_land(c) and _is_draw(c))
    interaction_count = sum(1 for c in expanded if not _is_land(c) and _is_interaction(c))

    return DeckStats(
        land_count=land_count,
        avg_cmc=round(avg_cmc, 2),
        curve=dict(curve),
        type_counts=dict(type_counts),
        color_pips=dict(color_pips),
        ramp_count=ramp_count,
        draw_count=draw_count,
        interaction_count=interaction_count,
        health_flags=[
            _land_flag(land_count),
            _ramp_flag(ramp_count),
            _draw_flag(draw_count),
            _interaction_flag(interaction_count),
            _cmc_flag(round(avg_cmc, 2)),
        ],
    )
