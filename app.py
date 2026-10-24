import os
from botocore.config import Config
import re
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for, Response, make_response
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from psycopg2 import connect
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
SITE_NAME = os.getenv("SITE_NAME", "DogGirl")
PAGE_SIZE = 12

# Do not publish explicit animal sexual content or titles about minors.
BLOCKED = re.compile(
    r"\b(sex|sexual|xxx|porn|bestiality|zoophil|fuck|nude|naked|18\+|teen|teenage|underage)\b",
    re.I,
)

def clean_title(raw):
    s = re.sub(r"\s*(?:[-|–]\s*)?(?:YouTube|Dailymotion Video|Facebook|Shutterstock|Vecteezy)\s*$", "", raw or "", flags=re.I)
    s = re.sub(r"\s*\|.*$", "", s).strip(" -|.")
    lower = s.lower()
    if not s or lower in ("youtube", "video", "girl dog videos"):
        return "A Dog and Owner Share a Sweet Moment"
    if "special food" in lower or "spacial food" in lower:
        return "Girl Treats Her Dogs to a Special Meal"
    if "annoy your dog" in lower:
        return "Funny Signs Your Dog Really Loves You"
    if "kissing my dog" in lower:
        return "A Playful Dog Gets Lots of Affection"
    if "group of dogs" in lower:
        return "Girl Enjoys Playtime With a Group of Dogs"
    if "training dogs" in lower:
        return "Fun Dog Training Moments Outdoors"
    if "playing with dog" in lower or "plays with her pet dog" in lower:
        return "Girl Shares a Playful Moment With Her Dog"
    if "petting a dog" in lower:
        return "A Peaceful Moment Petting a Family Dog"
    if "dog love" in lower:
        return "The Special Bond Between a Girl and Her Dog"
    if "german shepherd" in lower:
        return "Young Woman and German Shepherd Relax at Home"
    s = re.sub(r"\s+", " ", s).strip()
    return s[:87].rstrip() + ("…" if len(s) > 87 else "")

def category(title):
    t = title.lower()
    if any(w in t for w in ("training", "smart", "trick")):
        return "Training"
    if any(w in t for w in ("food", "meal", "treat", "eat")):
        return "Pet Care"
    if any(w in t for w in ("funny", "laugh", "prank", "annoy")):
        return "Funny Moments"
    return "Dog & Owner"

