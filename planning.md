# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset (`data/listings.json`) for items that match the user's description, optional size, and optional price ceiling. Returns a ranked list of matching listing dicts, best match first.

**Input parameters:**
- `description` (str): Keywords describing what the user is looking for (e.g., "vintage graphic tee"). Used to score each listing by keyword overlap against `title`, `description`, and `style_tags`.
- `size` (str | None): Size string to filter by (e.g., `"M"`, `"W30"`), or `None` to skip size filtering. Matching is case-insensitive and substring-based (e.g., `"M"` matches `"S/M"` and `"XL (fits oversized M)"`).
- `max_price` (float | None): Maximum price in dollars, inclusive (e.g., `30.0`). Listings with `price > max_price` are excluded. Pass `None` to skip price filtering.

**What it returns:**
A `list[dict]`, where each dict is a full listing record from `listings.json` with these fields:
- `id` (str): Unique listing identifier, e.g. `"lst_006"`
- `title` (str): Human-readable item name, e.g. `"Graphic Tee — 2003 Tour Bootleg Style"`
- `description` (str): Seller's description of the item
- `category` (str): One of `tops`, `bottoms`, `outerwear`, `shoes`, `accessories`
- `style_tags` (list[str]): Style descriptors, e.g. `["vintage", "grunge", "graphic tee"]`
- `size` (str): Size as listed, e.g. `"L"`, `"S/M"`, `"W30"`
- `condition` (str): One of `excellent`, `good`, `fair`
- `price` (float): Listing price in dollars
- `colors` (list[str]): Colors present in the item, e.g. `["black"]`
- `brand` (str | None): Brand name, or `null` if unbranded
- `platform` (str): Where it's listed — one of `depop`, `poshmark`, `thredUp`

Returns an empty list `[]` if nothing matches — never raises an exception.

**What happens if it fails or returns nothing:**
The agent sets `session["error"]` to a message explaining what was searched and suggesting adjustments: `"No listings found for '[description]' in size [size] under $[max_price]. Try removing the size filter, increasing your budget, or using broader keywords."` The agent then returns early — it does NOT call `suggest_outfit` or `create_fit_card` with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted listing the user is considering and their current wardrobe, calls the Groq LLM to suggest 1–2 complete outfit combinations that incorporate the new item alongside pieces the user already owns.

**Input parameters:**
- `new_item` (dict): A full listing dict from `search_listings` (same fields as above — `title`, `category`, `style_tags`, `colors`, `price`, `platform`, etc.).
- `wardrobe` (dict): A wardrobe dict with a single key `"items"` containing a list of wardrobe item dicts. Each wardrobe item has: `id` (str), `name` (str), `category` (str), `colors` (list[str]), `style_tags` (list[str]), `notes` (str | None). May be an empty list — handle gracefully.

**What it returns:**
A non-empty `str` containing 1–2 outfit suggestions. If the wardrobe has items, each suggestion names specific pieces from the wardrobe by name and explains how they work together. If the wardrobe is empty, the string contains general styling advice for the new item (what silhouettes, colors, or vibes pair well with it) rather than referencing specific owned pieces.

Example return (non-empty wardrobe): `"Outfit 1: Pair the faded band tee with your baggy straight-leg jeans and chunky white sneakers — tuck the front corner for shape. Outfit 2: Layer it under your vintage black denim jacket with black combat boots for a grungier take."`

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool does NOT crash — it prompts the LLM for general styling advice instead. If the LLM call fails (API error, timeout), the tool returns the string: `"Couldn't generate outfit suggestions right now. The item is a [category] with [style_tags] — try pairing it with pieces in similar colors or vibes."` The agent passes this string to `create_fit_card` as-is so the session can still complete.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM to generate a short, casual, shareable caption (2–4 sentences) for the outfit — the kind of thing someone would post on Instagram or TikTok alongside an OOTD photo.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty — if it is empty or whitespace-only, the tool returns an error string immediately without calling the LLM.
- `new_item` (dict): The listing dict for the thrifted item (same fields as above). Used to pull in `title`, `price`, and `platform` to mention naturally in the caption.

**What it returns:**
A `str` of 2–4 sentences that:
- Sounds like a real OOTD caption (casual, first-person, not a product description)
- Mentions the item name, price, and platform once each, naturally
- Captures the outfit vibe in specific terms (not generic like "cute look")
- Varies each time for different inputs (LLM temperature set to 1.0 or higher)

Example return: `"thrifted this faded band tee off depop for $19 and honestly it was made for my dark wash baggies 🖤 layered the black denim jacket on top and suddenly it's a whole look. full fit in my stories"`

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, returns: `"Couldn't generate a fit card — the outfit description was missing. Try running the full search again."` If the LLM call fails, returns: `"Fit card unavailable right now, but the look: [new_item title] from [platform] for $[price]."` Never raises an exception.

---

### Additional Tools (if any)

None for the base implementation. See stretch features section if added.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs inside `run_agent()` in `agent.py`. It follows this conditional logic:

