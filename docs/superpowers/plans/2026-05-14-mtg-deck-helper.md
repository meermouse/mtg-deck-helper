# MTG Deck Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit web app that fetches a Commander deck from Moxfield, computes rule-based statistics, and optionally calls Claude for strategic analysis and card suggestions.

**Architecture:** Five modules — `models.py` (dataclasses), `moxfield.py` (fetch/parse), `analyzer.py` (rule-based stats), `ai.py` (Claude integration), `app.py` (Streamlit UI). Data flows: Moxfield → Deck → DeckStats → optional AIAnalysis → rendered UI.

**Tech Stack:** Python 3.11+, Streamlit ≥1.32, anthropic ≥0.25, requests ≥2.31, python-dotenv ≥1.0, pytest ≥8.0

---

## File Map

| File | Role |
|---|---|
| `models.py` | Dataclasses: Card, Deck, HealthFlag, DeckStats, Suggestion, AIAnalysis |
| `moxfield.py` | `fetch_from_url()`, `parse_decklist()`, `_scryfall_lookup()` |
| `analyzer.py` | `analyze()`, `get_primary_type()`, keyword sets for ramp/draw/interaction |
| `ai.py` | `build_prompt()`, `get_ai_analysis()` |
| `app.py` | Streamlit entry point, all rendering functions |
| `tests/test_models.py` | Dataclass smoke tests |
| `tests/test_moxfield.py` | URL parsing, Moxfield response parsing, paste parsing |
| `tests/test_analyzer.py` | Each stat metric, health flags, ramp/draw/interaction |
| `tests/test_ai.py` | Prompt building, response parsing |
| `requirements.txt` | Dependencies |
| `.env.example` | Template for local secrets |

---

## Task 1: Project Setup & Data Models

**Files:**
- Create: `models.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write requirements.txt**

```
streamlit>=1.32.0
anthropic>=0.25.0
requests>=2.31.0
python-dotenv>=1.0.0
pytest>=8.0.0
```

- [ ] **Step 2: Write .env.example**

```
ANTHROPIC_API_KEY=your-api-key-here
```

- [ ] **Step 3: Write the failing test for models**

Create `tests/__init__.py` (empty) and `tests/test_models.py`:

```python
from models import Card, Deck, HealthFlag, DeckStats, Suggestion, AIAnalysis


def test_card_defaults():
    card = Card(
        name="Sol Ring", quantity=1, type_line="Artifact",
        mana_cost="{1}", cmc=1.0, colors=[], is_commander=False,
    )
    assert card.oracle_text == ""
    assert card.is_commander is False


def test_deck_holds_commander():
    commander = Card(
        name="Atraxa, Praetors' Voice", quantity=1,
        type_line="Legendary Creature — Phyrexian Angel Horror",
        mana_cost="{G}{W}{U}{B}", cmc=4.0,
        colors=["W", "U", "B", "G"], is_commander=True,
    )
    deck = Deck(
        name="Test", format="commander",
        commander=commander, cards=[commander], source_url=None,
    )
    assert deck.commander.name == "Atraxa, Praetors' Voice"
    assert len(deck.cards) == 1


def test_health_flag_statuses():
    for status in ("ok", "warning", "error"):
        flag = HealthFlag(label="Lands", status=status, message="msg")
        assert flag.status == status


def test_ai_analysis_suggestions():
    s = Suggestion(card_name="Cyclonic Rift", mana_cost="{1}{U}", reason="Board reset.")
    analysis = AIAnalysis(
        themes=["Control"], playstyle="Control strategy.",
        strengths=["Good"], weaknesses=["Slow"],
        adds=[s], cuts=[],
    )
    assert analysis.adds[0].card_name == "Cyclonic Rift"
```

- [ ] **Step 4: Run test — verify it fails**

```
pytest tests/test_models.py -v
```
Expected: `ModuleNotFoundError: No module named 'models'`

- [ ] **Step 5: Write models.py**

```python
from dataclasses import dataclass, field


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
```

- [ ] **Step 6: Run test — verify it passes**

```
pytest tests/test_models.py -v
```
Expected: `4 passed`

- [ ] **Step 7: Install dependencies**

```
pip install -r requirements.txt
```

- [ ] **Step 8: Commit**

```
git add models.py requirements.txt .env.example tests/
git commit -m "feat: add data models and project setup"
```

---

## Task 2: Moxfield URL Fetching

**Files:**
- Create: `moxfield.py` (URL path only)
- Modify: `tests/test_moxfield.py`

- [ ] **Step 1: Write failing tests for URL parsing and Moxfield response**

Create `tests/test_moxfield.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from moxfield import extract_deck_id, fetch_from_url


def test_extract_deck_id_standard_url():
    assert extract_deck_id("https://www.moxfield.com/decks/abc123XYZ") == "abc123XYZ"


def test_extract_deck_id_no_trailing_slash():
    assert extract_deck_id("https://moxfield.com/decks/My-Deck-ID_99") == "My-Deck-ID_99"


def test_extract_deck_id_invalid_url():
    with pytest.raises(ValueError, match="Could not extract deck ID"):
        extract_deck_id("https://moxfield.com/users/someone")


