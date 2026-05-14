import pytest
from unittest.mock import patch, MagicMock
from moxfield import extract_deck_id, fetch_from_url, parse_decklist, _scryfall_lookup


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
    _map = {**_SCRYFALL_MAP}
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
