#!/usr/bin/env python3
"""Download audio exposed by a public Xiaoyuzhou episode page."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "Mozilla/5.0 (compatible; podcast-source-forensics/1.0)"
ALLOWED_HOSTS = {"xiaoyuzhoufm.com", "www.xiaoyuzhoufm.com"}


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "-", value).strip().rstrip(".")
    value = re.sub(r"\s+", " ", value)
    return value[:120] or "episode"


def read_url(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return data.decode(charset, errors="replace")


def extract_episode(page: str, page_url: str) -> dict[str, Any]:
    episode: dict[str, Any] = {
        "source_url": page_url,
        "title": None,
        "show_name": None,
        "description": None,
        "duration": None,
        "published": None,
        "audio_url": None,
    }

    meta_patterns = {
        "title": r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)',
        "audio_url": r'<meta\s+property=["\']og:audio["\']\s+content=["\']([^"\']+)',
        "description": r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)',
    }
    for key, pattern in meta_patterns.items():
        match = re.search(pattern, page, flags=re.IGNORECASE)
        if match:
            episode[key] = html.unescape(match.group(1))

    scripts = re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in scripts:
        try:
            data = json.loads(html.unescape(match.group(1)).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict) or item.get("@type") != "PodcastEpisode":
                continue
            media = item.get("associatedMedia") or {}
            series = item.get("partOfSeries") or {}
            episode.update(
                {
                    "title": item.get("name") or episode["title"],
                    "show_name": series.get("name") or episode["show_name"],
                    "description": item.get("description") or episode["description"],
                    "duration": item.get("timeRequired") or episode["duration"],
                    "published": item.get("datePublished") or episode["published"],
                    "audio_url": media.get("contentUrl") or episode["audio_url"],
                }
            )

    if not episode["audio_url"]:
        raise RuntimeError("No public audio URL was found in the page metadata.")
    episode["title"] = episode["title"] or "Xiaoyuzhou Episode"
    return episode


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": "https://www.xiaoyuzhoufm.com/"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Public Xiaoyuzhou episode URL")
    parser.add_argument("--output-dir", required=True, help="Directory for metadata and audio")
    parser.add_argument("--metadata-only", action="store_true", help="Do not download audio")
    args = parser.parse_args()

    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ALLOWED_HOSTS:
        parser.error("--url must be a public xiaoyuzhoufm.com episode URL")

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        episode = extract_episode(read_url(args.url), args.url)
        if not args.metadata_only:
            suffix = Path(urllib.parse.urlparse(episode["audio_url"]).path).suffix or ".m4a"
            audio_path = output_dir / f"{safe_name(episode['title'])}{suffix}"
            download(episode["audio_url"], audio_path)
            episode["audio_file"] = audio_path.name
        metadata_path = output_dir / "episode.json"
        metadata_path.write_text(
            json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"METADATA={metadata_path}")
    if episode.get("audio_file"):
        print(f"AUDIO={output_dir / episode['audio_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