def get_images():
    url = os.getenv("DATABASE_URL")
    if not url:
        return [], "DATABASE_URL is not configured."
    try:
        with connect(url, connect_timeout=6, sslmode="require") as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, object_key, title, source_url, width, height, created_at
                    FROM public.saved_images
                    WHERE object_key IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 500
                """)
                rows = cur.fetchall()
    except Exception:
        app.logger.exception("Unable to load saved_images")
        return [], "The gallery is temporarily unavailable."
    items = []
    for row in rows:
        raw = row["title"] or ""
        if BLOCKED.search(raw):
            continue
        title = clean_title(raw)
        items.append({
            "iso_date": row["created_at"].isoformat() if row["created_at"] else None,
            "id": str(row["id"]), "title": title,
            "category": category(title),
            "width": row["width"], "height": row["height"],
            "date": row["created_at"].strftime("%b %d, %Y") if row["created_at"] else "",
        })
    return items, None

@app.context_processor
def globals_for_templates():
    return {"site_name": SITE_NAME}

@app.get("/")
def index():
    images, error = get_images()
    search = request.args.get("q", "").strip()[:100]
    selected = request.args.get("category", "All")
    if search:
        images = [x for x in images if search.casefold() in x["title"].casefold()]
    if selected != "All":
        images = [x for x in images if x["category"] == selected]
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    total_pages = max(1, (len(images) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    visible = images[(page-1)*PAGE_SIZE:page*PAGE_SIZE]
    structured = {
        "@context": "https://schema.org", "@type": "CollectionPage",
        "name": "DogGirl - Dog and Owner Photo Stories",
        "url": url_for("index", _external=True),
        "mainEntity": {"@type": "ItemList", "itemListElement": [
            {"@type": "ListItem", "position": i+1+(page-1)*PAGE_SIZE,
             "url": url_for("watch", item_id=x["id"], _external=True),
             "name": x["title"], "image": url_for("image", item_id=x["id"], _external=True)}
            for i, x in enumerate(visible)
        ]}
    }
    return render_template("index.html", images=visible, structured=structured,
        page=page, total_pages=total_pages, search=search, selected=selected,
        count=len(images), error=error, categories=["All", "Dog & Owner", "Funny Moments", "Training", "Pet Care"])

@app.get("/watch/<uuid:item_id>")
def watch(item_id):
    images, error = get_images()
    item = next((x for x in images if x["id"] == str(item_id)), None)
    if not item:
        abort(404)
    structured = {
        "@context": "https://schema.org", "@type": "ImageObject",
        "name": item["title"], "description": item["title"],
        "contentUrl": url_for("image", item_id=item["id"], _external=True),
        "url": url_for("watch", item_id=item["id"], _external=True),
        "width": item["width"], "height": item["height"]
    }
    if item["iso_date"]:
        structured["datePublished"] = item["iso_date"]
    return render_template("watch.html", item=item, error=error, structured=structured)

@app.get("/image/<uuid:item_id>")
def image(item_id):
    # The Neon Storage photos bucket is private. With S3 credentials, issue
    # a short-lived read URL server-side; otherwise use the original image source.
    url = os.getenv("DATABASE_URL")
    if not url:
        abort(404)
    try:
        with connect(url, connect_timeout=6, sslmode="require") as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT object_key, source_url, title FROM public.saved_images WHERE id=%s", (str(item_id),))
                row = cur.fetchone()
        if not row or BLOCKED.search(row["title"] or ""):
            abort(404)
        endpoint = os.getenv("AWS_ENDPOINT_URL_S3")
        key = os.getenv("AWS_ACCESS_KEY_ID")
        secret = os.getenv("AWS_SECRET_ACCESS_KEY")
        bucket = os.getenv("STORAGE_BUCKET", "photos")
        if endpoint and key and secret:
            import boto3
            client = boto3.client("s3", endpoint_url=endpoint,
                aws_access_key_id=key, aws_secret_access_key=secret,
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
            signed = client.generate_presigned_url(
                "get_object", Params={"Bucket": bucket, "Key": row["object_key"]},
                ExpiresIn=900)
            response = redirect(signed, code=302)
            response.headers["Cache-Control"] = "private, no-store"
            return response
        original = row["source_url"] or ""
        parsed = urlparse(original)
        if parsed.scheme == "https" and parsed.hostname in ("encrypted-tbn0.gstatic.com", "images.unsplash.com"):
            return redirect(original, code=302)
    except Exception:
        app.logger.exception("Image delivery failed")
    abort(404)

@app.get("/robots.txt")
def robots():
    return Response("User-agent: *\nAllow: /\nSitemap: " + url_for("sitemap", _external=True) + "\n", mimetype="text/plain")

@app.get("/sitemap.xml")
def sitemap():
    images, _ = get_images()
    from xml.sax.saxutils import escape
    urls = [url_for("index", _external=True)] + [
        url_for("watch", item_id=x["id"], _external=True) for x in images
    ]
    content = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(
        "<url><loc>" + escape(u) + "</loc></url>" for u in urls
    ) + "</urlset>"
    return Response(content, mimetype="application/xml")


# These routes enforce consent on the server, not only through CSS.
# No video database is connected: reviewed, lawful content is a prerequisite.
RESTRICTED_COOKIE = "dg_restricted_consent"
RESTRICTED_MAX_AGE = 1800

def consent_serializer():
    secret = os.getenv("RESTRICTED_SESSION_SECRET")
    if not secret or len(secret) < 32:
        return None
    return URLSafeTimedSerializer(secret, salt="doggirl-restricted-v1")

def has_restricted_consent():
    signer = consent_serializer()
    if not signer:
        return False
    try:
        return signer.loads(request.cookies.get(RESTRICTED_COOKIE, ""), max_age=RESTRICTED_MAX_AGE) == "adult-acknowledged"
    except (BadSignature, SignatureExpired):
        return False

def private_response(response):
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, noimageindex"
    response.headers["Vary"] = "Cookie"
    return response

def same_origin_post():
    # Require an Origin header matching the configured public site origin.
    # A missing Origin is rejected rather than silently trusted.
    origin = request.headers.get("Origin", "").rstrip("/")
    expected = os.getenv("PUBLIC_SITE_ORIGIN", "").rstrip("/")
    return bool(expected and origin == expected and request.headers.get("Sec-Fetch-Site","same-origin") in ("same-origin","none"))

@app.post("/api/restricted/consent")
def grant_restricted_consent():
    if not same_origin_post():
        return private_response(jsonify(error="Origin not allowed")), 403
    signer = consent_serializer()
    if not signer:
        return private_response(jsonify(error="Restricted section is not configured")), 503
    if not request.is_json or request.get_json(silent=True) != {"adult": True}:
        return private_response(jsonify(error="Explicit acknowledgement required")), 400
    resp = private_response(jsonify(allowed=True))
    resp.set_cookie(RESTRICTED_COOKIE, signer.dumps("adult-acknowledged"),
        max_age=RESTRICTED_MAX_AGE, secure=True, httponly=True, samesite="Strict", path="/api/restricted")
    return resp

@app.post("/api/restricted/revoke")
def revoke_restricted_consent():
    if not same_origin_post():
        return private_response(jsonify(error="Origin not allowed")), 403
    resp = private_response(jsonify(allowed=False))
    resp.delete_cookie(RESTRICTED_COOKIE, path="/api/restricted", secure=True, httponly=True, samesite="Strict")
    return resp

@app.get("/api/restricted/items")
def restricted_items():
    if not has_restricted_consent():
        return private_response(jsonify(error="Consent required")), 403
    # Deliberately empty until a properly reviewed collection is available.
    return private_response(jsonify(items=[], message="No reviewed items available"))

@app.get("/health")
def health():
    return jsonify(status="ok", service="doggirl")

if __name__ == "__main__":
    app.run(debug=True)
