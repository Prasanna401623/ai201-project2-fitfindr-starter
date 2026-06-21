"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    listings = load_listings()

    # Step 1: Filter by price and size
    filtered = []
    for item in listings:
        if max_price is not None and item["price"] > max_price:
            continue
        if size is not None and size.lower() not in item["size"].lower():
            continue
        filtered.append(item)

    # Step 2: Score by keyword overlap with description
    keywords = description.lower().split()

    def score(item):
        searchable = (
            item["title"].lower()
            + " "
            + item["description"].lower()
            + " "
            + " ".join(item["style_tags"]).lower()
        )
        return sum(1 for kw in keywords if kw in searchable)

    # Step 3: Drop zero-score items, sort best first
    results = [item for item in filtered if score(item) > 0]
    results.sort(key=score, reverse=True)

    return results


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    client = _get_groq_client()

    item_summary = (
        f"{new_item['title']} — {new_item['category']}, "
        f"colors: {', '.join(new_item['colors'])}, "
        f"style: {', '.join(new_item['style_tags'])}"
    )

    if not wardrobe["items"]:
        prompt = (
            f"A user is considering buying this thrifted item: {item_summary}. "
            f"They haven't entered their wardrobe yet. Give them 2 specific suggestions "
            f"for what kinds of pieces pair well with it — mention silhouettes, colors, "
            f"and the overall vibe. Be casual and specific, not generic."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {w['name']} ({w['category']}, colors: {', '.join(w['colors'])}, "
            f"style: {', '.join(w['style_tags'])})"
            for w in wardrobe["items"]
        )
        prompt = (
            f"A user is considering buying this thrifted item: {item_summary}. "
            f"Here is their current wardrobe:\n{wardrobe_lines}\n\n"
            f"Suggest 2 complete outfit combinations using the new item and specific "
            f"pieces from their wardrobe. Name the exact wardrobe pieces in each outfit. "
            f"Be casual and specific — mention the vibe, how to style it, any small details "
            f"like tucking or layering. Do not be generic."
        )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300,
    )

    return response.choices[0].message.content.strip()
# ── Tool 3: create_fit_card ───────────────────────────────────────────────────
def create_fit_card(outfit: str, new_item: dict) -> str:
    if not outfit or not outfit.strip():
        return "Couldn't generate a fit card — the outfit description was missing. Try running the full search again."

    client = _get_groq_client()

    prompt = (
        f"Write a 2-4 sentence Instagram caption for this thrifted outfit. "
        f"The thrifted item is: {new_item['title']}, bought on {new_item['platform']} for ${new_item['price']}. "
        f"The outfit: {outfit}\n\n"
        f"Rules: write in first person, casual tone like a real OOTD post, "
        f"mention the item name, price, and platform once each naturally, "
        f"capture the specific vibe of the outfit, add 1-2 relevant emojis. "
        f"Do NOT write it like a product description. Make it sound like a real person posted it."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=1.0,
    )

    return response.choices[0].message.content.strip()