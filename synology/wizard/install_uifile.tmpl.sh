#!/bin/sh
# Assistent des webtrees-Pakets — schreibt das Assistenten-JSON nach $SYNOPKG_TEMP_LOGFILE.
# build.sh setzt ein: __WLANG__ = enu | ger, __WMODE__ = install | upgrade
WLANG="__WLANG__"
WMODE="__WMODE__"
WIZENV="/var/packages/nas4webtrees/var/wizard.env"
wiz_get() { [ -f "${WIZENV}" ] && sed -n "s/^$1=//p" "${WIZENV}" | head -1; }
d_port="$(wiz_get wizard_port)"; [ -n "${d_port}" ] || d_port="8095"
# Die Freigabe "docker" legt Container Manager an; es gibt sie also auf jeder NAS, auf der das
# Paket überhaupt laufen kann. Die Sicherung landet dort in webtrees-sicherung/, neben
# docker/nas4webtrees/ — und nicht darin, denn das löscht der Worker beim Deinstallieren.
d_share="$(wiz_get wizard_backup_share)"; [ -n "${d_share}" ] || d_share="docker"
d_user="${SYNOPKG_USERNAME:-admin}"
jq_esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }

if [ "${WLANG}" = "ger" ]; then
T_P1="Stammbaum und Administrator"
T_P1_INTRO="Das Paket richtet das <b>originale webtrees</b> ein — mit einer einzigen Datenbankdatei statt Datenbank-Server und dem Modul <b>api4webtrees</b> für die Apps wtAnd, wtWin und wtTux."
T_TREE="Name des Stammbaums"
T_USER="Benutzername des Administrators"
T_NAME="Vollständiger Name"
T_EMAIL="E-Mail-Adresse"
T_PW="Passwort"
T_PW_HINT="Mindestens 8 Zeichen. Dieses Konto gilt nur für webtrees, nicht für DSM."
T_REQ="Pflichtfeld"
T_EMAIL_ERR="Bitte eine E-Mail-Adresse angeben"
T_PW_ERR="Mindestens 8 Zeichen"
T_P2="Erreichbarkeit und Sicherung"
T_P2_INTRO="webtrees ist danach im Heimnetz unter <b>http://&lt;NAS&gt;:&lt;Port&gt;</b> erreichbar."
T_PORT="Port"
T_PORT_ERR="Port zwischen 1024 und 65535"
T_SHARE="Freigabe für die Sicherung"
T_SHARE_HINT="Jede Nacht sichert das Paket jeden Stammbaum als <b>GEDCOM-Datei</b>, dazu Datenbank und Fotos, nach <code>&lt;Freigabe&gt;/webtrees-sicherung</code>. Dieser Ordner bleibt auch beim Deinstallieren."
T_SHARE_ERR="Nur der Name der Freigabe, kein Pfad"
T_RESTORE="Aus vorhandener Sicherung wiederherstellen"
T_RESTORE_HINT="Nur wirksam, wenn dort schon eine Sicherung liegt — etwa nach einer Neuinstallation."
T_P3="Vor dem Start"
T_IMPORT="<b>Vorhandenen Stammbaum übernehmen?</b> Nach der Installation die GEDCOM-Datei in den Ordner <code>webtrees-sicherung/import</code> legen und das Paket einmal stoppen und starten. Oder in webtrees: Verwaltung → Stammbäume → GEDCOM-Datei importieren."
T_WAIT="<b>Die Installation dauert einige Minuten.</b> Beim ersten Mal lädt der Container Manager einige hundert MB; der Fortschrittsbalken bewegt sich dabei kaum."
T_UPD="Programm und Daten bleiben erhalten. webtrees selbst aktualisierst du wie gewohnt in webtrees unter Verwaltung → Aktualisierung; dieses Paket-Update erneuert nur die Umgebung (Apache, PHP) und api4webtrees und setzt webtrees nie auf eine ältere Fassung zurück."
else
T_P1="Family tree and administrator"
T_P1_INTRO="This package sets up the <b>original webtrees</b> — with a single database file instead of a database server, and the <b>api4webtrees</b> module for the wtAnd, wtWin and wtTux apps."
T_TREE="Name of the family tree"
T_USER="Administrator user name"
T_NAME="Full name"
T_EMAIL="Email address"
T_PW="Password"
T_PW_HINT="At least 8 characters. This account is for webtrees only, not for DSM."
T_REQ="Required"
T_EMAIL_ERR="Please enter an email address"
T_PW_ERR="At least 8 characters"
T_P2="Access and backup"
T_P2_INTRO="webtrees is then reachable on your LAN at <b>http://&lt;NAS&gt;:&lt;port&gt;</b>."
T_PORT="Port"
T_PORT_ERR="Port between 1024 and 65535"
T_SHARE="Shared folder for backups"
T_SHARE_HINT="Every night the package backs up each family tree as a <b>GEDCOM file</b>, plus database and photos, to <code>&lt;share&gt;/webtrees-sicherung</code>. This folder is kept when you uninstall."
T_SHARE_ERR="Just the share name, no path"
T_RESTORE="Restore from an existing backup"
T_RESTORE_HINT="Only takes effect if a backup is already there — e.g. after reinstalling."
T_P3="Before you start"
T_IMPORT="<b>Bringing an existing tree?</b> After installation, put the GEDCOM file into the folder <code>webtrees-sicherung/import</code> and stop and start the package once. Or in webtrees: Control panel → Family trees → Import a GEDCOM file."
T_WAIT="<b>Installation takes a few minutes.</b> The first time, Container Manager downloads a few hundred MB; the progress bar barely moves meanwhile."
T_UPD="Program and data are kept. You update webtrees itself as usual in webtrees under Control panel → Upgrade; this package update only renews the environment (Apache, PHP) and api4webtrees and never takes webtrees back to an older version."
fi

