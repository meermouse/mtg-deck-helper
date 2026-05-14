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
        plural = "Sorceries" if type_name == "Sorcery" else f"{type_name}s"
        card_list += f"\n{plural} ({len(cards)}):\n"
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
        max_tokens=4096,
        messages=[{"role": "user", "content": build_prompt(deck, stats)}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"```\s*$", "", raw).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"AI returned invalid JSON: {exc}\n\nRaw response:\n{raw[:500]}") from exc
    return AIAnalysis(
        themes=data.get("themes", []),
        playstyle=data.get("playstyle", ""),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        adds=[Suggestion(card_name=s["card_name"], mana_cost=s["mana_cost"], reason=s["reason"])
              for s in data.get("adds", [])],
        cuts=[Suggestion(card_name=s["card_name"], mana_cost=s["mana_cost"], reason=s["reason"])
              for s in data.get("cuts", [])],
    )