_MOCK_MOXFIELD_RESPONSE = {
    "name": "Test Deck",
    "format": "commander",
    "boards": {
        "commanders": {
            "cards": {
                "id1": {
                    "quantity": 1,
                    "card": {
                        "name": "Atraxa, Praetors' Voice",
                        "type_line": "Legendary Creature — Phyrexian Angel Horror",
                        "mana_cost": "{G}{W}{U}{B}",
                        "cmc": 4.0,
                        "colors": ["W", "U", "B", "G"],
                        "oracle_text": "Flying, vigilance, deathtouch, lifelink.",
                    },
                }
            }
        },
        "mainboard": {
            "cards": {
                "id2": {
                    "quantity": 1,
                    "card": {
                        "name": "Sol Ring",
                        "type_line": "Artifact",
                        "mana_cost": "{1}",
                        "cmc": 1.0,
                        "colors": [],
                        "oracle_text": "{T}: Add {C}{C}.",
                    },
                }
            }
        },
    },
}


def test_fetch_from_url_parses_deck():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _MOCK_MOXFIELD_RESPONSE
    with patch("moxfield.requests.get", return_value=mock_resp):
        deck = fetch_from_url("https://www.moxfield.com/decks/abc123")

    assert deck.name == "Test Deck"
    assert deck.commander.name == "Atraxa, Praetors' Voice"
    assert deck.commander.is_commander is True
    assert len(deck.cards) == 2
    assert deck.source_url == "https://www.moxfield.com/decks/abc123"


def test_fetch_from_url_http_error():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = Exception("404")
    with patch("moxfield.requests.get", return_value=mock_resp):
        with pytest.raises(Exception):
            fetch_from_url("https://www.moxfield.com/decks/private")
```

- [ ] **Step 2: Run tests — verify they fail**

```
pytest tests/test_moxfield.py -v
```
Expected: `ModuleNotFoundError: No module named 'moxfield'`

- [ ] **Step 3: Write moxfield.py (URL path)**

```python
import re
import time
import requests
from models import Card, Deck

_MOXFIELD_API = "https://api2.moxfield.com/v3/decks/all/{}"
_SCRYFALL_API = "https://api.scryfall.com/cards/named"
_HEADERS = {"User-Agent": "MTG-Deck-Helper/1.0"}


