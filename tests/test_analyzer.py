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


def _make_cards(tuples: list[tuple]) -> list[dict]:
    """Convert (name, type_line, mana_cost, cmc) tuples to dicts for _make_deck."""
    return [
        {"name": name, "type_line": type_line, "mana_cost": mana_cost, "cmc": cmc}
        for name, type_line, mana_cost, cmc in tuples
    ]


def test_ramp_health_flag_warning():
    cards = _make_cards(
        [("Sol Ring", "Artifact", "{1}", 1.0)] * 8
        + [("Forest", "Basic Land — Forest", "", 0.0)] * 36
        + [("Gray Ogre", "Creature", "{2}{R}", 3.0)] * 55
    )
    stats = analyze(_make_deck(cards))
    ramp_flag = next(f for f in stats.health_flags if f.label == "Ramp")
    assert ramp_flag.status == "warning"


def test_draw_health_flag_error():
    cards = _make_cards(
        [("Rhystic Study", "Enchantment", "{2}{U}", 3.0)] * 5
        + [("Forest", "Basic Land — Forest", "", 0.0)] * 36
        + [("Gray Ogre", "Creature", "{2}{R}", 3.0)] * 58
    )
    stats = analyze(_make_deck(cards))
    draw_flag = next(f for f in stats.health_flags if f.label == "Card Draw")
    assert draw_flag.status == "error"


def test_cmc_health_flag_warning():
    cards = _make_cards(
        [("Forest", "Basic Land — Forest", "", 0.0)] * 36
        + [("Emrakul", "Creature", "{15}", 15.0)] * 63
    )
    stats = analyze(_make_deck(cards))
    cmc_flag = next(f for f in stats.health_flags if f.label == "Average CMC")
    assert cmc_flag.status == "warning"
