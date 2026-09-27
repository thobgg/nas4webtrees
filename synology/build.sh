#!/bin/bash
# Baut das Synology-Paket nas4webtrees-<version>.spk nach ../dist/.
# Ein SPK ist ein tar aus INFO, PACKAGE_ICON*.PNG, package.tgz, scripts/, conf/ und WIZARD_UIFILES/.
# Kein spksrc, kein pkgscripts – für ein noarch-Paket ohne Kompilat reicht tar.
#
#   synology/build.sh               → Build-Nummer = Zahl der Commits; das Paket zieht das fertige Image
#                                     ghcr.io/thobgg/nas4webtrees:<WEBTREES>-<REVISION>
#   synology/build.sh 3             → Build-Nummer 3
#   synology/build.sh --standalone  → das Paket baut das ganze Image selbst auf der NAS
#                                     (zum Testen eines Image-Stands, der noch nicht veröffentlicht ist)
#
# Platzhalter: __NAME__ setzt dieses Skript beim Bauen ein (Konstanten aus scripts/common, Version),
# {{wizard_…}} setzt DSM beim Installieren ein (nur in conf/resource).
#
# Warum im Normalfall nur FROM: DSM baut das Image auf der NAS, und RUN-Schritte brauchen dort
# Namensauflösung im Bridge-Netz. Die fehlt bei strengen DNS-Filtern, der Bau scheitert dann nach
# Minuten ohne Meldung. FROM läuft über den Docker-Daemon der NAS.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
IMAGE_REPO="ghcr.io/thobgg/nas4webtrees"

# Konstanten (PKG, CONTAINER, DEFAULT_LAN_PORT, BACKUP_SUBDIR, DEFAULT_SHARE) und apply_ports –
# dieselben wie auf der NAS.
# shellcheck source=scripts/common
. "${HERE}/scripts/common"