def extract_deck_id(url: str) -> str:
    match = re.search(r"/decks/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(f"Could not extract deck ID from URL: {url}")
    return match.group(1)


def fetch_from_url(url: str) -> Deck:
    deck_id = extract_deck_id(url)
    response = requests.get(_MOXFIELD_API.format(deck_id), headers=_HEADERS)
    response.raise_for_status()
    return _parse_moxfield_response(response.json(), source_url=url)


def _parse_moxfield_response(data: dict, source_url: str | None) -> Deck:
    boards = data.get("boards", {})

    commander_cards = boards.get("commanders", {}).get("cards", {})
    if not commander_cards:
        raise ValueError("No commander found in deck data")
    commander = _parse_card(next(iter(commander_cards.values())), is_commander=True)

    cards = [commander]
    for entry in boards.get("mainboard", {}).get("cards", {}).values():
        cards.append(_parse_card(entry, is_commander=False))

    return Deck(
        name=data.get("name", "Unknown Deck"),
        format=data.get("format", "commander"),
        commander=commander,
        cards=cards,
        source_url=source_url,
    )


def _parse_card(entry: dict, is_commander: bool) -> Card:
    c = entry.get("card", {})
    return Card(
        name=c.get("name", ""),
        quantity=entry.get("quantity", 1),
        type_line=c.get("type_line", ""),
        mana_cost=c.get("mana_cost", ""),
        cmc=float(c.get("cmc", 0)),
        colors=c.get("colors", []),
        is_commander=is_commander,
        oracle_text=c.get("oracle_text", ""),
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```
pytest tests/test_moxfield.py::test_extract_deck_id_standard_url tests/test_moxfield.py::test_extract_deck_id_no_trailing_slash tests/test_moxfield.py::test_extract_deck_id_invalid_url tests/test_moxfield.py::test_fetch_from_url_parses_deck tests/test_moxfield.py::test_fetch_from_url_http_error -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```
git add moxfield.py tests/test_moxfield.py
git commit -m "feat: add Moxfield URL fetching"
```

---

## Task 3: Paste Decklist + Scryfall Lookup

**Files:**
- Modify: `moxfield.py` (add paste path)
- Modify: `tests/test_moxfield.py` (add paste tests)

- [ ] **Step 1: Write failing tests for paste parsing**

Append to `tests/test_moxfield.py`:

```python
from moxfield import parse_decklist, _scryfall_lookup


_SCRYFALL_ATRAXA = {
    "name": "Atraxa, Praetors' Voice",
    "type_line": "Legendary Creature — Phyrexian Angel Horror",
    "mana_cost": "{G}{W}{U}{B}",
    "cmc": 4.0,
    "colors": ["W", "U", "B", "G"],
    "oracle_text": "Flying, vigilance, deathtouch, lifelink.",
}
_SCRYFALL_SOL_RING = {
    "name": "Sol Ring",
    "type_line": "Artifact",
    "mana_cost": "{1}",
    "cmc": 1.0,
    "colors": [],
    "oracle_text": "{T}: Add {C}{C}.",
}
_SCRYFALL_FOREST = {
    "name": "Forest",
    "type_line": "Basic Land — Forest",
    "mana_cost": "",
    "cmc": 0.0,
    "colors": [],
    "oracle_text": "",
}

_SCRYFALL_MAP = {
    "Atraxa, Praetors' Voice": _SCRYFALL_ATRAXA,
    "Sol Ring": _SCRYFALL_SOL_RING,
    "Forest": _SCRYFALL_FOREST,
}


def _mock_scryfall(card_name: str) -> dict:
    return _SCRYFALL_MAP[card_name]


_PASTE_TEXT = """Commander
1 Atraxa, Praetors' Voice

Mainboard
1 Sol Ring
1 Forest
"""


def test_parse_decklist_with_commander_section():
    with patch("moxfield._scryfall_lookup", side_effect=_mock_scryfall):
        with patch("moxfield.time.sleep"):
            deck = parse_decklist(_PASTE_TEXT, commander_override=None)

    assert deck.commander.name == "Atraxa, Praetors' Voice"
    assert deck.commander.is_commander is True
    assert len(deck.cards) == 3


def test_parse_decklist_commander_override():
    text = "1 Atraxa, Praetors' Voice\n1 Sol Ring\n1 Forest\n"
    with patch("moxfield._scryfall_lookup", side_effect=_mock_scryfall):
        with patch("moxfield.time.sleep"):
            deck = parse_decklist(text, commander_override="Atraxa, Praetors' Voice")

    assert deck.commander.name == "Atraxa, Praetors' Voice"


def test_parse_decklist_no_commander_raises():
    text = "1 Sol Ring\n1 Forest\n"
    with patch("moxfield._scryfall_lookup", side_effect=_mock_scryfall):
        with patch("moxfield.time.sleep"):
            with pytest.raises(ValueError, match="No commander"):
                parse_decklist(text, commander_override=None)


def test_parse_decklist_4x_format():
    text = "Commander\n1 Atraxa, Praetors' Voice\n\nMainboard\n4x Sol Ring\n"
    _map = {**_SCRYFALL_MAP, "Sol Ring": {**_SCRYFALL_SOL_RING}}
    with patch("moxfield._scryfall_lookup", side_effect=lambda n: _map[n]):
        with patch("moxfield.time.sleep"):
            deck = parse_decklist(text, commander_override=None)
    sol = next(c for c in deck.cards if c.name == "Sol Ring")
    assert sol.quantity == 4


def test_scryfall_lookup_calls_api():
    mock_resp = MagicMock()
    mock_resp.json.return_value = _SCRYFALL_SOL_RING
    with patch("moxfield.requests.get", return_value=mock_resp) as mock_get:
        result = _scryfall_lookup("Sol Ring")
    mock_get.assert_called_once()
    assert "fuzzy" in mock_get.call_args.kwargs["params"]
    assert result["name"] == "Sol Ring"
```

- [ ] **Step 2: Run new tests — verify they fail**

```
pytest tests/test_moxfield.py -k "paste or scryfall" -v
```
Expected: `ImportError` or `AttributeError` — `parse_decklist` not yet defined.

- [ ] **Step 3: Add paste path to moxfield.py**

Append to `moxfield.py`:

```python
def parse_decklist(text: str, commander_override: str | None) -> Deck:
    lines = text.strip().splitlines()
    current_section = "mainboard"
    commander_name: str | None = commander_override
    entries: list[tuple[str, int, str]] = []  # (section, qty, name)

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        lower = line.lower()
        if lower in ("commander", "commanders"):
            current_section = "commander"
            continue
        if lower in ("mainboard", "main", "deck"):
            current_section = "mainboard"
            continue
        if lower in ("sideboard", "side", "maybeboard"):
            current_section = "skip"
            continue
        if current_section == "skip":
            continue

        m = re.match(r"^(\d+)x?\s+(.+)$", line)
        if not m:
            continue
        qty, name = int(m.group(1)), m.group(2).strip()

        if current_section == "commander" and commander_name is None:
            commander_name = name
        entries.append((current_section, qty, name))

    if not commander_name:
        raise ValueError(
            "No commander found. Add a 'Commander' section header or pass commander_override."
        )

    unique_names = {name for _, _, name in entries}
    cache: dict[str, dict] = {}
    for name in unique_names:
        cache[name] = _scryfall_lookup(name)
        time.sleep(0.1)

    cards: list[Card] = []
    commander: Card | None = None
    for section, qty, name in entries:
        if section == "skip":
            continue
        data = cache[name]
        is_cmd = name == commander_name
        card = Card(
            name=data.get("name", name),
            quantity=qty,
            type_line=data.get("type_line", ""),
            mana_cost=data.get("mana_cost", ""),
            cmc=float(data.get("cmc", 0)),
            colors=data.get("colors", []),
            is_commander=is_cmd,
            oracle_text=data.get("oracle_text", ""),
        )
        if is_cmd:
            commander = card
        cards.append(card)

    if commander is None:
        raise ValueError(f"Commander '{commander_name}' not found in decklist.")

    return Deck(
        name="Pasted Deck",
        format="commander",
        commander=commander,
        cards=cards,
        source_url=None,
    )


def _scryfall_lookup(card_name: str) -> dict:
    response = requests.get(
        _SCRYFALL_API,
        params={"fuzzy": card_name},
        headers=_HEADERS,
    )
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run all moxfield tests — verify they pass**

```
pytest tests/test_moxfield.py -v
```
Expected: `10 passed`

- [ ] **Step 5: Commit**

```
git add moxfield.py tests/test_moxfield.py
git commit -m "feat: add paste decklist parsing with Scryfall lookup"
```

---

## Task 4: Rule-Based Analyzer

**Files:**
- Create: `analyzer.py`
- Create: `tests/test_analyzer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_analyzer.py`:

```python
import pytest
from models import Card, Deck
from analyzer import analyze, get_primary_type


def _make_deck(extra_cards: list[dict]) -> Deck:
    commander = Card(
        name="Atraxa, Praetors' Voice", quantity=1,
        type_line="Legendary Creature — Phyrexian Angel Horror",
        mana_cost="{G}{W}{U}{B}", cmc=4.0,
        colors=["W", "U", "B", "G"], is_commander=True,
    )
    cards = [commander] + [
        Card(
            name=d["name"], quantity=d.get("quantity", 1),
            type_line=d["type_line"], mana_cost=d.get("mana_cost", ""),
            cmc=d.get("cmc", 0.0), colors=d.get("colors", []),
            is_commander=False, oracle_text=d.get("oracle_text", ""),
        )
        for d in extra_cards
    ]
    return Deck(name="Test", format="commander", commander=commander,
                cards=cards, source_url=None)


def test_land_count():
    lands = [{"name": f"Forest {i}", "type_line": "Basic Land — Forest"} for i in range(37)]
    stats = analyze(_make_deck(lands))
    assert stats.land_count == 37


def test_avg_cmc_excludes_lands():
    cards = [
        {"name": "Sol Ring", "type_line": "Artifact", "cmc": 1.0, "mana_cost": "{1}"},
        {"name": "Counterspell", "type_line": "Instant", "cmc": 2.0, "mana_cost": "{U}{U}"},
        {"name": "Forest", "type_line": "Basic Land — Forest", "cmc": 0.0},
    ]
    stats = analyze(_make_deck(cards))
    # non-lands: Atraxa(4.0), Sol Ring(1.0), Counterspell(2.0) → avg = 7/3
    assert stats.avg_cmc == pytest.approx(7 / 3, rel=1e-2)


def test_curve_excludes_lands_and_caps_at_7():
    cards = [
        {"name": "Bolt", "type_line": "Instant", "cmc": 1.0},
        {"name": "Eldrazi", "type_line": "Creature", "cmc": 10.0},
        {"name": "Forest", "type_line": "Basic Land — Forest", "cmc": 0.0},
    ]
    stats = analyze(_make_deck(cards))
    assert stats.curve.get(1) == 1   # Bolt
    assert stats.curve.get(7) == 1   # Eldrazi capped at 7
    assert 0 not in stats.curve      # no land in curve


def test_type_counts():
    cards = [
        {"name": "Sol Ring", "type_line": "Artifact", "cmc": 1.0},
        {"name": "Counterspell", "type_line": "Instant", "cmc": 2.0},
        {"name": "Forest", "type_line": "Basic Land — Forest"},
    ]
    stats = analyze(_make_deck(cards))
    assert stats.type_counts["Creature"] == 1   # Atraxa
    assert stats.type_counts["Artifact"] == 1
    assert stats.type_counts["Instant"] == 1
    assert stats.type_counts["Land"] == 1


def test_color_pips():
    cards = [
        {"name": "Wrath of God", "type_line": "Sorcery", "cmc": 4.0, "mana_cost": "{2}{W}{W}"},
        {"name": "Counterspell", "type_line": "Instant", "cmc": 2.0, "mana_cost": "{U}{U}"},
    ]
    stats = analyze(_make_deck(cards))
    # Commander: G(1) W(1) U(1) B(1) + Wrath: W(2) + Counter: U(2)
    assert stats.color_pips.get("W", 0) == 3
    assert stats.color_pips.get("U", 0) == 3
    assert stats.color_pips.get("B", 0) == 1
    assert stats.color_pips.get("G", 0) == 1


def test_ramp_detected_by_known_name():
    cards = [{"name": "Sol Ring", "type_line": "Artifact", "cmc": 1.0, "mana_cost": "{1}"}]
    stats = analyze(_make_deck(cards))
    assert stats.ramp_count >= 1


def test_ramp_detected_by_oracle_text():
    cards = [{"name": "Custom Ramp", "type_line": "Sorcery", "cmc": 2.0,
              "oracle_text": "Search your library for a basic land card."}]
    stats = analyze(_make_deck(cards))
    assert stats.ramp_count >= 1


def test_draw_detected_by_oracle_text():
    cards = [{"name": "Night's Whisper", "type_line": "Sorcery", "cmc": 2.0,
              "oracle_text": "You draw two cards and you lose 2 life."}]
    stats = analyze(_make_deck(cards))
    assert stats.draw_count >= 1


def test_interaction_detected_by_oracle_text():
    cards = [{"name": "Custom Removal", "type_line": "Instant", "cmc": 2.0,
              "oracle_text": "Destroy target creature."}]
    stats = analyze(_make_deck(cards))
    assert stats.interaction_count >= 1


def test_health_flag_lands_ok():
    lands = [{"name": f"Forest {i}", "type_line": "Basic Land — Forest"} for i in range(37)]
    stats = analyze(_make_deck(lands))
    flag = next(f for f in stats.health_flags if f.label == "Lands")
    assert flag.status == "ok"


def test_health_flag_lands_warning():
    lands = [{"name": f"Forest {i}", "type_line": "Basic Land — Forest"} for i in range(34)]
    stats = analyze(_make_deck(lands))
    flag = next(f for f in stats.health_flags if f.label == "Lands")
    assert flag.status == "warning"


def test_health_flag_lands_error():
    lands = [{"name": f"Forest {i}", "type_line": "Basic Land — Forest"} for i in range(30)]
    stats = analyze(_make_deck(lands))
    flag = next(f for f in stats.health_flags if f.label == "Lands")
    assert flag.status == "error"


def test_get_primary_type_creature():
    assert get_primary_type("Legendary Creature — Angel") == "Creature"


def test_get_primary_type_land():
    assert get_primary_type("Basic Land — Forest") == "Land"


def test_get_primary_type_other():
    assert get_primary_type("Tribal Instant — Sliver") == "Instant"
```

- [ ] **Step 2: Run — verify they fail**

```
pytest tests/test_analyzer.py -v
```
Expected: `ModuleNotFoundError: No module named 'analyzer'`

- [ ] **Step 3: Write analyzer.py**

```python
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
    re.compile(r"counter target (?:spell|ability|activated|triggered)", re.IGNORECASE),
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
    draw_count = sum(1 for c in expanded if _is_draw(c))
    interaction_count = sum(1 for c in expanded if _is_interaction(c))

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
```

- [ ] **Step 4: Run tests — verify they pass**

```
pytest tests/test_analyzer.py -v
```
Expected: `14 passed`

- [ ] **Step 5: Commit**

```
git add analyzer.py tests/test_analyzer.py
git commit -m "feat: add rule-based Commander deck analyzer"
```

---

## Task 5: AI Module

**Files:**
- Create: `ai.py`
- Create: `tests/test_ai.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ai.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch
from models import Card, Deck, DeckStats, HealthFlag, AIAnalysis
from ai import build_prompt, get_ai_analysis


def _make_minimal_deck() -> Deck:
    commander = Card(
        name="Atraxa, Praetors' Voice", quantity=1,
        type_line="Legendary Creature — Phyrexian Angel Horror",
        mana_cost="{G}{W}{U}{B}", cmc=4.0,
        colors=["W", "U", "B", "G"], is_commander=True,
    )
    sol = Card(name="Sol Ring", quantity=1, type_line="Artifact",
               mana_cost="{1}", cmc=1.0, colors=[], is_commander=False)
    return Deck(name="Test", format="commander", commander=commander,
                cards=[commander, sol], source_url=None)


def _make_minimal_stats() -> DeckStats:
    return DeckStats(
        land_count=37, avg_cmc=2.8,
        curve={1: 5, 2: 14, 3: 11, 4: 8},
        type_counts={"Land": 37, "Creature": 24, "Artifact": 10},
        color_pips={"W": 20, "U": 18, "B": 14, "G": 9},
        ramp_count=12, draw_count=10, interaction_count=8,
        health_flags=[HealthFlag("Lands", "ok", "Good")],
    )


def test_build_prompt_contains_commander():
    prompt = build_prompt(_make_minimal_deck(), _make_minimal_stats())
    assert "Atraxa, Praetors' Voice" in prompt


def test_build_prompt_contains_stats():
    prompt = build_prompt(_make_minimal_deck(), _make_minimal_stats())
    assert "37" in prompt   # land count
    assert "2.8" in prompt  # avg cmc


def test_build_prompt_contains_card_list():
    prompt = build_prompt(_make_minimal_deck(), _make_minimal_stats())
    assert "Sol Ring" in prompt


def test_build_prompt_requests_json():
    prompt = build_prompt(_make_minimal_deck(), _make_minimal_stats())
    assert "JSON" in prompt or "json" in prompt


_MOCK_AI_RESPONSE = {
    "themes": ["Superfriends", "Proliferate"],
    "playstyle": "A controlling strategy focused on planeswalker ultimates.",
    "strengths": ["Strong card advantage", "Resilient win conditions"],
    "weaknesses": ["Slow start", "Relies on Atraxa"],
    "adds": [{"card_name": "Cyclonic Rift", "mana_cost": "{1}{U}", "reason": "Board reset."}],
    "cuts": [{"card_name": "Dark Ritual", "mana_cost": "{B}", "reason": "One-shot mana is weak here."}],
}


def test_get_ai_analysis_parses_response():
    mock_message = MagicMock()
    mock_message.content[0].text = json.dumps(_MOCK_AI_RESPONSE)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai.anthropic.Anthropic", return_value=mock_client):
        analysis = get_ai_analysis(_make_minimal_deck(), _make_minimal_stats(), api_key="test")

    assert isinstance(analysis, AIAnalysis)
    assert analysis.themes == ["Superfriends", "Proliferate"]
    assert len(analysis.adds) == 1
    assert analysis.adds[0].card_name == "Cyclonic Rift"
    assert analysis.cuts[0].mana_cost == "{B}"


def test_get_ai_analysis_strips_markdown_fences():
    mock_message = MagicMock()
    mock_message.content[0].text = "```json\n" + json.dumps(_MOCK_AI_RESPONSE) + "\n```"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai.anthropic.Anthropic", return_value=mock_client):
        analysis = get_ai_analysis(_make_minimal_deck(), _make_minimal_stats(), api_key="test")

    assert analysis.themes == ["Superfriends", "Proliferate"]
```

- [ ] **Step 2: Run — verify they fail**

```
pytest tests/test_ai.py -v
```
Expected: `ModuleNotFoundError: No module named 'ai'`

- [ ] **Step 3: Write ai.py**

```python
import json
import re
from collections import defaultdict
import anthropic
from models import Card, Deck, DeckStats, AIAnalysis, Suggestion
from analyzer import get_primary_type

MODEL = "claude-sonnet-4-6"


def build_prompt(deck: Deck, stats: DeckStats) -> str:
    grouped: dict[str, list[Card]] = defaultdict(list)
    for card in deck.cards:
        if not card.is_commander:
            grouped[get_primary_type(card.type_line)].append(card)

    card_list = ""
    for type_name in sorted(grouped):
        cards = grouped[type_name]
        card_list += f"\n{type_name}s ({len(cards)}):\n"
        for c in sorted(cards, key=lambda x: x.name):
            card_list += f"  - {c.quantity}x {c.name} [{c.mana_cost}]\n"

    health_lines = "\n".join(
        f"  - {f.label}: {f.status.upper()} — {f.message}"
        for f in stats.health_flags
    )

    return f"""You are an expert Magic: The Gathering Commander deckbuilder.
Analyse the following Commander deck and return a JSON object ONLY — no explanation, no markdown, just raw valid JSON.

DECK: {deck.name}
COMMANDER: {deck.commander.name} ({deck.commander.mana_cost})
FORMAT: Commander (100 cards, singleton)

STATISTICS:
  - Land count: {stats.land_count}
  - Average CMC: {stats.avg_cmc}
  - Ramp cards: {stats.ramp_count}
  - Card draw: {stats.draw_count}
  - Interaction: {stats.interaction_count}

HEALTH CHECK:
{health_lines}

CARD LIST:
{card_list}

Return exactly this JSON schema (no other text):
{{
  "themes": ["theme tag 1", "theme tag 2"],
  "playstyle": "A paragraph describing the strategy and win conditions.",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "adds": [
    {{"card_name": "Card Name", "mana_cost": "{{X}}{{Y}}", "reason": "One sentence."}}
  ],
  "cuts": [
    {{"card_name": "Card Name", "mana_cost": "{{X}}{{Y}}", "reason": "One sentence."}}
  ]
}}

Provide 3–5 themes, 3–5 strengths, 3–5 weaknesses, 3 add suggestions, 3 cut suggestions."""


def get_ai_analysis(deck: Deck, stats: DeckStats, api_key: str) -> AIAnalysis:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": build_prompt(deck, stats)}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    data = json.loads(raw)
    return AIAnalysis(
        themes=data.get("themes", []),
        playstyle=data.get("playstyle", ""),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        adds=[Suggestion(**s) for s in data.get("adds", [])],
        cuts=[Suggestion(**s) for s in data.get("cuts", [])],
    )
```

- [ ] **Step 4: Run tests — verify they pass**

```
pytest tests/test_ai.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```
git add ai.py tests/test_ai.py
git commit -m "feat: add Claude AI analysis module"
```

---

## Task 6: Streamlit App — Core Layout & Sidebar

**Files:**
- Modify: `app.py` (replace placeholder with full implementation)

- [ ] **Step 1: Write app.py**

```python
import os
import streamlit as st
from dotenv import load_dotenv

from moxfield import fetch_from_url, parse_decklist
from analyzer import analyze, get_primary_type
from ai import get_ai_analysis
from models import Deck, DeckStats, AIAnalysis

load_dotenv()

st.set_page_config(page_title="MTG Deck Helper", page_icon="🃏", layout="wide")

_COLOR_EMOJI = {"W": "☀️", "U": "💧", "B": "💀", "R": "🔥", "G": "🌿"}
_COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}
_STATUS_ICON = {"ok": "✅", "warning": "⚠️", "error": "❌"}


def _get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def _render_commander_banner(deck: Deck) -> None:
    colors_str = " ".join(_COLOR_EMOJI.get(c, c) for c in deck.commander.colors)
    ai: AIAnalysis | None = st.session_state.get("ai_analysis")
    theme_label = " · ".join(ai.themes[:2]) if ai else ""

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"### 👑 {deck.commander.name}")
            st.caption(f"{deck.commander.type_line}   {colors_str}")
        with col2:
            if theme_label:
                st.markdown(f"**Theme:** {theme_label}")


