#!/usr/bin/env python3
"""Builds the Reel Drinks pairing pages under reel-drinks/ from stored film answers.

    python3 _tools/reel_drinks_pages.py            # build from cached answers, fetching any missing
    python3 _tools/reel_drinks_pages.py --refresh  # re-fetch every answer first

Films, lists and the beta link live in _tools/reel-drinks/films.json. Answers come from the drinks
Worker's free `GET /v1/films/{id}/answer` and are cached in _tools/reel-drinks/answers/ so builds are
repeatable. The script never generates an answer (that's a paid model call): pair a new film in the
app first. Recipes come from the app's bundled catalog (../ReelDrinks/ReelDrinks/Resources/catalog.json).
"""

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
DATA = SITE / "_tools" / "reel-drinks"
OUT = SITE / "reel-drinks"
DEFAULT_CATALOG = SITE.parent / "ReelDrinks" / "ReelDrinks" / "Resources" / "catalog.json"
DRINKS_URL = "https://reeldrinks-drinks.jrames.workers.dev"
SITE_URL = "https://www.jefframes.com"
BASE = "/reel-drinks"
LINEUP_SIZE = 5
FRACTIONS = [(0, ""), (0.25, "¼"), (1 / 3, "⅓"), (0.5, "½"), (2 / 3, "⅔"), (0.75, "¾"), (1, "")]
CITRUS = {"lime", "lemon", "orange", "grapefruit"}

e = html.escape


# Data

