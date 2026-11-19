"""
Parse M3U / M3U8 playlists into a list of channel dicts.

Supported tags:
  #EXTINF:-1 tvg-id="..." tvg-logo="..." group-title="...",Channel Name
  http://stream.url/...
"""
import re
from typing import List, Dict, Optional


_ATTR_RE = re.compile(r'(\w[\w-]*)="([^"]*)"')


def _parse_extinf(line: str) -> Dict:
    attrs = dict(_ATTR_RE.findall(line))
    name_part = line.rsplit(",", 1)
    name = name_part[-1].strip() if "," in line else ""
    return {
        "name": name,
        "logo_url": attrs.get("tvg-logo") or attrs.get("tvg-logo-url") or None,
        "group": attrs.get("group-title") or None,
    }


def parse_m3u(text: str) -> List[Dict]:
    channels = []
    lines = [l.rstrip() for l in text.splitlines()]
    i = 0
    meta: Optional[Dict] = None
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            meta = _parse_extinf(line)
        elif line and not line.startswith("#"):
            if meta is None:
                meta = {"name": line, "logo_url": None, "group": None}
            channels.append({
                "name": meta["name"] or line,
                "logo_url": meta["logo_url"],
                "group": meta["group"],
                "stream_url": line,
            })
            meta = None
        i += 1
    return channels