def _render_statistics(stats: DeckStats) -> None:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Mana Curve")
        curve_data = {
            (f"{k}+" if k == 7 else str(k)): v
            for k, v in sorted(stats.curve.items())
        }
        st.bar_chart(curve_data)

        st.subheader("Deck Health")
        for flag in stats.health_flags:
            icon = _STATUS_ICON[flag.status]
            st.markdown(f"{icon} {flag.message}")

    with col2:
        st.subheader("Card Types")
        total = sum(stats.type_counts.values())
        for type_name, count in sorted(stats.type_counts.items(), key=lambda x: -x[1]):
            st.markdown(f"**{type_name}** — {count}")
            st.progress(count / total if total else 0)

        st.subheader("Colour Distribution")
        total_pips = sum(stats.color_pips.values())
        for color, pips in sorted(stats.color_pips.items(), key=lambda x: -x[1]):
            label = f"{_COLOR_EMOJI.get(color, color)} {_COLOR_NAMES.get(color, color)}"
            st.markdown(f"**{label}** — {pips} pips")
            st.progress(pips / total_pips if total_pips else 0)


def _render_ai_analysis(deck: Deck, stats: DeckStats) -> None:
    api_key = _get_api_key()
    if not api_key:
        st.warning(
            "No Anthropic API key found. "
            "Set `ANTHROPIC_API_KEY` in your `.env` file or Streamlit secrets."
        )
        return

    if st.button("✨ Generate AI Analysis", type="primary"):
        with st.spinner("Analysing your deck with Claude..."):
            try:
                analysis = get_ai_analysis(deck, stats, api_key)
                st.session_state.ai_analysis = analysis
                st.rerun()
            except Exception as e:
                st.error(f"AI analysis failed: {e}")

    analysis: AIAnalysis | None = st.session_state.get("ai_analysis")
    if not analysis:
        return

    st.subheader("Theme & Playstyle")
    st.markdown(" ".join(f"`{t}`" for t in analysis.themes))
    st.write(analysis.playstyle)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("✅ Strengths")
        for s in analysis.strengths:
            st.markdown(f"- {s}")
    with col2:
        st.subheader("❌ Weaknesses")
        for w in analysis.weaknesses:
            st.markdown(f"- {w}")

    st.subheader("Consider Adding")
    for suggestion in analysis.adds:
        with st.container(border=True):
            st.markdown(f"**{suggestion.card_name}** `{suggestion.mana_cost}`")
            st.caption(suggestion.reason)

    st.subheader("Consider Cutting")
    for suggestion in analysis.cuts:
        with st.container(border=True):
            st.markdown(f"**{suggestion.card_name}** `{suggestion.mana_cost}`")
            st.caption(suggestion.reason)


