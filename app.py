"""
Jack and the Beanstalk cartoonifier.

Flow: user uploads a photo + picks cartoon settings + picks a scene
-> ONE call to OpenAI's image edit endpoint -> show the result with the
scene specification as its caption.

The API key is read from the OPENAI_API_KEY environment variable.
It is never written in this file.
"""

import base64
import io
import os

from dotenv import load_dotenv
from flask import Flask, render_template, request
from openai import OpenAI, OpenAIError
from PIL import Image, ImageOps, UnidentifiedImageError

# Optional: lets iPhone HEIC photos open. Safe to skip if not installed.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

load_dotenv()  # locally, loads OPENAI_API_KEY from a .env file (Render uses its own env settings)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB upload cap

# Cheap defaults. Change these in Render's Environment tab, not in code.
MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
QUALITY = os.environ.get("IMAGE_QUALITY", "low")  # low | medium | high

# ---------------------------------------------------------------------------
# The two scenes. The "spec" text is sent in the prompt AND used as the caption,
# so the caption is exactly the scene specification that was sent.
# ---------------------------------------------------------------------------
SCENES = {
    "planting": {
        "label": "1. Jack is planting the seeds",
        "spec": (
            "Jack is planting the seeds: he kneels in the freshly dug soil of a "
            "small garden beside a thatched-roof cottage, pressing a handful of "
            "magic beans into the ground with his hands."
        ),
    },
    "climbing": {
        "label": "2. Jack is climbing the beanstalk",
        "spec": (
            "Jack is climbing the beanstalk: he grips an enormous, twisting green "
            "beanstalk with both hands and feet, partway up, surrounded by giant "
            "leaves, with his tiny cottage far below and clouds above him."
        ),
    },
    "chocolate": {
        "label": "3. Charlie is covering his face with chocolate",
        "spec": (
            "Charlie is covering his face with chocolate: he is sitting at a table, "
            "surrounded by a pile of chocolate bars, with his face hidden behind the "
            "treats."
        ),
    },
}

# ---------------------------------------------------------------------------
# User-adjustable cartoon settings -> prompt phrases.
# Only keys from these dicts are accepted, so users can't inject prompt text.
# ---------------------------------------------------------------------------
STYLES = {
    "classic": "classic hand-drawn 2D storybook cartoon",
    "3d": "polished 3D animated-movie character",
    "comic": "bold comic-book illustration",
    "anime": "soft anime illustration",
}
LINES = {
    "thin": "thin, delicate outlines",
    "medium": "medium-weight clean outlines",
    "bold": "thick, bold outlines",
}
PALETTES = {
    "vibrant": "bright, saturated colors",
    "pastel": "soft pastel colors",
    "muted": "muted, earthy colors",
}
EXAGGERATION = {
    "subtle": "Keep body and face proportions close to realistic, with only light stylization.",
    "medium": "Use classic cartoon proportions: a slightly larger head and eyes.",
    "strong": "Use big-head, highly exaggerated cartoon proportions, but the face must still clearly read as this person.",
}

DEFAULTS = {"style": "classic", "lines": "medium", "palette": "vibrant", "exaggeration": "medium", "scene": "planting"}


def build_prompt(settings: dict) -> str:
    scene = SCENES[settings["scene"]]["spec"]
    return f"""Turn the person in the attached photo into a {STYLES[settings['style']]} and place them in a storybook illustration from the fairy tale "Jack and the Beanstalk". This person is Jack.

IDENTITY (most important): The cartoon must be instantly recognizable as this exact person. Preserve their face shape, eye shape and color, eyebrows, nose, mouth, smile, skin tone, hairstyle, hair color and length, facial hair, glasses, and any distinctive marks. Stylize, but do not change who they are, their apparent age, or their ethnicity. {EXAGGERATION[settings['exaggeration']]}

STYLE: {STYLES[settings['style']]}, {LINES[settings['lines']]}, {PALETTES[settings['palette']]}. Dress Jack in simple fairy-tale peasant clothes.

SCENE (must be depicted exactly): {scene}

Keep Jack's face clearly visible, turned mostly toward the viewer, and large enough to recognize. Do not put any text, captions, or speech bubbles in the image."""


def prepare_photo(raw: bytes) -> bytes:
    """Fix phone rotation, shrink to max 1024px, re-encode as JPEG (cheaper input)."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1024, 1024))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def read_settings(form) -> dict:
    settings = {}
    for key, options in [("style", STYLES), ("lines", LINES), ("palette", PALETTES),
                         ("exaggeration", EXAGGERATION), ("scene", SCENES)]:
        value = form.get(key, DEFAULTS[key])
        settings[key] = value if value in options else DEFAULTS[key]
    return settings


def render_page(**kwargs):
    return render_template(
        "index.html",
        scenes=SCENES, styles=STYLES, lines=LINES, palettes=PALETTES,
        exaggeration=EXAGGERATION, model=MODEL, quality=QUALITY, **kwargs,
    )


@app.get("/")
def index():
    return render_page(settings=DEFAULTS)


@app.post("/generate")
def generate():
    settings = read_settings(request.form)

    # Use a newly uploaded photo, or reuse the one from the previous run
    # (so you can make scene 2 with the same person without re-uploading).
    upload = request.files.get("photo")
    try:
        if upload and upload.filename:
            photo = prepare_photo(upload.read())
        elif request.form.get("photo_b64"):
            photo = base64.b64decode(request.form["photo_b64"])
        else:
            return render_page(settings=settings, error="Please upload a photo first.")
    except (UnidentifiedImageError, ValueError):
        return render_page(settings=settings, error="That file isn't an image I can read. Try a JPG or PNG.")

    photo_b64 = base64.b64encode(photo).decode()

    if not os.environ.get("OPENAI_API_KEY"):
        return render_page(settings=settings, photo_b64=photo_b64,
                           error="Server is missing OPENAI_API_KEY. Set it in your .env (local) or Render's Environment tab.")

    # ---- The single API call. No loops, no automatic retries. ----
    try:
        client = OpenAI()  # reads OPENAI_API_KEY from the environment
        result = client.images.edit(
            model=MODEL,
            image=("photo.jpg", photo, "image/jpeg"),
            prompt=build_prompt(settings),
            size="1024x1024",
            quality=QUALITY,
        )
        output_b64 = result.data[0].b64_json
    except OpenAIError as e:
        return render_page(settings=settings, photo_b64=photo_b64, error=f"OpenAI error: {e}")

    return render_page(
        settings=settings,
        photo_b64=photo_b64,
        output_b64=output_b64,
        caption=SCENES[settings["scene"]]["spec"],
    )


@app.errorhandler(413)
def too_large(_):
    return render_page(settings=DEFAULTS, error="That photo is too big (15 MB max)."), 413


if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