1. **Parse the query.** Extract `description`, `size`, and `max_price` from the user's natural language input (either via the LLM or simple parsing). Store these in the session.

2. **Call `search_listings`.** Always the first tool called.
   - If `results == []`: set `session["error"] = "No listings found for..."`, set `session["selected_item"] = None`, and **return early** — do not proceed to step 3 or 4.
   - If `len(results) > 0`: set `session["selected_item"] = results[0]` (top match) and continue.

3. **Call `suggest_outfit`.** Only reached if `session["selected_item"]` is not None.
   - Pass `session["selected_item"]` as `new_item` and the wardrobe (from `get_example_wardrobe()` or user-provided) as `wardrobe`.
   - Store the return value in `session["outfit_suggestion"]`.
   - This tool always returns a non-empty string (either real suggestions or a graceful fallback), so the loop always continues to step 4.

4. **Call `create_fit_card`.** Only reached if `session["outfit_suggestion"]` is not None and not empty.
   - Pass `session["outfit_suggestion"]` as `outfit` and `session["selected_item"]` as `new_item`.
   - Store the return value in `session["fit_card"]`.

5. **Return the session.** `app.py` reads `session["selected_item"]`, `session["outfit_suggestion"]`, `session["fit_card"]`, and `session["error"]` to populate the UI panels.

The agent never calls `suggest_outfit` or `create_fit_card` with `None` or empty inputs — each step is gated on the previous step's output.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict initialized at the start of `run_agent()`:

```python
session = {
    "query": str,               # original user input
    "selected_item": None,      # set after search_listings succeeds — full listing dict
    "outfit_suggestion": None,  # set after suggest_outfit runs — string
    "fit_card": None,           # set after create_fit_card runs — string
    "error": None,              # set if any tool hits a failure mode — string
}
```

- `session["selected_item"]` is set from `results[0]` after `search_listings` returns. It is passed directly as the `new_item` argument to both `suggest_outfit` and `create_fit_card` — never re-fetched or re-entered.
- `session["outfit_suggestion"]` is set from the return value of `suggest_outfit`. It is passed directly as the `outfit` argument to `create_fit_card`.
- `session["error"]` is set when `search_listings` returns `[]`, so `app.py` can display a specific error message to the user instead of empty panels.
- The wardrobe is loaded once at the start of the session (via `get_example_wardrobe()`) and passed into `suggest_outfit`. It is not stored in the session dict because it doesn't change within a single run.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query (returns `[]`) | Sets `session["error"]` to `"No listings found for '[description]' in size [size] under $[max_price]. Try broader keywords, removing the size filter, or increasing your budget."` Returns early — `suggest_outfit` and `create_fit_card` are never called. |
| `suggest_outfit` | `wardrobe["items"]` is empty | Calls LLM with a general styling prompt instead of a wardrobe-specific one. Returns general advice like `"This piece has a grunge/streetwear vibe — pair it with wide-leg denim, chunky sneakers, or a vintage jacket."` Never crashes or returns an empty string. |
| `create_fit_card` | `outfit` argument is empty or whitespace-only | Returns the string `"Couldn't generate a fit card — the outfit description was missing. Try running the full search again."` without calling the LLM. |

---

## Architecture