def _render_decklist(deck: Deck) -> None:
    from collections import defaultdict
    grouped: dict[str, list] = defaultdict(list)
    for card in deck.cards:
        grouped[get_primary_type(card.type_line)].append(card)

    type_order = ["Creature", "Planeswalker", "Instant", "Sorcery",
                  "Enchantment", "Artifact", "Land", "Other"]
    for type_name in type_order:
        if type_name not in grouped:
            continue
        cards = sorted(grouped[type_name], key=lambda c: c.name)
        total = sum(c.quantity for c in cards)
        st.subheader(f"{type_name}s ({total})")
        for card in cards:
            st.markdown(f"- {card.quantity}x **{card.name}** `{card.mana_cost}`")


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🃏 MTG Deck Helper")
    st.caption("Commander Deck Analyser")
    st.divider()

    url_input = st.text_input("Moxfield URL", placeholder="https://moxfield.com/decks/...")
    if st.button("Analyse Deck", type="primary", use_container_width=True):
        if url_input.strip():
            with st.spinner("Fetching from Moxfield..."):
                try:
                    deck = fetch_from_url(url_input.strip())
                    st.session_state.deck = deck
                    st.session_state.stats = analyze(deck)
                    st.session_state.ai_analysis = None
                    st.session_state.error = None
                except Exception as exc:
                    st.session_state.error = str(exc)
        else:
            st.warning("Please enter a Moxfield URL.")

    with st.expander("— or paste a decklist —"):
        paste_text = st.text_area(
            "Decklist", height=200,
            placeholder="Commander\n1 Atraxa, Praetors' Voice\n\nMainboard\n1 Sol Ring\n...",
        )
        commander_override = st.text_input("Commander (if not in decklist)")
        if st.button("Analyse Pasted Deck", use_container_width=True):
            if paste_text.strip():
                with st.spinner("Looking up cards on Scryfall..."):
                    try:
                        deck = parse_decklist(paste_text, commander_override or None)
                        st.session_state.deck = deck
                        st.session_state.stats = analyze(deck)
                        st.session_state.ai_analysis = None
                        st.session_state.error = None
                    except Exception as exc:
                        st.session_state.error = str(exc)
            else:
                st.warning("Please paste a decklist.")

    if st.session_state.get("error"):
        st.error(st.session_state.error)

    if "deck" in st.session_state:
        _deck: Deck = st.session_state.deck
        _stats: DeckStats = st.session_state.stats
        st.divider()
        st.markdown(f"**{_deck.commander.name}**")
        st.caption(f"{_deck.name} • {sum(c.quantity for c in _deck.cards)} cards")
        st.write(" ".join(_COLOR_EMOJI.get(c, c) for c in _deck.commander.colors))
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Lands", _stats.land_count)
            st.metric("Avg CMC", f"{_stats.avg_cmc:.1f}")
            st.metric("Ramp", _stats.ramp_count)
        with col2:
            st.metric("Creatures", _stats.type_counts.get("Creature", 0))
            st.metric("Draw", _stats.draw_count)
            st.metric("Interaction", _stats.interaction_count)

