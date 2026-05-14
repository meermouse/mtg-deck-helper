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
