# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Describe what you're looking for, and FitFindr searches a mock thrift dataset, suggests outfits using your wardrobe, and generates a shareable fit card caption.

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Then open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Searches `data/listings.json` for thrifted items matching the user's request.

**Inputs:**
- `description` (str): Keywords describing the item (e.g. `"vintage graphic tee"`)
- `size` (str | None): Size filter — case-insensitive substring match (e.g. `"M"` matches `"S/M"`). Pass `None` to skip.
- `max_price` (float | None): Maximum price inclusive. Pass `None` to skip.

**Output:** `list[dict]` — matching listing dicts sorted by relevance score (keyword overlap across `title`, `description`, and `style_tags`). Returns `[]` if nothing matches — never raises an exception.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Given a thrifted item and the user's wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations.

**Inputs:**
- `new_item` (dict): A full listing dict from `search_listings`
- `wardrobe` (dict): A wardrobe dict with an `"items"` key containing a list of wardrobe item dicts. May be empty.

**Output:** `str` — outfit suggestions. If the wardrobe is empty, returns general styling advice instead of referencing specific pieces. Always returns a non-empty string.

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Calls the Groq LLM to generate a casual, shareable OOTD caption (2–4 sentences) for the outfit.

**Inputs:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`
- `new_item` (dict): The listing dict for the thrifted item

**Output:** `str` — an Instagram/TikTok-style caption mentioning the item name, price, and platform naturally. Returns a descriptive error string if `outfit` is empty — never raises an exception.

---

## How the Planning Loop Works

The planning loop runs inside `run_agent()` in `agent.py`. It follows this conditional logic:

1. **Parse the query** using regex to extract `description`, `size`, and `max_price` from the user's natural language input.

2. **Call `search_listings`** with the parsed parameters.
   - If results are empty → set `session["error"]` with a helpful message and **return early**. `suggest_outfit` and `create_fit_card` are never called.
   - If results are non-empty → set `session["selected_item"] = results[0]` and continue.

3. **Call `suggest_outfit`** with `session["selected_item"]` and the wardrobe. Store the result in `session["outfit_suggestion"]`. This always produces a non-empty string, so the loop always continues.

4. **Call `create_fit_card`** with `session["outfit_suggestion"]` and `session["selected_item"]`. Store the result in `session["fit_card"]`.

5. **Return the session.** `app.py` maps session keys to the three output panels.

The agent never calls a later tool with empty input — each step is gated on the previous step's output.

---

## State Management

All state lives in a single `session` dict initialized at the start of `run_agent()`:

```python
session = {
    "query": str,               # original user input
    "parsed": {},               # extracted description, size, max_price
    "search_results": [],       # full list returned by search_listings
    "selected_item": None,      # results[0] — passed into suggest_outfit and create_fit_card
    "wardrobe": dict,           # loaded once, passed into suggest_outfit
    "outfit_suggestion": None,  # string returned by suggest_outfit
    "fit_card": None,           # string returned by create_fit_card
    "error": None,              # set if the interaction ended early
}
```

`session["selected_item"]` is set once after `search_listings` and passed directly into both subsequent tools — the user never has to re-enter it. `session["outfit_suggestion"]` is set once after `suggest_outfit` and passed directly into `create_fit_card`. No values are re-fetched or hardcoded between steps.

---

## Error Handling

### `search_listings` — no results
If `search_listings` returns `[]`, the agent sets `session["error"]` to:
```
No listings found for '[description]' in size [size] under $[max_price].
Try broader keywords, removing the size filter, or increasing your budget.
```
The agent returns early — `suggest_outfit` and `create_fit_card` are never called with empty input.

**Tested by running:**
```bash
python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []
```

### `suggest_outfit` — empty wardrobe
If `wardrobe["items"]` is empty, the tool switches to a general styling prompt instead of a wardrobe-specific one. Returns general advice like what silhouettes and colors pair well with the item. Never crashes or returns an empty string.

**Tested by running:**
```bash
python -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
# Output: general styling advice, no exception
```

### `create_fit_card` — empty outfit string
If `outfit` is empty or whitespace-only, the tool returns immediately with:
```
Couldn't generate a fit card — the outfit description was missing. Try running the full search again.
```
No LLM call is made. Never raises an exception.

**Tested by running:**
```bash
python -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
# Output: error string, no exception
```

---

## Spec Reflection

**One way the spec helped:** Designing the planning loop's conditional logic in `planning.md` before writing any code made `run_agent()` straightforward to implement. Having the exact branch conditions written out ("if results == [], set error and return early") meant the implementation matched the spec on the first try with no ambiguity about when to stop.

**One way implementation diverged from the spec:** The spec described query parsing as "use regex, string splitting, or ask the LLM." I initially planned to use the LLM for parsing to handle natural language better, but switched to regex because it's faster (no extra API call), more predictable, and easier to test. The tradeoff is that unusual phrasings like "no more than thirty dollars" won't be parsed correctly — but for the dataset and demo queries in this project, regex is sufficient.

---

## AI Usage

**Instance 1 — `search_listings` implementation:**
I gave Claude the Tool 1 section of `planning.md` (inputs, return value, failure mode, full field list) and asked it to implement the function using `load_listings()` from the data loader, with case-insensitive substring size matching and keyword scoring across `title`, `description`, and `style_tags`. The generated code was correct but called `score()` twice per item (once to filter, once to sort). I revised it to compute scores once and reuse them, which is cleaner and avoids redundant work.

**Instance 2 — planning loop in `agent.py`:**
I gave Claude the Planning Loop section, State Management section, and the full ASCII architecture diagram from `planning.md`. The generated `run_agent()` correctly gated each tool call on the previous step's output and stored values in the session dict as specified. I overrode one thing: the generated code used the LLM to parse the query, which added an unnecessary API call. I replaced it with regex parsing since the demo queries all follow a predictable pattern and the extra latency wasn't worth the flexibility.