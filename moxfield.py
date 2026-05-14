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
    response = requests.get(_MOXFIELD_API.format(deck_id), headers=_HEADERS, timeout=10)
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

        # Strip Moxfield clipboard annotations: (SET) 123 and *TAGS*
        name = re.sub(r"\s*\([A-Z0-9]{2,6}\)\s*\d*\s*$", "", name).strip()
        name = re.sub(r"\s*\*[A-Z]+\*\s*$", "", name).strip()

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
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
