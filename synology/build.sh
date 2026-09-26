#!/bin/bash
# Baut das Synology-Paket nas4webtrees-<version>.spk nach ../dist/.
# Ein SPK ist ein tar aus: INFO, PACKAGE_ICON*.PNG, package.tgz, scripts/, conf/, WIZARD_UIFILES/.
# Kein spksrc, kein pkgscripts — für ein noarch-Paket ohne Kompilat reicht tar.
#
#   synology/build.sh               → Build-Nummer aus BUILD; das Paket zieht das fertige Image
#                                     ghcr.io/thobgg/nas4webtrees:<WEBTREES>-<REVISION>
#   synology/build.sh 3             → Build-Nummer 3
#   synology/build.sh --standalone  → das Paket baut das ganze Image selbst auf der NAS
#                                     (für Tests, solange das Image nicht veröffentlicht ist)
#
# Warum im Normalfall nur FROM: DSM baut das Image auf der NAS, und RUN-Schritte brauchen dort
# Namensauflösung im Bridge-Netz. Die fehlt bei strengen DNS-Filtern, der Bau scheitert dann nach
# Minuten ohne Meldung. FROM läuft über den Docker-Daemon der NAS.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
PKGID="nas4webtrees"
IMAGE_REPO="ghcr.io/thobgg/nas4webtrees"

ver() { sed -n "s/^$1=//p" "${ROOT}/VERSIONS" | tr -d '[:space:]'; }
WT_VER="$(ver WEBTREES)"
REV="$(ver REVISION)"
[ -n "${WT_VER}" ] && [ -n "${REV}" ] || { echo "✗ VERSIONS unvollständig"; exit 1; }
IMAGE_TAG="${WT_VER}-${REV}"

STANDALONE=0
if [ "${1:-}" = "--standalone" ]; then STANDALONE=1; shift; fi
BUILD="${1:-$(tr -d '[:space:]' < "${HERE}/BUILD")}"
VERSION="${WT_VER}-${BUILD}"
DIST="${ROOT}/dist"
STAGE="${DIST}/stage"
PKG="${DIST}/pkg"
SUFFIX=""; [ "${STANDALONE}" = 1 ] && SUFFIX="-standalone"
OUT="${DIST}/${PKGID}-${VERSION}${SUFFIX}.spk"

echo "→ webtrees ${WT_VER}, Image ${IMAGE_TAG}, Paket ${VERSION}${SUFFIX}"
rm -rf "${STAGE}" "${PKG}"
mkdir -p "${STAGE}" "${PKG}"

# 1) target/image = Docker-Build-Kontext (conf/resource: "build": "image")
IMG="${STAGE}/image"; mkdir -p "${IMG}"
if [ "${STANDALONE}" = 1 ]; then
    # Das ganze Image mit fest eingetragenen Build-Argumenten (der Worker kann keine übergeben).
    rsync -a "${ROOT}/image/" "${IMG}/"
    python3 - "${IMG}/Dockerfile" "${ROOT}/VERSIONS" <<'PY'
import re, sys
df, vf = sys.argv[1], sys.argv[2]
v = dict(l.strip().split("=", 1) for l in open(vf) if re.match(r"^[A-Z0-9_]+=", l))
m = {"WEBTREES_VERSION": v["WEBTREES"], "WEBTREES_SHA256": v["WEBTREES_SHA256"],
     "API4WEBTREES_VERSION": v["API4WEBTREES"], "API4WEBTREES_SHA256": v["API4WEBTREES_SHA256"]}
s = open(df).read()
for k, val in m.items():
    s = re.sub(rf"^ARG {k}$", f"ARG {k}={val}", s, flags=re.M)
open(df, "w").write(s)
PY
else
    cat > "${IMG}/Dockerfile" <<EOT
# Synology-Paket nas4webtrees: das fertige Image nas4webtrees, unverändert.
FROM ${IMAGE_REPO}:${IMAGE_TAG}
EOT
fi

# 2) übrige Paketdateien unter target/
rsync -a --exclude 'image/' "${HERE}/package/" "${STAGE}/"
mkdir -p "${STAGE}/conf"; touch "${STAGE}/conf/.keep"
# Mount-Platzhalter: prestart ersetzt ihn durch einen Symlink auf die Freigabe für die
# Sicherung (der Worker erlaubt nur Pfade unter target/ und lehnt Symlinks ab).
mkdir -p "${STAGE}/mounts/backup" "${STAGE}/empty"
touch "${STAGE}/mounts/backup/.keep" "${STAGE}/empty/.nas4webtrees-no-target"
cp "${ROOT}/LICENSE" "${STAGE}/LICENSE"

