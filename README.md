# Campus Current

A UNC marketplace where you describe what you need in plain words, and it finds someone on campus who already has it. Buy it, borrow it, or book help, then meet up on campus.

**Live site:** https://hack-nc.onrender.com
**Demo video:** [add link]

Built at HackNC 2026.

## What it does

- **Ask in plain language.** Type something like "Need to borrow a TI-84 for my final next Thursday, under $10." Gemini turns it into structured details you can check and edit before searching.
- **Search with a photo.** Upload an optional reference photo, and Gemini suggests the category, type, color, and style. The photo isn't stored.
- **Real matches with reasons.** Results come from real listings, with reasons each one fits and anything that still needs confirming. Listings that don't fit are ruled out.
- **Buy, borrow, or book a service.** Items can be for sale, for loan, or both. People can also offer services like tutoring.
- **Agree on terms.** A private exchange with messages and an offer card for price, deposit, and pickup. The lender can choose a lower deposit and sees exactly how much isn't covered. Any change to the terms means both people accept again.
- **Pickup, return, and reviews.** Condition photos at handoff and return, then structured reviews.
- **Post a request.** If nothing matches, publish what you need so someone can list it.
- **Real impact counts.** The home page counts completed loans and sales, plus optional answers about where items would have ended up otherwise.


## How we built it

- **Backend:** Python, Flask, SQLAlchemy, Flask-Migrate, Pydantic
- **Frontend:** Jinja templates, hand-written CSS, vanilla JavaScript, in a Frutiger Aero style
- **AI:** Gemini 3.5 Flash-Lite through the google-genai SDK, with structured output validated by Pydantic and a fallback to larger Gemini models when the API is busy
- **Data:** SQLite locally, Supabase (PostgreSQL, Auth, Storage) in production
- **Hosting:** Render

Gemini reads requests and photos, but regular Python code checks the hard rules (mode, dates, budget, deposit, availability), so the AI can't invent listings or force a bad match.

## Run it locally

```bash
git clone https://github.com/evanrm312/hack-nc.git
cd hack-nc
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt
cp .env.example .env            # then add your Gemini API key
flask db upgrade
flask seed-demo
flask run --debug
```

Open http://127.0.0.1:5000. For local development, keep `APP_ENV=development` in `.env`.

## Demo accounts

Go to `/sign-in` and pick a sandbox user (Alice, Bob, or Carol). These are demo accounts and are labeled as not verified.

## Tests

```bash
pytest
```

## Limitations

- Payments and deposits are **simulated**. No real money is held or charged.
- Sandbox sign-in is for the demo. Real use would require a verified @unc.edu email.
- The site includes labeled demo listings and fictional profiles so it isn't empty.
- The savings widget on the About page is an illustration, not real data.
- Price data is limited, and suggested meeting spots don't guarantee safety.

## Team

- **Evan:** backend, database, auth, deployment
- **Aarush:** Gemini integration and matching
- **Emily:** UI, Frutiger Aero design, marketplace pages
- **Sid:** exchanges, offers, reviews, demo testing

We used AI coding assistants (Claude Code and Codex) to help write and test code. We planned the app, split the work, and reviewed and tested everything ourselves.