# ── Main Panel ───────────────────────────────────────────────────────────────

if "deck" not in st.session_state:
    st.markdown("## Welcome to MTG Deck Helper")
    st.markdown(
        "Paste a **Moxfield deck URL** in the sidebar, or expand "
        "**'paste a decklist'** to enter cards manually."
    )
else:
    _deck = st.session_state.deck
    _stats = st.session_state.stats

    _render_commander_banner(_deck)

    tab1, tab2, tab3 = st.tabs(["📊 Statistics", "✨ AI Analysis", "📋 Full Decklist"])
    with tab1:
        _render_statistics(_stats)
    with tab2:
        _render_ai_analysis(_deck, _stats)
    with tab3:
        _render_decklist(_deck)
```

- [ ] **Step 2: Run the app to verify it starts**

```
streamlit run app.py
```
Expected: browser opens, welcome message displayed, no Python errors in terminal.

- [ ] **Step 3: Test sidebar — paste a small decklist**

Paste the following into the "paste a decklist" expander:

```
Commander
1 Atraxa, Praetors' Voice

Mainboard
1 Sol Ring
1 Cultivate
1 Swords to Plowshares
1 Rhystic Study
1 Forest
1 Island
1 Plains
1 Swamp
```

Click **Analyse Pasted Deck**. Expected: sidebar updates with quick stats, commander banner appears, Statistics tab shows mana curve and type breakdown.

- [ ] **Step 4: Test Moxfield URL (if you have a public deck)**

Enter a public Moxfield deck URL and click **Analyse Deck**. Expected: same result as paste path.

- [ ] **Step 5: Test AI Analysis tab**

With a deck loaded, click **✨ Generate AI Analysis**. Expected: spinner runs, analysis renders with themes, strengths, weaknesses, and suggestions. (Requires `ANTHROPIC_API_KEY` in `.env`.)

- [ ] **Step 6: Run backend tests to confirm nothing broke**

```
pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 7: Commit**

