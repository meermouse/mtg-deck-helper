from dataclasses import dataclass


@dataclass
class Card:
    name: str
    quantity: int
    type_line: str
    mana_cost: str
    cmc: float
    colors: list[str]
    is_commander: bool
    oracle_text: str = ""


@dataclass
class Deck:
    name: str
    format: str
    commander: Card
    cards: list[Card]
    source_url: str | None


@dataclass
class HealthFlag:
    label: str
    status: str   # "ok" | "warning" | "error"
    message: str


@dataclass
class DeckStats:
    land_count: int
    avg_cmc: float
    curve: dict[int, int]
    type_counts: dict[str, int]
    color_pips: dict[str, int]
    ramp_count: int
    draw_count: int
    interaction_count: int
    health_flags: list[HealthFlag]


@dataclass
class Suggestion:
    card_name: str
    mana_cost: str
    reason: str


@dataclass
class AIAnalysis:
    themes: list[str]
    playstyle: str
    strengths: list[str]
    weaknesses: list[str]
    adds: list[Suggestion]
    cuts: list[Suggestion]