RX_PORT="/^(102[4-9]|10[3-9][0-9]|1[1-9][0-9]{2}|[2-9][0-9]{3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$/"
RX_SHARE="/^[^\\\\\\\\/:*?\\\"<>|]+$/"

page2_fields="$(cat <<EOT
  {"type":"textfield","subitems":[{"key":"wizard_port","desc":"${T_PORT}","defaultValue":"${d_port}",
    "validator":{"allowBlank":false,"regex":{"expr":"${RX_PORT}","errorText":"${T_PORT_ERR}"}}}]},
  {"desc":"${T_SHARE_HINT}"},
  {"type":"textfield","subitems":[{"key":"wizard_backup_share","desc":"${T_SHARE}","defaultValue":"${d_share}",
    "validator":{"allowBlank":false,"regex":{"expr":"${RX_SHARE}","errorText":"${T_SHARE_ERR}"}}}]}
EOT
)"

if [ "${WMODE}" = "upgrade" ]; then
cat > "${SYNOPKG_TEMP_LOGFILE}" <<EOT
[
 {"step_title":"${T_P2}","invalid_next_disabled":true,"items":[
  {"desc":"${T_UPD}"},
${page2_fields}
 ]}
]
EOT
exit 0
fi

cat > "${SYNOPKG_TEMP_LOGFILE}" <<EOT
[
 {"step_title":"${T_P1}","invalid_next_disabled":true,"items":[
  {"desc":"${T_P1_INTRO}"},
  {"type":"textfield","subitems":[{"key":"wizard_tree_title","desc":"${T_TREE}","defaultValue":"Mein Stammbaum",
    "validator":{"allowBlank":false,"blankText":"${T_REQ}"}}]},
  {"type":"textfield","subitems":[{"key":"wizard_admin_user","desc":"${T_USER}","defaultValue":"$(jq_esc "${d_user}")",
    "validator":{"allowBlank":true}}]},
  {"type":"textfield","subitems":[{"key":"wizard_admin_name","desc":"${T_NAME}","defaultValue":"",
    "validator":{"allowBlank":true}}]},
  {"type":"textfield","subitems":[{"key":"wizard_admin_email","desc":"${T_EMAIL}","defaultValue":"",
    "validator":{"allowBlank":true,"regex":{"expr":"/^[^@ ]+@[^@ ]+\\\\.[^@ ]+$/","errorText":"${T_EMAIL_ERR}"}}}]},
  {"desc":"${T_PW_HINT}"},
  {"type":"password","subitems":[{"key":"wizard_admin_pw","desc":"${T_PW}",
    "validator":{"allowBlank":true,"minLength":8,"minLengthText":"${T_PW_ERR}"}}]}
 ]},
 {"step_title":"${T_P2}","invalid_next_disabled":true,"items":[
  {"desc":"${T_P2_INTRO}"},
${page2_fields},
  {"type":"multiselect","subitems":[{"key":"wizard_restore","desc":"${T_RESTORE}","defaultValue":true}]},
  {"desc":"${T_RESTORE_HINT}"}
 ]},
 {"step_title":"${T_P3}","items":[
  {"desc":"${T_IMPORT}"},
  {"desc":"${T_WAIT}"}
 ]}
]
EOT
exit 0
