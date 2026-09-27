#!/usr/bin/env python3
"""Umbrel-Store auf eine neue Image-Version heben: Tag im Compose, version und releaseNotes im Manifest.

    bump_umbrel.py <app-ordner> <tag>

Der Store ist englisch; CHANGES.md ist für Synology-Nutzer geschrieben – darum nur ein Hinweis mit Link.
"""
import re
import sys

app, tag = sys.argv[1:3]

compose = f"{app}/docker-compose.yml"
s = open(compose, encoding="utf-8").read()
s = re.sub(r"(image: ghcr\.io/thobgg/nas4webtrees:)\S+", rf"\g<1>{tag}", s)
open(compose, "w", encoding="utf-8").write(s)

news = f"nas4webtrees {tag}. What's new: https://github.com/thobgg/nas4webtrees/blob/main/CHANGES.md"

manifest = f"{app}/umbrel-app.yml"
s = open(manifest, encoding="utf-8").read()
s = re.sub(r'^version: .*$', f'version: "{tag}"', s, flags=re.M)
s = re.sub(r"^releaseNotes: >-\n(?:[ ]{2}.*\n|\n)*", f"releaseNotes: >-\n  {news}\n", s, flags=re.M)
open(manifest, "w", encoding="utf-8").write(s)
print(f"Umbrel: {tag}")