```
git add app.py
git commit -m "feat: add Streamlit UI with sidebar, stats, AI analysis, and decklist tabs"
```

---

## Task 7: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite README.md**

```markdown
# MTG Deck Helper

A Streamlit web application for reviewing Magic: The Gathering Commander decks.
Fetches deck data from Moxfield, computes statistics, and uses Claude for AI-powered suggestions.

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file (copy from `.env.example`) and add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

## Running

```bash
streamlit run app.py
```

## Usage

1. Enter a public Moxfield deck URL in the sidebar, or expand **"paste a decklist"** and paste a decklist in standard MTG format.
2. Click **Analyse Deck** to load statistics.
3. Explore the **Statistics** tab for mana curve, card type breakdown, colour distribution, and deck health.
4. Click **✨ Generate AI Analysis** for Claude's strategic assessment and card suggestions.

## Moxfield URL format

Works with any public deck URL: `https://www.moxfield.com/decks/<deck-id>`

## Paste format

```
Commander
1 Atraxa, Praetors' Voice

Mainboard
1 Sol Ring
1 Cultivate
...
```

## Project Structure

```
mtg-deck-helper/
├── app.py          # Streamlit UI
├── moxfield.py     # Moxfield + Scryfall integration
├── analyzer.py     # Rule-based deck analysis
├── ai.py           # Claude AI integration
├── models.py       # Data models
├── requirements.txt
└── tests/          # Pytest test suite
```

