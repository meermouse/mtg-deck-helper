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
