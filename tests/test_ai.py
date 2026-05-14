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


def test_get_ai_analysis_raises_on_invalid_json():
    mock_message = MagicMock()
    mock_message.content[0].text = "this is not json"
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(ValueError, match="AI returned invalid JSON"):
            get_ai_analysis(_make_minimal_deck(), _make_minimal_stats(), api_key="test")


def test_get_ai_analysis_handles_extra_keys_in_suggestion():
    response_with_extra = {**_MOCK_AI_RESPONSE}
    response_with_extra["adds"] = [
        {"card_name": "Cyclonic Rift", "mana_cost": "{1}{U}", "reason": "Board reset.", "set": "RTR", "price": 12.5}
    ]
    mock_message = MagicMock()
    mock_message.content[0].text = json.dumps(response_with_extra)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai.anthropic.Anthropic", return_value=mock_client):
        analysis = get_ai_analysis(_make_minimal_deck(), _make_minimal_stats(), api_key="test")

    assert analysis.adds[0].card_name == "Cyclonic Rift"


def test_get_ai_analysis_missing_suggestion_key_raises():
    bad_response = {**_MOCK_AI_RESPONSE, "adds": [{"card_name": "Rift", "mana_cost": "{U}"}]}  # missing "reason"
    mock_message = MagicMock()
    mock_message.content[0].text = json.dumps(bad_response)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message

    with patch("ai.anthropic.Anthropic", return_value=mock_client):
        with pytest.raises(KeyError):
            get_ai_analysis(_make_minimal_deck(), _make_minimal_stats(), api_key="test")
