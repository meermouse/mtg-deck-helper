# MTG Deck Helper — Design Spec

**Date:** 2026-05-14
**Format scope:** Commander/EDH only
**Deployment target:** Streamlit

---

## Overview

A web application that helps Magic: The Gathering players review their Commander decks and receive improvement suggestions. Users connect their Moxfield account by providing a public deck URL; the app fetches the decklist, computes rule-based statistics, and optionally calls Claude for AI-powered strategic analysis and card suggestions.

---

## Architecture

Five Python modules with a single responsibility each:

```
mtg-deck-helper/
├── app.py          # Streamlit entry point — UI layout, wires all modules together
├── moxfield.py     # Fetches deck from Moxfield API or parses a pasted decklist
├── analyzer.py     # Rule-based Commander analysis (lands, curve, types, ramp, draw, interaction)
├── ai.py           # Claude API integration — theme, strategy, card suggestions
├── models.py       # Shared dataclasses: Deck, Card, DeckStats, AIAnalysis
└── requirements.txt
```

### Data Flow

1. User provides a Moxfield URL or pastes a decklist → `moxfield.py` returns a `Deck` object.
2. `Deck` is passed to `analyzer.py` → returns a `DeckStats` object.
3. On demand, `Deck` + `DeckStats` are passed to `ai.py` → returns an `AIAnalysis` object.
4. `app.py` renders all three objects using Streamlit's sidebar + main panel layout.

---

## Data Models (`models.py`)

```python
@dataclass
class Card:
    name: str
    quantity: int
    type_line: str       # e.g. "Legendary Creature — Angel"
    mana_cost: str       # e.g. "{W}{U}{B}{G}"
    cmc: float
    colors: list[str]    # ["W", "U", "B", "G"]
    is_commander: bool

@dataclass
class Deck:
    name: str
    format: str          # always "commander" in v1
    commander: Card
    cards: list[Card]    # all 100 cards including commander
    source_url: str | None

@dataclass
class HealthFlag:
    label: str
    status: str          # "ok" | "warning" | "error"
    message: str

@dataclass
class DeckStats:
    land_count: int
    avg_cmc: float
    curve: dict[int, int]          # cmc → card count
    type_counts: dict[str, int]    # "Creature" → 24, "Land" → 37, etc.
    color_pips: dict[str, int]     # "W" → 22, "U" → 18, etc.
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
    themes: list[str]       # e.g. ["Superfriends", "Proliferate", "Control"]
    playstyle: str          # prose paragraph
    strengths: list[str]
    weaknesses: list[str]
    adds: list[Suggestion]
    cuts: list[Suggestion]
```

---

## Moxfield Integration (`moxfield.py`)

### URL path (primary)

1. Extract deck ID from URL using regex: `/decks/([A-Za-z0-9_-]+)`
2. `GET https://api2.moxfield.com/v3/decks/all/{deck_id}` — no authentication required for public decks.
3. Parse JSON response into `Deck` and `Card` objects. The commander is identified from the `commanders` field in the response.
4. On HTTP error or private deck (401/403): surface a clear error message and prompt the user to use the paste fallback.

### Paste fallback

1. Accept standard MTG decklist format: `1 Card Name` or `4x Card Name`, one per line. Lines starting with `#` or blank lines are ignored. The commander is identified by a `Commander` section header line (e.g. `Commander` on its own line, followed by `1 Card Name` on the next). If no section header is present, the user is prompted to specify the commander via a text input.
2. For each unique card name, call `GET https://api.scryfall.com/cards/named?fuzzy={name}` to resolve CMC, type line, mana cost, and colour identity.
3. Scryfall calls are batched with a small delay to respect rate limits (10 req/s).

---

## Rule-Based Analysis (`analyzer.py`)

All thresholds are Commander-specific:

| Metric | Recommended range | Flag level |
|---|---|---|
| Land count | 36–38 | warning <36, error <33 |
| Ramp (mana rocks, dorks, land fetch) | ≥10 | warning <10, error <7 |
| Card draw | ≥12 | warning <12, error <8 |
| Interaction (removal, counters, wipes) | ≥10 | warning <10, error <6 |
| Average CMC | ≤3.5 | warning >3.5 |

**Computed outputs:**
- Mana curve histogram (`curve: dict[int, int]`)
- Card type breakdown (Lands, Creatures, Instants, Sorceries, Enchantments, Artifacts, Planeswalkers, Other)
- Colour pip distribution (count of each colour symbol across all mana costs)
- Health flags list (green ✓ / amber ⚠ / red ✗) for each metric above

**Ramp / draw / interaction classification:** keyword-based matching against known card names and oracle text keywords (e.g. "draw a card", "search your library for a land", "destroy target", "counter target spell"). This list is maintained as a simple set of strings in `analyzer.py` and can be expanded over time.

---

## AI Analysis (`ai.py`)

### Trigger
On-demand only — user clicks **Generate Analysis** button. Not called automatically.

### Prompt structure
A structured prompt is sent to Claude containing:
- Commander name and abilities
- Full card list grouped by type
- Pre-computed stats (land count, avg CMC, ramp/draw/interaction counts, health flags)

Claude is asked to return a JSON object matching the `AIAnalysis` schema (themes, playstyle, strengths, weaknesses, adds, cuts). The prompt instructs Claude to respond with only valid JSON so it can be parsed directly.

### Response handling
The full response is awaited before rendering (no streaming in v1 — streaming partial JSON is unreliable). A spinner is shown while the request is in flight. The completed JSON is parsed into an `AIAnalysis` object and all sections render at once.

### Configuration
`ANTHROPIC_API_KEY` is read from:
- Local: `.env` file (not committed)
- Deployed: Streamlit secrets (`st.secrets["ANTHROPIC_API_KEY"]`)

Model: `claude-sonnet-4-6` (can be changed via a constant in `ai.py`).

---

## UI Layout (`app.py`)

### Sidebar
- App title
- Moxfield URL input field + **Analyse Deck** button
- "— or —" divider + **Paste Decklist** toggle (reveals a text area)
- After analysis: commander name, colour identity chips, quick stats (lands, creatures, avg CMC, ramp, draw, interaction)

### Main Panel
**Commander banner** (always visible after analysis): commander name, type line, colour identity, identified theme label.

**Three tabs:**

1. **Statistics**
   - Mana curve bar chart
   - Card type breakdown with progress bars
   - Deck health checklist (green/amber/red flags)
   - Colour pip distribution

2. **AI Analysis**
   - Generate Analysis button
   - Theme tags + playstyle paragraph
   - Strengths / Weaknesses two-column layout
   - Card suggestions: "Consider Adding" and "Consider Cutting" sections, each card showing name, mana cost, and one-line reasoning

3. **Full Decklist**
   - Cards grouped by type, displayed as a readable list with quantities

---

## Configuration & Deployment

- Run locally: `streamlit run app.py`
- Requires `ANTHROPIC_API_KEY` in `.env` (local) or Streamlit secrets (deployed)
- No database — all state is in-memory per session
- No user accounts — decks are fetched fresh each session

---

## Out of Scope (v1)

- Formats other than Commander
- Deck editing or saving
- Price / budget analysis
- Card image display
- Authentication with Moxfield (private decks)
- Comparing multiple decks
