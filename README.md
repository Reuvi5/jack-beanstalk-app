# Cartoon Me: Jack and the Beanstalk

Upload a photo → cartoonify it with adjustable settings → place the cartoon person in a
Jack and the Beanstalk scene → caption the image with the exact scene specification sent.

Live URL: _(paste your Render URL here)_

## Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then put your real key in .env
python app.py                     # open http://localhost:5000
```

## Deploy (Render)

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app --timeout 180`
- Environment: `OPENAI_API_KEY` (and optionally `IMAGE_MODEL`, `IMAGE_QUALITY`)

## Settings the user can change

Cartoon style · outline weight · color palette · exaggeration · scene

## Production test log

Pass = a person who knows the subject would recognize them (identity), and the picture
shows what the caption says (scene).

| # | Photo (describe, don't name) | Settings | Scene | Looks like them? | Matches caption? | Notes / prompt change |
|---|---|---|---|---|---|---|
| 1 | me, glasses, short dark hair | classic / medium | planting | | | |
| 2 | me | classic / medium | climbing | | | |
| 3 | friend A | | planting | | | |
| 4 | friend A | | climbing | | | |
| 5 | friend B | | planting | | | |
| 6 | friend B | | climbing | | | |

## Prompt iterations

- v1: _(what failed, what you changed)_
