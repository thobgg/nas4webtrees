# nas4webtrees

[English](README.md) · **Deutsch**

Das originale, unveränderte [webtrees](https://webtrees.net/) für NAS und Heimserver — mit
[api4webtrees](https://github.com/thobgg/api4webtrees) an Bord, damit sich die Apps **wtAnd**
(Android), **wtWin** (Windows) und **wtTux** (Linux) aus
[app4webtrees](https://github.com/thobgg/app4webtrees) sofort verbinden.

- **Natives webtrees, kein Fork.** Beim ersten Start wird die offizielle Release-Datei von
  [fisharebest/webtrees](https://github.com/fisharebest/webtrees/releases) (mit Prüfsumme) in
  dein Volume entpackt. Danach gehört die Installation webtrees: Aktualisiert wird wie gewohnt
  unter *Verwaltung → Aktualisierung*. Ein neues Image fasst sie nie an und setzt sie nie zurück.
- **Kein Datenbank-Server.** Standard ist SQLite — eine einzige Datei. MySQL/MariaDB und
  PostgreSQL gehen auch.
- **Deine GEDCOM-Datei, jede Nacht.** Jeder Stammbaum landet als `backup/gedcom/<baum>.ged`
  (fester Name, dazu 30 ältere Stände), zusammen mit einer konsistenten Kopie der Datenbank und
  einem Spiegel aller Fotos. Neu installieren neben der Sicherung holt den letzten Stand zurück.
- **Vorhandenen Stammbaum mitbringen.** GEDCOM-Datei nach `backup/import/` legen und neu
  starten: Sie wird in den (noch leeren) Stammbaum übernommen.
- amd64, arm64 und armv7.

## Wo es läuft

| Plattform | Weg |
| - | - |
| Synology (DSM 7.2+, Modelle mit Container Manager) | Paket mit Installationsassistent: `nas4webtrees-….spk` unter [Releases](https://github.com/thobgg/nas4webtrees/releases) laden, dann Paket-Zentrum → Manuelle Installation |
| TrueNAS SCALE 25.04+ | Apps → Discover → *Install via YAML* mit [`compose/docker-compose.yml`](compose/docker-compose.yml) |
| UGREEN (UGOS Pro) | Docker → Projekt → Erstellen, Compose-Datei einfügen |
| TerraMaster (TOS 6) | Docker Manager → Projekt, Compose-Datei einfügen |
| Asustor (ADM) | Portainer aus App Central → Stacks, Compose-Datei einfügen |
| Unraid | Vorlage [`unraid/nas4webtrees.xml`](unraid/nas4webtrees.xml) |
| QNAP | Container Station → Anwendungen, Compose-Datei einfügen |
| Raspberry Pi, jeder Linux-Server | `docker compose up -d` |

## Synology in Kürze

Ausführlich mit Bildern: **[Anleitung für Synology](docs/synology/anleitung.de.md)**.

1. **Container Manager** im Paket-Zentrum installieren (einmalig).
2. `nas4webtrees-….spk` unter [Releases](https://github.com/thobgg/nas4webtrees/releases) herunterladen.
3. Paket-Zentrum → *Manuelle Installation* → Datei wählen → Hinweis auf Drittanbieter bestätigen → Assistent
   ausfüllen (Name des Stammbaums, Administrator, Port, Freigabe für die Sicherung).
4. webtrees über das DSM-Hauptmenü öffnen (*nas4webtrees*). Der Eintrag *nas4webtrees – Apps verbinden* führt
   zur Seite für die Apps.

## Schnellstart (Docker Compose)

```sh
mkdir webtrees && cd webtrees
curl -O https://raw.githubusercontent.com/thobgg/nas4webtrees/main/compose/docker-compose.yml
echo 'ein-langes-passwort' > webtrees_admin_password.txt   # erstes Admin-Passwort
# docker-compose.yml anpassen: Name, E-Mail, Port, Zeitzone
docker compose up -d
```

Dann `http://<deine-nas>:8095` öffnen. Ohne `WT_USER`/`WT_EMAIL`/`WT_PASS` erscheint stattdessen
der Einrichtungsassistent von webtrees — dort *SQLite* wählen.

Alle Einstellungen stehen in der [englischen Anleitung](README.md#settings).

## Zugriff von unterwegs

Den Reverse Proxy der NAS davorschalten (Synology: *Systemsteuerung → Anmeldeportal → Erweitert →
Reverse Proxy*), außen HTTPS, innen `http://localhost:8095`. Das Image wertet
`X-Forwarded-Proto` aus, webtrees erzeugt dann `https://`-Links.

## Apps verbinden

In webtrees anmelden, im Menü **App** öffnen und den zwei Schritten dort folgen. Mehr dazu bei
[api4webtrees](https://github.com/thobgg/api4webtrees/blob/main/README.de.md).

## Kein offizielles webtrees-Projekt

nas4webtrees ist ein unabhängiges Gemeinschaftsprojekt, das webtrees für NAS-Geräte verpackt. Es
gehört nicht zum webtrees-Projekt und wird von ihm nicht unterstützt. Zu webtrees selbst:
[webtrees.net](https://webtrees.net/).

## Lizenz

GPL-3.0-or-later, wie webtrees und api4webtrees. webtrees ist © das webtrees-Entwicklerteam;
dieses Projekt verpackt es nur.
