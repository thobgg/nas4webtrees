#!/usr/bin/env python3
"""Paketquelle für das Synology-Paket-Zentrum als statische Seite (GitHub Pages).

DSM 7 liest unter der eingetragenen Adresse eine JSON-Datei {"packages": [...]} und zeigt neue
Versionen als Update an. Format wie https://github.com/nhymxu/spkrepo (tools/dsm_catalog.py).

    package_source.py <spk> <pkg-dir mit INFO und Icons> <download-url> <ziel-ordner> <seiten-url>
"""
import hashlib
import html
import json
import os
import shutil
import sys

spk, pkgdir, link, out, site = sys.argv[1:6]


def info(path):
    d = {}
    for line in open(path, encoding="utf-8"):
        if "=" in line:
            k, v = line.rstrip("\n").split("=", 1)
            d[k] = v.strip().strip('"')
    return d


i = info(os.path.join(pkgdir, "INFO"))
md5 = hashlib.md5(open(spk, "rb").read()).hexdigest()
os.makedirs(out, exist_ok=True)
shutil.copy(os.path.join(pkgdir, "PACKAGE_ICON.PNG"), os.path.join(out, "icon_72.png"))
shutil.copy(os.path.join(pkgdir, "PACKAGE_ICON_256.PNG"), os.path.join(out, "icon_256.png"))

entry = {
    "package": i["package"],
    "version": i["version"],
    "dname": i.get("displayname", i["package"]),
    "desc": i.get("description_ger") or i.get("description", ""),
    "link": link,
    "md5": md5,
    "size": os.path.getsize(spk),
    "thumbnail": [f"{site}/icon_72.png"],
    "thumbnail_retina": [f"{site}/icon_256.png", f"{site}/icon_256.png"],
    "qinst": False,      # Installationsassistent vorhanden
    "qupgrade": False,   # Update-Assistent vorhanden
    "qstart": False,
    "deppkgs": i.get("install_dep_packages", ""),
    "maintainer": i.get("maintainer", ""),
    "maintainer_url": i.get("maintainer_url", ""),
    "distributor": i.get("maintainer", ""),
    "distributor_url": "https://github.com/thobgg/nas4webtrees",
    "changelog": f"webtrees für die NAS, Version {i['version']}. Details: https://github.com/thobgg/nas4webtrees/releases",
    "snapshot": [],
}
with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
    json.dump({"packages": [entry]}, f, ensure_ascii=False, indent=1)

e = html.escape
with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
    f.write(f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>nas4webtrees – Paketquelle</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:44rem;margin:2rem auto;padding:0 1rem;color:#222}}
code{{background:#eef;padding:.1em .3em;border-radius:3px}}img{{float:right}}</style></head><body>
<img src="icon_72.png" alt="" width="72" height="72">
<h1>nas4webtrees {e(i['version'])}</h1>
<p>Paketquelle für das Synology-Paket-Zentrum. Einmal eintragen, dann meldet DSM neue Versionen von selbst:</p>
<ol><li><b>Paket-Zentrum → Einstellungen → Paketquellen → Hinzufügen</b></li>
<li>Name: <code>nas4webtrees</code>, Ort: <code>{e(site)}/index.json</code></li>
<li>Im Paket-Zentrum unter <b>Community</b> erscheint nas4webtrees. Beim Installieren weist DSM darauf hin, dass das Paket nicht von Synology stammt – mit <b>Akzeptieren</b> geht es weiter.</li></ol>
<p>Oder direkt herunterladen: <a href="{e(link)}">{e(os.path.basename(link))}</a> und über „Manuelle Installation“ einspielen.</p>
<p><a href="https://github.com/thobgg/nas4webtrees">Projekt auf GitHub</a> · Gemeinschaftspaket, kein offizieller Teil von webtrees.</p>
</body></html>
""")
print(f"Paketquelle: {i['package']} {i['version']} → {out}")