```
User query (natural language)
    │
    ▼
run_agent(query, wardrobe)
    │
    │  1. Parse: description, size, max_price from query
    │
    ├─► search_listings(description, size, max_price)
    │       │
    │       ├── results == []
    │       │       │
    │       │       └──► session["error"] = "No listings found..."
    │       │            session["selected_item"] = None
    │       │            RETURN EARLY ◄─────────────────────────────┐
    │       │                                                        │
    │       └── results = [item, ...]                               │
    │               │                                               │
    │               └──► session["selected_item"] = results[0]      │
    │                       │                                       │
    ├─► suggest_outfit(session["selected_item"], wardrobe)          │
    │       │                                                        │
    │       ├── wardrobe["items"] == []                             │
    │       │       └──► LLM prompt: general styling advice         │
    │       │                                                        │
    │       └── wardrobe["items"] = [...]                           │
    │               └──► LLM prompt: specific outfit combinations   │
    │                       │                                       │
    │               session["outfit_suggestion"] = "<string>"       │
    │                       │                                       │
    ├─► create_fit_card(session["outfit_suggestion"],               │
    │                   session["selected_item"])                   │
    │       │                                                        │
    │       ├── outfit == "" → return error string ────────────────►│
    │       │                                                        │
    │       └── outfit ok → LLM prompt: OOTD caption               │
    │               │                                               │
    │       session["fit_card"] = "<caption string>"               │
    │               │                                               │
    └──────────────►▼                                               │
            return session ◄────────────────────────────────────────┘
                │
                ▼
        app.py: maps session keys to UI output panels
            - Panel 1: session["selected_item"] (title, price, platform, condition)
            - Panel 2: session["outfit_suggestion"]
            - Panel 3: session["fit_card"]
            - Error panel: session["error"] (if set)
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

**`search_listings`:** Give Claude the Tool 1 section of this planning.md (inputs, return value, failure mode, field list) and ask it to implement the function in `tools.py` using `load_listings()` from `utils/data_loader.py`. Specify that scoring should use keyword overlap across `title`, `description`, and `style_tags`, and that size matching should be case-insensitive substring matching. Before running: verify the generated code filters by all three parameters, handles `None` for `size` and `max_price`, drops zero-score results, and returns `[]` (not an exception) when nothing matches. Test with three queries: one that should return results, one with an impossible size+price combo that should return `[]`, and one with no size/price filter.

**`suggest_outfit`:** Give Claude the Tool 2 section of this planning.md plus 2–3 example wardrobe items from `wardrobe_schema.json` and 1 example listing from `listings.json`. Ask it to implement the function with two branches: empty wardrobe → general styling prompt, non-empty wardrobe → specific outfit prompt using named wardrobe pieces. Before running: check that the empty-wardrobe branch is present and doesn't crash, that the LLM is called with `groq` using `llama-3.3-70b-versatile`, and that the function always returns a non-empty string. Test with both `get_example_wardrobe()` and `get_empty_wardrobe()`.

**`create_fit_card`:** Give Claude the Tool 3 section of this planning.md including the example return value and the style requirements (casual, first-person, mentions item/price/platform once, varies with temperature). Ask it to implement the function with the empty-outfit guard and LLM temperature set to 1.0 or above. Before running: check the empty-string guard is the first thing in the function, verify temperature is set high, and confirm the prompt instructs the LLM to write a caption (not a product description). Run it 3 times on the same input and verify the outputs differ.

**Milestone 4 — Planning loop and state management:**

Give Claude the Planning Loop section, State Management section, and the full Architecture diagram from this file. Ask it to implement `run_agent()` in `agent.py` following the numbered conditional steps exactly. Before running: verify the generated code (1) gates each tool call on the previous step's output, (2) stores values in the `session` dict as specified, (3) does NOT call all three tools unconditionally, and (4) returns early when `search_listings` returns `[]`. Test the happy path (valid query) and the error path (impossible query) and print the session dict at the end of each to confirm correct state.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The agent calls `search_listings(description="vintage graphic tee", size=None, max_price=30.0)`.

`load_listings()` returns all 40 listings. The price filter removes listings over $30 (e.g., lst_004 at $45, lst_009 at $55, lst_022 at $75). Each remaining listing is scored by keyword overlap between `"vintage graphic tee"` and its `title`, `description`, and `style_tags`. High scorers include:
- `lst_033` ("Vintage Band Tee — Faded Grey", tags: `["vintage", "grunge", "band tee", "graphic tee", "streetwear"]`, $19) — score: 4 matches
- `lst_006` ("Graphic Tee — 2003 Tour Bootleg Style", tags: `["graphic tee", "vintage", "grunge", "streetwear", "band tee"]`, $24) — score: 4 matches

`results[0]` = `lst_033` (or `lst_006` depending on tie-breaking). `session["selected_item"]` = that listing dict.

**Step 2:**
The agent calls `suggest_outfit(new_item=session["selected_item"], wardrobe=get_example_wardrobe())`.

The wardrobe is non-empty (10 items). The LLM receives a prompt with the new item details (`"Vintage Band Tee — Faded Grey, $19, style tags: vintage/grunge/band tee"`) and the wardrobe items listed by name, category, and style tags. The LLM returns something like:

`"Outfit 1: Tuck the faded band tee into your baggy straight-leg jeans (dark wash) and finish with chunky white sneakers — classic 90s streetwear. Outfit 2: Layer the vintage black denim jacket over the tee, pair with black combat boots, and leave the jeans loose for a grungier look."`

`session["outfit_suggestion"]` = that string.

**Step 3:**
The agent calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`.

`outfit` is non-empty, so no early return. The LLM receives a prompt with the outfit description and item details (`title="Vintage Band Tee — Faded Grey"`, `price=19.0`, `platform="depop"`), instructed to write a casual OOTD caption. Returns something like:

`"found this faded band tee on depop for $19 and it was literally made for my dark wash baggies 🖤 threw the black denim jacket on top and suddenly it's a whole fit. chunky sneakers tie it together — full look in my stories"`

`session["fit_card"]` = that string.

**Final output to user:**
The Gradio UI populates three panels:
- **Found Item:** "Vintage Band Tee — Faded Grey — $19 — depop — Condition: fair"
- **How to Wear It:** "Outfit 1: Tuck the faded band tee into your baggy straight-leg jeans..."
- **Fit Card:** "found this faded band tee on depop for $19 and it was literally made for my dark wash baggies 🖤..."

If instead `search_listings` had returned `[]` (e.g., query was "designer ballgown, size XXS, under $5"), the UI would show only the error panel: "No listings found for 'designer ballgown' in size XXS under $5.00. Try broader keywords, removing the size filter, or increasing your budget." The outfit and fit card panels would be empty.