die() { echo "✗ $*" >&2; exit 1; }
ver() { sed -n "s/^$1=//p" "${ROOT}/VERSIONS" | tr -d '[:space:]'; }
json_ok() { python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$1" 2>/dev/null; }

# ── Versionen und Pfade ────────────────────────────────────────────────────────────────────────────
WT_VER="$(ver WEBTREES)"
REV="$(ver REVISION)"
[ -n "${WT_VER}" ] && [ -n "${REV}" ] || die "VERSIONS unvollständig"
IMAGE_TAG="${WT_VER}-${REV}"

STANDALONE=0
if [ "${1:-}" = "--standalone" ]; then STANDALONE=1; shift; fi
# Build-Nummer aus der Git-Historie: steigt mit jedem Commit, lokal wie in GitHub Actions gleich
# (dort mit vollständiger Historie auschecken). Ohne Historie lieber abbrechen als raten.
BUILD="${1:-$(git -C "${ROOT}" rev-list --count HEAD 2>/dev/null || echo 0)}"
[ "${BUILD}" -gt 0 ] || die "Keine Git-Historie – Build-Nummer unbekannt"
VERSION="${WT_VER}-${BUILD}"

DIST="${ROOT}/dist"
STAGE="${DIST}/stage"        # wird zu package.tgz = target/ auf der NAS
SPKDIR="${DIST}/pkg"         # die Einzelteile des SPK
SUFFIX=""; [ "${STANDALONE}" = 1 ] && SUFFIX="-standalone"
OUT="${DIST}/${PKG}-${VERSION}${SUFFIX}.spk"

# Konstanten in eine Datei einsetzen: fill <quelle> > <ziel>
fill() {
    sed -e "s/__PKG__/${PKG}/g" -e "s/__CONTAINER__/${CONTAINER}/g" \
        -e "s/__DEFAULT_LAN_PORT__/${DEFAULT_LAN_PORT}/g" -e "s/__DEFAULT_SHARE__/${DEFAULT_SHARE}/g" \
        -e "s/__BACKUP_SUBDIR__/${BACKUP_SUBDIR}/g" -e "s/__PKG_VERSION__/${VERSION}/g" "$1"
}

# ── 1. target/image: Docker-Build-Kontext (conf/resource: "build": "image") ───────────────────────
stage_image() {
    local img="${STAGE}/image"
    mkdir -p "${img}"
    if [ "${STANDALONE}" = 1 ]; then
        # Das ganze Image mit fest eingetragenen Build-Argumenten (der Worker kann keine übergeben).
        rsync -a "${ROOT}/image/" "${img}/"
        python3 - "${img}/Dockerfile" "${ROOT}/VERSIONS" <<'PY'
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
        printf '# Synology-Paket %s: das fertige Image, unverändert.\nFROM %s:%s\n' \
            "${PKG}" "${IMAGE_REPO}" "${IMAGE_TAG}" > "${img}/Dockerfile"
    fi
}

# ── 2. übrige Dateien unter target/ ───────────────────────────────────────────────────────────────
stage_files() {
    rsync -a --exclude 'icon.svg' "${HERE}/package/" "${STAGE}/"
    cp "${ROOT}/LICENSE" "${STAGE}/LICENSE"
    # /config für den Container (setup.json, write-gid, timezone schreiben die Paketskripte)
    mkdir -p "${STAGE}/conf"
    # Mount-Platzhalter: prestart ersetzt ihn durch einen Symlink auf die Freigabe für die
    # Sicherung (der Worker erlaubt nur Pfade unter target/ und lehnt Symlinks ab).
    mkdir -p "${STAGE}/mounts/backup" "${STAGE}/empty"
    touch "${STAGE}/mounts/backup/.keep" "${STAGE}/empty/.nas4webtrees-no-target"
    # Menüeinträge und Firewall-Dienst mit dem Vorgabe-Port; postinst setzt den gewählten ein.
    TARGET="${STAGE}" apply_ports "${DEFAULT_LAN_PORT}"
}

# ── 3. Symbole (Paket-Zentrum und DSM-Menü) ────────────────────────────────────────────────────────
stage_icons() {
    local s
    mkdir -p "${STAGE}/ui/images"
    for s in 16 24 32 48 64 72 256; do
        inkscape -w "$s" -h "$s" "${HERE}/package/icon.svg" -o "${STAGE}/ui/images/${PKG}_${s}.png" >/dev/null 2>&1 \
            || die "inkscape fehlt oder scheitert (Symbol ${s} px)"
    done
    cp "${STAGE}/ui/images/${PKG}_72.png"  "${SPKDIR}/PACKAGE_ICON.PNG"
    cp "${STAGE}/ui/images/${PKG}_256.png" "${SPKDIR}/PACKAGE_ICON_256.PNG"
}

# ── 4. conf/: Rechte und Docker-Deklaration ───────────────────────────────────────────────────────
spk_conf() {
    mkdir -p "${SPKDIR}/conf"
    cp "${HERE}/conf/privilege" "${SPKDIR}/conf/"
    fill "${HERE}/conf/resource" > "${SPKDIR}/conf/resource"
    json_ok "${SPKDIR}/conf/resource" || die "conf/resource ist kein gültiges JSON"
}

# ── 5. scripts/ ───────────────────────────────────────────────────────────────────────────────────
spk_scripts() {
    local f
    mkdir -p "${SPKDIR}/scripts"
    cp "${HERE}"/scripts/* "${SPKDIR}/scripts/"
    chmod 755 "${SPKDIR}"/scripts/*
    for f in "${SPKDIR}"/scripts/*; do sh -n "$f" || die "Syntax: $f"; done
}

# ── 6. WIZARD_UIFILES/: Installation, Update, Deinstallation; enu ist der Rückfall ohne Suffix ──────
spk_wizard() {
    local w="${SPKDIR}/WIZARD_UIFILES" m f t
    mkdir -p "${w}"
    for m in install upgrade; do
        fill "${HERE}/wizard/install_uifile.tmpl.sh" | sed -e 's/__WLANG__/enu/' -e "s/__WMODE__/${m}/" > "${w}/${m}_uifile.sh"
        fill "${HERE}/wizard/install_uifile.tmpl.sh" | sed -e 's/__WLANG__/ger/' -e "s/__WMODE__/${m}/" > "${w}/${m}_uifile_ger.sh"
    done
    fill "${HERE}/wizard/uninstall_uifile.enu" > "${w}/uninstall_uifile"
    fill "${HERE}/wizard/uninstall_uifile.ger" > "${w}/uninstall_uifile_ger"
    chmod 755 "${w}"/*.sh
    # Trockentest: jede Fassung muss gültiges JSON liefern
    for f in "${w}"/*.sh; do
        t="$(mktemp)"
        SYNOPKG_TEMP_LOGFILE="${t}" SYNOPKG_USERNAME=admin sh "$f"
        json_ok "${t}" || die "Assistent liefert kein JSON: $f"
        rm -f "${t}"
    done
    for f in "${w}"/uninstall_uifile*; do json_ok "$f" || die "kein JSON: $f"; done
}

# ── 7. package.tgz, INFO und das SPK ──────────────────────────────────────────────────────────────
spk_pack() {
    tar -czf "${SPKDIR}/package.tgz" -C "${STAGE}" .
    sed -e "s/__VERSION__/${VERSION}/" -e "s/__EXTRACTSIZE__/$(du -sk "${STAGE}" | cut -f1)/" \
        "${HERE}/INFO.in" > "${SPKDIR}/INFO"
    rm -f "${OUT}"
    tar -cf "${OUT}" -C "${SPKDIR}" INFO PACKAGE_ICON.PNG PACKAGE_ICON_256.PNG package.tgz scripts conf WIZARD_UIFILES
}

# Kein Platzhalter darf übrig bleiben – außer __LAN_PORT__ in den Vorlagen, die postinst ausfüllt.
check_placeholders() {
    local left
    left="$(grep -rIo --exclude-dir=templates '__[A-Z_]*__' "${SPKDIR}/INFO" "${SPKDIR}/conf" \
        "${SPKDIR}/scripts" "${SPKDIR}/WIZARD_UIFILES" "${STAGE}" | grep -v ':__LAN_PORT__$' || true)"
    [ -z "${left}" ] || { rm -f "${OUT}"; die "Platzhalter nicht ersetzt: ${left}"; }
}

echo "→ webtrees ${WT_VER}, Image ${IMAGE_TAG}, Paket ${VERSION}${SUFFIX}"
rm -rf "${STAGE}" "${SPKDIR}"
mkdir -p "${STAGE}" "${SPKDIR}"
stage_image
stage_files
stage_icons
spk_conf
spk_scripts
spk_wizard
spk_pack
check_placeholders
echo "✓ $(du -h "${OUT}" | cut -f1)  ${OUT}"
