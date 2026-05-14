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