## Deployment (Streamlit Cloud)

1. Push to GitHub.
2. Connect repo at [share.streamlit.io](https://share.streamlit.io).
3. Add `ANTHROPIC_API_KEY` in the app's **Secrets** settings.
```

- [ ] **Step 2: Commit**

```
git add README.md .env.example
git commit -m "docs: update README with setup and usage instructions"
```

---

## Self-Review Checklist

Verifying spec coverage:

| Spec requirement | Task |
|---|---|
| Moxfield URL fetch | Task 2 |
| Paste fallback with Scryfall | Task 3 |
| Commander/EDH only | Tasks 2–4 (format always "commander") |
| Land count, avg CMC, mana curve | Task 4 |
| Card type breakdown | Task 4 |
| Colour pip distribution | Task 4 |
| Ramp / draw / interaction counts | Task 4 |
| Health flags (ok/warning/error) | Task 4 |
| Claude AI analysis on demand | Task 5 |
| JSON response parsing + fence stripping | Task 5 |
| Sidebar layout + quick stats | Task 6 |
| Commander banner | Task 6 |
| Statistics tab | Task 6 |
| AI Analysis tab | Task 6 |
| Full Decklist tab | Task 6 |
| ANTHROPIC_API_KEY from .env / secrets | Tasks 5–6 |
| requirements.txt + .env.example | Task 1 |
| README update | Task 7 |
