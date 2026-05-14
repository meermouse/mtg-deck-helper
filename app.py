import os
from collections import defaultdict

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
            except Exception as e:
                st.error(f"AI analysis failed: {e}")
            else:
                st.rerun()

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
