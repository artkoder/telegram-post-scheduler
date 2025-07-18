#!/usr/bin/env python3
"""Upload a photo post to a VK group using a group token."""

import json
import os
import subprocess
import sys

try:
    import requests
except ImportError:  # pragma: no cover - ensure requests present
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

VK_GROUP_ID = os.getenv("VK_GROUP_ID")
VK_TOKEN = os.getenv("VK_TOKEN")
PHOTO_PATH = os.getenv("PHOTO_PATH")
API = "https://api.vk.com/method/"
VERSION = "5.199"


def vk(method: str, params: dict | None = None) -> dict:
    """Call VK API and return response or exit on error."""
    params = params or {}
    params.setdefault("access_token", VK_TOKEN)
    params.setdefault("v", VERSION)
    try:
        resp = requests.post(API + method, data=params, timeout=30)
        data = resp.json()
    except Exception as exc:  # pragma: no cover - network errors
        print(f"HTTP error: {exc}", file=sys.stderr)
        sys.exit(1)
    if "error" in data:
        msg = data["error"].get("error_msg", "Unknown error")
        print(f"VK error {method}: {msg}", file=sys.stderr)
        sys.exit(1)
    return data["response"]


def get_album_id() -> int:
    """Find or create the bot album."""
    resp = vk("photos.getAlbums", {"group_id": VK_GROUP_ID})
    albums = resp.get("items", [])
    chosen = None
    for alb in albums:
        if alb["title"].startswith("bot_uploads"):
            chosen = alb
    if chosen and chosen.get("size", 0) < 10000:
        return chosen["id"]
    suffix = 1
    titles = {a["title"] for a in albums}
    name = "bot_uploads"
    while name in titles:
        suffix += 1
        name = f"bot_uploads_{suffix}"
    new_alb = vk(
        "photos.createAlbum",
        {"title": name, "group_id": VK_GROUP_ID, "privacy_view": "nobody"},
    )
    return new_alb["id"]


def upload_photo(album_id: int) -> str:
    """Upload photo to album and return attachment id."""
    up = vk("photos.getUploadServer", {"group_id": VK_GROUP_ID, "album_id": album_id})
    url = up["upload_url"]
    try:
        with open(PHOTO_PATH, "rb") as fh:
            resp = requests.post(url, files={"file1": fh}, timeout=300)
    except FileNotFoundError:
        print(f"File not found: {PHOTO_PATH}", file=sys.stderr)
        sys.exit(1)
    data = resp.json()
    save = vk(
        "photos.save",
        {
            "group_id": VK_GROUP_ID,
            "album_id": album_id,
            "server": data["server"],
            "photos_list": data["photos_list"],
            "hash": data["hash"],
        },
    )[0]
    return f"photo{save['owner_id']}_{save['id']}"


def post_wall(attachment: str) -> None:
    """Publish photo on group wall and print post URL."""
    resp = vk(
        "wall.post",
        {
            "owner_id": f"-{VK_GROUP_ID}",
            "from_group": 1,
            "message": "Hello from bot \U0001F44B",
            "attachments": attachment,
        },
    )
    post_url = f"https://vk.com/wall-{VK_GROUP_ID}_{resp['post_id']}"
    print(post_url)


def main() -> None:
    if not (VK_GROUP_ID and VK_TOKEN and PHOTO_PATH):
        print("VK_GROUP_ID, VK_TOKEN and PHOTO_PATH must be set", file=sys.stderr)
        sys.exit(1)
    album = get_album_id()
    attach = upload_photo(album)
    post_wall(attach)


if __name__ == "__main__":
    main()
