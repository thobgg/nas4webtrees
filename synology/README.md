# Synology-Paket

Paket für DSM 7.2+ auf Modellen mit Container Manager: Installationsassistent (Stammbaum,
Administrator, Port, Freigabe für die Sicherung), kein root, keine Web Station, keine MariaDB.
Das Paket zieht das Image `ghcr.io/thobgg/nas4webtrees` und legt Programm und Daten unter
`docker/nas4webtrees/data` ab, die Sicherung unter `<Freigabe>/webtrees-sicherung` (bleibt beim
Deinstallieren stehen). Anleitung für Nutzer: [docs/synology/anleitung.de.md](../docs/synology/anleitung.de.md).

## Bauen

`synology/build.sh` → `dist/nas4webtrees-<webtrees>-<build>.spk` (Build = Zahl der Commits), einspielen
über Paket-Zentrum → Manuelle Installation. `--standalone` baut das ganze Image auf der NAS statt es
zu laden. Braucht `inkscape` (Symbole) und `python3` (JSON-Prüfung). Den Release samt Paketquelle
baut GitHub Actions (`.github/workflows/image.yml`).

## Aufbau

| Pfad | Inhalt |
| - | - |
| `INFO.in` | Paketbeschreibung; `__VERSION__`, `__EXTRACTSIZE__` setzt build.sh ein |
| `conf/privilege` | läuft als Paketnutzer `nas4webtrees`, nie als root |
| `conf/resource` | Docker-Worker: Image, Container, Ordner, Port (`{{wizard_port}}` setzt DSM ein) |
| `scripts/common` | **Konstanten** (Port-Vorgabe, Sicherungsordner, Container) und alle Helfer |
| `scripts/preinst` | prüft die Eingaben aus dem Assistenten, bei Installation und Update |
| `scripts/postinst` | merkt sich Port und Freigabe, setzt den Port ein, schreibt `setup.json` |
| `scripts/start-stop-status` | `prestart`: Mount für die Sicherung, Gruppe und Zeitzone für den Container |
| `wizard/` | Assistenten für Installation, Update (Port, Freigabe) und Deinstallation, deutsch und englisch |
| `package/` | Inhalt von `target/`: Vorlagen für DSM-Menü und Firewall-Dienst, Symbol |

Platzhalter: `__NAME__` ersetzt build.sh beim Bauen (aus `scripts/common` und der Version) und prüft am
Ende, dass keiner übrig ist; nur `__LAN_PORT__` in `package/templates/` füllt postinst mit dem gewählten
Port. `{{wizard_…}}` ersetzt DSM beim Installieren.

## Ablauf auf der NAS

1. **Assistent** (vor dem Auspacken): Stammbaum, Konto, Port, Freigabe.
2. **preinst**: Port frei und gültig, Freigabe vorhanden, Konto vollständig (entfällt über vorhandenen
   Daten oder einer Sicherung, die wiederhergestellt wird).
3. **Docker-Worker**: baut das Image (`FROM ghcr.io/thobgg/nas4webtrees:<tag>`) und legt den Container an.
4. **postinst**: `var/wizard.env` (ohne Passwort), Port in `ui/config` und `port_conf/`, bei der
   Erstinstallation `conf/setup.json` – das Image richtet webtrees damit ein und löscht das Passwort.
5. **prestart** bei jedem Start: `mounts/backup` → `/volume1/<Freigabe>`, `conf/write-gid`, `conf/timezone`.

Beim Update lässt der Worker `docker/nas4webtrees` stehen; der Update-Assistent fragt Port und Freigabe
erneut, vorbelegt mit den gespeicherten Werten.
