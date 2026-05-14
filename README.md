# MTG Deck Helper

A Streamlit web application for reviewing Magic: The Gathering Commander decks.
Fetches deck data from Moxfield, computes statistics, and uses Claude for AI-powered suggestions.

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file (copy from `.env.example`) and add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

## Running

```bash
streamlit run app.py
```

## Usage

1. Enter a public Moxfield deck URL in the sidebar, or expand **"paste a decklist"** and paste a decklist in standard MTG format.
2. Click **Analyse Deck** to load statistics.
3. Explore the **Statistics** tab for mana curve, card type breakdown, colour distribution, and deck health.
4. Click **✨ Generate AI Analysis** for Claude's strategic assessment and card suggestions.

## Moxfield URL format

Works with any public deck URL: `https://www.moxfield.com/decks/<deck-id>`

## Paste format

```
Commander
1 Atraxa, Praetors' Voice

Mainboard
1 Sol Ring
1 Cultivate
...
```

## Project Structure

```
mtg-deck-helper/
├── app.py          # Streamlit UI
├── moxfield.py     # Moxfield + Scryfall integration
├── analyzer.py     # Rule-based deck analysis
├── ai.py           # Claude AI integration
├── models.py       # Data models
├── requirements.txt
└── tests/          # Pytest test suite
```

## Deployment (Streamlit Cloud)

1. Push to GitHub.
2. Connect repo at [share.streamlit.io](https://share.streamlit.io).
3. Add `ANTHROPIC_API_KEY` in the app's **Secrets** settings.