# 3) Icons
ICON="${HERE}/package/icon.svg"
mkdir -p "${STAGE}/ui/images"
for s in 16 24 32 48 64 72 256; do
    inkscape -w "$s" -h "$s" "${ICON}" -o "${STAGE}/ui/images/nas4webtrees_${s}.png" >/dev/null 2>&1
done
cp "${STAGE}/ui/images/nas4webtrees_72.png"  "${PKG}/PACKAGE_ICON.PNG"
cp "${STAGE}/ui/images/nas4webtrees_256.png" "${PKG}/PACKAGE_ICON_256.PNG"
rm -f "${STAGE}/icon.svg"

# 4) conf/ — resource enthält {{wizard_…}}-Platzhalter, die DSM beim Installieren füllt
mkdir -p "${PKG}/conf"
cp "${HERE}/conf/privilege" "${PKG}/conf/"
sed -e "s/{{PKG_VERSION}}/${VERSION}/g" "${HERE}/conf/resource" > "${PKG}/conf/resource"
python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${PKG}/conf/resource" \
    || { echo "✗ conf/resource ist kein gültiges JSON"; exit 1; }
sed 's/__LAN_PORT__/8095/g' "${HERE}/package/templates/ui-config.tmpl" > "${STAGE}/ui/config"
sed 's/__LAN_PORT__/8095/g' "${HERE}/package/port_conf/nas4webtrees.sc.tmpl" > "${STAGE}/port_conf/nas4webtrees.sc"

# 5) scripts/
mkdir -p "${PKG}/scripts"
cp "${HERE}"/scripts/* "${PKG}/scripts/"
chmod 755 "${PKG}"/scripts/*
for f in "${PKG}"/scripts/*; do sh -n "$f" || { echo "✗ Syntax: $f"; exit 1; }; done

# 6) WIZARD_UIFILES/ — enu ist der Rückfall ohne Suffix
W="${PKG}/WIZARD_UIFILES"; mkdir -p "${W}"
for m in install upgrade; do
    sed -e 's/__WLANG__/enu/' -e "s/__WMODE__/${m}/" "${HERE}/wizard/install_uifile.tmpl.sh" > "${W}/${m}_uifile.sh"
    sed -e 's/__WLANG__/ger/' -e "s/__WMODE__/${m}/" "${HERE}/wizard/install_uifile.tmpl.sh" > "${W}/${m}_uifile_ger.sh"
done
cp "${HERE}/wizard/uninstall_uifile.enu" "${W}/uninstall_uifile"
cp "${HERE}/wizard/uninstall_uifile.ger" "${W}/uninstall_uifile_ger"
chmod 755 "${W}"/*.sh
# Trockentest: jede Assistenten-Fassung muss gültiges JSON liefern
for f in "${W}"/*.sh; do
    t="$(mktemp)"; SYNOPKG_TEMP_LOGFILE="${t}" SYNOPKG_USERNAME=admin sh "$f"
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${t}" || { echo "✗ Assistent kein JSON: $f"; exit 1; }
    rm -f "${t}"
done
for f in "${W}"/uninstall_uifile*; do
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" || { echo "✗ kein JSON: $f"; exit 1; }
done

# 7) package.tgz + INFO
tar -czf "${PKG}/package.tgz" -C "${STAGE}" .
EXTRACT_KB="$(du -sk "${STAGE}" | cut -f1)"
sed -e "s/__VERSION__/${VERSION}/" -e "s/__LAN_PORT__/8095/" -e "s/__EXTRACTSIZE__/${EXTRACT_KB}/" \
    "${HERE}/INFO.in" > "${PKG}/INFO"

# 8) SPK
rm -f "${OUT}"
tar -cf "${OUT}" -C "${PKG}" INFO PACKAGE_ICON.PNG PACKAGE_ICON_256.PNG package.tgz scripts conf WIZARD_UIFILES
echo "✓ $(du -h "${OUT}" | cut -f1)  ${OUT}"