def slugify(text):
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def fetch_answer(film_id, catalog_version):
    url = f"{DRINKS_URL}/v1/films/{film_id}/answer?catalog={catalog_version}"
    request = urllib.request.Request(url, headers={"User-Agent": "reel-drinks-pages"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def load_answers(films, catalog_version, refresh):
    cache = DATA / "answers"
    cache.mkdir(parents=True, exist_ok=True)
    answers = {}
    for film in films:
        path = cache / f"{film['id']}.json"
        if path.exists() and not refresh:
            answers[film["id"]] = json.loads(path.read_text())
            continue
        answer = fetch_answer(film["id"], catalog_version)
        if answer is None or not answer.get("complete"):
            print(f"skip {film['title']}: no complete stored answer (pair it in the app first)", file=sys.stderr)
            continue
        path.write_text(json.dumps(answer, indent=1, ensure_ascii=False) + "\n")
        answers[film["id"]] = answer
    return answers


def lineup(answer, recipes):
    """The film's drinks as the app's ideal lineup shows them: signatures first, then the model's picks."""
    cuts = {cut["classic"]: cut for cut in answer.get("cuts", [])}
    drinks, seen = [], set()
    for signature in answer.get("signatures", []):
        if signature["id"] in recipes and signature["id"] not in seen:
            seen.add(signature["id"])
            drinks.append({"recipe": recipes[signature["id"]], "name": signature["name"],
                           "blurb": signature.get("sceneNote") or "", "signature": signature})
    for pick in answer.get("picks", []):
        if len(drinks) >= LINEUP_SIZE:
            break
        if pick["id"] in recipes and pick["id"] not in seen:
            seen.add(pick["id"])
            drinks.append({"recipe": recipes[pick["id"]], "name": pick["name"], "blurb": pick["blurb"]})
    for drink in drinks:
        cut = cuts.get(drink["recipe"]["id"])
        if cut and cut["recipe"] in recipes and not any(d in seen for d in cut.get("duplicates", [])):
            drink["cut"] = {**cut, "recipeData": recipes[cut["recipe"]]}
    return drinks


# Formatting (mirrors Model/Formatting.swift in the app)

def fraction(value):
    whole = int(value // 1)
    nearest = min(FRACTIONS, key=lambda option: abs(option[0] - (value - whole)))
    if nearest[0] == 1:
        return str(whole + 1)
    if whole == 0:
        return nearest[1] or "0"
    return f"{whole}{nearest[1]}"


def measure(ingredient):
    unit, amount = ingredient["unit"], ingredient.get("amount")
    if unit == "top":
        return "Top"
    if unit == "rinse":
        return "Rinse"
    if unit == "pinch":
        return f"{fraction(amount)} pinch" if amount else "Pinch"
    if amount is None:
        return ""
    number, plural = fraction(amount), amount > 1
    if unit == "slice" and ingredient["categoryID"] in CITRUS:
        return f"{number} {'wedges' if plural else 'wedge'}"
    words = {"oz": "oz", "barspoon": "barspoon", "tsp": "tsp", "leaves": "leaves",
             "dash": "dashes" if plural else "dash", "drop": "drops" if plural else "drop",
             "slice": "slices" if plural else "slice", "sprig": "sprigs" if plural else "sprig"}
    return f"{number} {words[unit]}" if unit in words else number


def ingredient_name(ingredient, categories):
    """"¾ oz Lime juice" but "4 wedges Limes" (RecipeIngredient.displayName in the app)."""
    category = categories.get(ingredient["categoryID"], {})
    name = category.get("name", ingredient["categoryID"])
    if ingredient["unit"] in {"oz", "tsp", "barspoon", "dash", "drop"}:
        name = category.get("measuredName") or name
    if ingredient.get("note"):
        name += f" ({ingredient['note']})"
    if ingredient.get("isOptional"):
        name += ", optional"
    return name


def glass_label(glass):
    """"Cocktail" → "Cocktail glass"; names that already say what they are ("Tiki mug", "Julep cup") stay."""
    if not glass:
        return ""
    if re.search(r"(glass|mug|cup|flute|balloon)$", glass, re.IGNORECASE):
        return glass
    return f"{glass} glass"


# Pages

def beta_button(beta_url, extra_class=""):
    if beta_url:
        return f'<a class="button {extra_class}" href="{e(beta_url)}">Join the iPhone beta</a>'
    return f'<span class="button soon {extra_class}">iPhone beta opening soon</span>'


def page(title, description, path, body, json_ld=None):
    canonical = f"{SITE_URL}{path}"
    ld = f'\n  <script type="application/ld+json">{json.dumps(json_ld, ensure_ascii=False)}</script>' if json_ld else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{e(title)}</title>
  <meta name="description" content="{e(description)}" />
  <link rel="canonical" href="{canonical}" />
  <link rel="icon" href="{BASE}/assets/app-icon.png" />
  <link rel="stylesheet" href="{BASE}/assets/site.css" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Reel Drinks" />
  <meta property="og:title" content="{e(title)}" />
  <meta property="og:description" content="{e(description)}" />
  <meta property="og:url" content="{canonical}" />
  <meta property="og:image" content="{SITE_URL}{BASE}/assets/app-icon.png" />
  <meta name="twitter:card" content="summary" />
  <script data-goatcounter="https://jefframes.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>{ld}
</head>
<body>
  <nav class="nav">
    <div class="wrap nav-inner">
      <a class="brand" href="{BASE}/"><img src="{BASE}/assets/app-icon.png" alt="" />Reel Drinks</a>
      <a class="nav-link" href="{BASE}/christmas-movie-cocktails/">Christmas movies</a>
    </div>
  </nav>
{body}
  <footer class="wrap">
    <span>© 2026 Reel Drinks · Made by <a href="/">Jeff Rames</a> · For adults of legal drinking age. Please drink responsibly.</span>
    <a href="{BASE}/privacy/">Privacy</a>
  </footer>
</body>
</html>
"""


def cta(beta_url, heading="What can you make tonight?"):
    return f"""    <section class="cta">
      <h2>{e(heading)}</h2>
      <p>Reel Drinks pairs any movie with real cocktails, then checks your own bottles: what you can make tonight, what's one bottle away, and the bottle that would unlock the most drinks.</p>
      {beta_button(beta_url)}
    </section>"""


def recipe_block(recipe, categories):
    items = "".join(f'<li><span class="amt">{e(measure(i))}</span> {e(ingredient_name(i, categories))}</li>'
                    for i in recipe["ingredients"])
    steps = "".join(f"<li>{e(step)}</li>" for step in recipe["steps"])
    return f"""<div class="recipe">
          <div><h4>Ingredients</h4><ul class="ingredients">{items}</ul></div>
          <div><h4>Method</h4><ol class="steps">{steps}</ol></div>
        </div>"""


def recipe_ld(drink, film, categories):
    recipe = drink["recipe"]
    return {
        "@type": "Recipe",
        "name": f"{drink['name']} ({recipe['name']})",
        "description": drink["blurb"] or f"A {recipe['name']} to drink with {film['title']}.",
        "recipeCategory": "Cocktail",
        "keywords": f"{film['title']} cocktail, {recipe['name']}, movie night drinks",
        "recipeIngredient": [f"{measure(i)} {ingredient_name(i, categories)}".strip() for i in recipe["ingredients"]],
        "recipeInstructions": [{"@type": "HowToStep", "text": step} for step in recipe["steps"]],
        "author": {"@type": "Organization", "name": "Reel Drinks"},
    }


def film_page(film, drinks, answer, lists, films_by_id, picks_by_film, categories, beta_url):
    cards = []
    for index, drink in enumerate(drinks):
        recipe = drink["recipe"]
        meta = " · ".join(part for part in [recipe["name"], glass_label(recipe.get("glass"))] if part)
        tag = '<span class="tag">On screen</span>' if drink.get("signature") else ""
        garnish = f'<p class="garnish"><strong>Garnish:</strong> {e(recipe["garnish"])}</p>' if recipe.get("garnish") else ""
        cut = ""
        if "cut" in drink:
            c = drink["cut"]
            cut = f"""
        <div class="cut">
          <p class="eyebrow">Director's Cut</p>
          <h4>{e(c['name'])} <span class="muted">· {e(c['recipeData']['name'])}</span></h4>
          <p>{e(c['note'])} {e(c['how'])}</p>
          {recipe_block(c['recipeData'], categories)}
        </div>"""
        cards.append(f"""      <details class="drink"{' open' if index == 0 else ''}>
        <summary>
          <span class="num">{index + 1:02d}</span>
          <span class="title"><span class="name">{e(drink['name'])}</span>{tag}<span class="meta">{e(meta)}</span>
          <span class="blurb">{e(drink['blurb'])}</span></span>
        </summary>
        {recipe_block(recipe, categories)}
        {garnish}{cut}
      </details>""")

    reasons = "".join(f"<li>{e(reason)}</li>" for reason in answer.get("reasons", [])[:4])
    more = []
    for film_list in lists:
        if film["id"] not in film_list["films"]:
            continue
        others = [films_by_id[i] for i in film_list["films"] if i != film["id"] and i in picks_by_film][:6]
        links = "".join(f'<li><a href="{BASE}/pairings/{o["slug"]}/">{e(o["title"])}</a></li>' for o in others)
        more.append(f"""    <section class="more">
      <h2>More from <a href="{BASE}/{film_list['slug']}/">{e(film_list['title'])}</a></h2>
      <ul class="more-list">{links}</ul>
    </section>""")

    top = drinks[0]
    title = f"What to Drink with {film['title']} ({film['year']}): Cocktail Pairings | Reel Drinks"
    description = (f"Cocktails to drink with {film['title']} ({film['year']}), led by the {top['name']}, "
                   f"a {top['recipe']['name']}. Real recipes with ingredients and steps.")
    body = f"""  <main class="shell">
    <header class="hero">
      <p class="eyebrow">Now pairing</p>
      <h1>{e(film['title'])} <span class="year">{film['year']}</span></h1>
      <p class="lede">{len(drinks)} real cocktails to drink with {e(film['title'])}, each one matched to the film.</p>
      <ul class="reasons">{reasons}</ul>
    </header>
    <section class="lineup">
{chr(10).join(cards)}
    </section>
{cta(beta_url)}
{chr(10).join(more)}
  </main>"""
    json_ld = {"@context": "https://schema.org", "@graph": [recipe_ld(d, film, categories) for d in drinks]}
    return page(title, description, f"{BASE}/pairings/{film['slug']}/", body, json_ld)


def film_card(film, drink, show_blurb=False):
    blurb = f'<span class="card-blurb">{e(drink["blurb"])}</span>' if show_blurb else ""
    return f"""      <a class="card" href="{BASE}/pairings/{film['slug']}/">
        <span class="card-film">{e(film['title'])} <span class="year">{film['year']}</span></span>
        <span class="card-drink">{e(drink['name'])}</span>
        <span class="card-recipe">{e(drink['recipe']['name'])}</span>
        {blurb}
      </a>"""


def varied(films, picks_by_film):
    """Same-mood films often share a top pick (six Christmas films lead with Mulled Claret), so a grid of
    films shows each one's best drink the grid hasn't used yet. Each film's own page keeps its full lineup."""
    used, chosen = set(), []
    for film in films:
        drinks = picks_by_film[film["id"]]
        drink = next((d for d in drinks if d["recipe"]["id"] not in used), drinks[0])
        used.add(drink["recipe"]["id"])
        chosen.append((film, drink))
    return chosen


def list_page(film_list, films_by_id, picks_by_film, beta_url):
    films = [films_by_id[i] for i in film_list["films"] if i in picks_by_film]
    cards = "\n".join(film_card(f, d, show_blurb=True) for f, d in varied(films, picks_by_film))
    body = f"""  <main class="shell">
    <header class="hero">
      <p class="eyebrow">Staff picks</p>
      <h1>{e(film_list['title'])}</h1>
      <p class="lede">{e(film_list['intro'])}</p>
    </header>
    <section class="grid">
{cards}
    </section>
{cta(beta_url, "Pair any movie with what's on your shelf")}
  </main>"""
    json_ld = {"@context": "https://schema.org", "@type": "ItemList", "name": film_list["title"],
               "itemListElement": [{"@type": "ListItem", "position": n + 1, "url": f"{SITE_URL}{BASE}/pairings/{f['slug']}/"}
                                   for n, f in enumerate(films)]}
    return page(f"{film_list['title']}: A Drink for Every Film | Reel Drinks",
                film_list["description"], f"{BASE}/{film_list['slug']}/", body, json_ld)


def landing_page(films, lists, picks_by_film, beta_url):
    featured = [f for f in films if f["id"] in picks_by_film][:9]
    cards = "\n".join(film_card(f, d) for f, d in varied(featured, picks_by_film))
    list_links = "".join(f'<a class="button ghost" href="{BASE}/{l["slug"]}/">{e(l["title"])} →</a>' for l in lists)
    body = f"""  <main class="shell">
    <header class="hero landing">
      <img class="hero-icon" src="{BASE}/assets/app-icon.png" alt="Reel Drinks app icon" />
      <p class="eyebrow">Now showing on iPhone</p>
      <h1>Real cocktails for the movie you're watching tonight.</h1>
      <p class="lede">Pick a film and Reel Drinks pours a lineup of drinks that suit its mood, era, setting and colors. Every one is a tested recipe, never an invented one.</p>
      <div class="actions">{beta_button(beta_url)}{list_links}</div>
    </header>
    <section class="how">
      <div><span class="num">01</span><h3>Pick a film</h3><p>Search any movie or browse new releases.</p></div>
      <div><span class="num">02</span><h3>Get the lineup</h3><p>Drinks matched to the film, each with a name and a note on why it fits.</p></div>
      <div><span class="num">03</span><h3>Check your bar</h3><p>See what you can make tonight and the one bottle that unlocks the most.</p></div>
    </section>
    <h2 class="section-title">Tonight's pairings</h2>
    <section class="grid">
{cards}
    </section>
  </main>"""
    return page("Reel Drinks: Cocktail Pairings for Any Movie",
                "Reel Drinks pairs movies with real, tested cocktail recipes, then shows what you can make with the bottles you have.",
                f"{BASE}/", body)


def sitemap(paths):
    urls = "".join(f"  <url><loc>{SITE_URL}{p}</loc></url>\n" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>\n'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="re-fetch every stored answer")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()

    config = json.loads((DATA / "films.json").read_text())
    catalog = json.loads(args.catalog.read_text())
    recipes = {r["id"]: r for r in catalog["recipes"]}
    categories = {c["id"]: c for c in catalog["categories"]}
    films, lists, beta_url = config["films"], config.get("lists", []), config.get("betaURL", "")
    for film in films:
        film.setdefault("slug", slugify(film["title"]))
    films_by_id = {f["id"]: f for f in films}

    answers = load_answers(films, catalog["version"], args.refresh)
    picks_by_film = {}
    for film in films:
        if film["id"] in answers:
            drinks = lineup(answers[film["id"]], recipes)
            if drinks:
                picks_by_film[film["id"]] = drinks

    paths = [f"{BASE}/"]
    for film in films:
        if film["id"] not in picks_by_film:
            continue
        write(OUT / "pairings" / film["slug"] / "index.html",
              film_page(film, picks_by_film[film["id"]], answers[film["id"]], lists, films_by_id, picks_by_film, categories, beta_url))
        paths.append(f"{BASE}/pairings/{film['slug']}/")
    for film_list in lists:
        write(OUT / film_list["slug"] / "index.html", list_page(film_list, films_by_id, picks_by_film, beta_url))
        paths.append(f"{BASE}/{film_list['slug']}/")
    write(OUT / "index.html", landing_page(films, lists, picks_by_film, beta_url))
    write(OUT / "sitemap.xml", sitemap(paths))
    print(f"Built {len(picks_by_film)} film pages, {len(lists)} lists, landing page and sitemap in {OUT}")


if __name__ == "__main__":
    main()
