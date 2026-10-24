# DogGirl — Flask gallery

DogGirl is a responsive, three-column desktop gallery backed by Neon's `public.saved_images` table and the private `photos` storage bucket.

## Quick start

```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://..."
python app.py
```

## Deploy on Vercel

Import this repository to Vercel. Set `DATABASE_URL` in the project environment and deploy. A preconfigured `vercel.json` is included.

### Private Neon image storage

The private `photos` bucket **cannot be accessed with object keys alone**. The `/image/<uuid>` route signs short-lived S3 download URLs when all the variables below are available in Vercel:

- `AWS_ENDPOINT_URL_S3` — your Neon Storage S3 endpoint
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `STORAGE_BUCKET=photos`
- `AWS_REGION` (optional, defaults to `auto`)

Until configured, the route falls back to the original `source_url` for supported Google thumbnail hosts. These cached URLs may be temporary; S3 signing is recommended for reliable production image delivery. Do not expose S3 credentials to JavaScript or commit them.

## Pages

- `/`: cards, category filters, keyword search, pagination, and an inactive partner-feed placeholder.
- `/watch/<uuid>`: lightweight item page, no video player yet.
- `/image/<uuid>`: image resolution from Neon Storage or safe cached source.
- `/health`: simple uptime response.

## Content handling

The originals in `saved_images` remain unchanged. The website rewrites titles in-memory, removes copied source suffixes, and excludes entries with explicit animal-sexual references or references to minors. Please independently review image content, permissions and usage rights before public release. Thumbnails are not a substitute for uploaded/licensed videos.

To enable the future partner-feed area, replace the static `future` section in `templates/index.html` with a server-side feed and separate permissions/validation.
