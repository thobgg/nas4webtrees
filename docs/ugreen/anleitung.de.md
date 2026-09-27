# nas4webtrees auf einer UGREEN-NAS – Schritt für Schritt

Für UGREEN-Geräte mit UGOS Pro. Rechne mit einer Viertelstunde. Du brauchst keinen Datenbank-Server;
alles läuft in einem Container. Die Bezeichnungen unten stammen aus der englischen Oberfläche.

nas4webtrees ist ein Gemeinschaftsprojekt und kein offizieller Teil von webtrees.

## 1. Voraussetzungen

- **Docker** aus dem *App Center* installieren (einmalig). Dabei entsteht der freigegebene Ordner
  `docker`.
- Deinem Konto im *File Manager* Lese- und Schreibrechte auf den Ordner `docker` geben, falls es sie
  noch nicht hat.
- Internet während der Installation (das Image hat einige hundert MB).

## 2. Installieren

*Docker* → links **Project** → **Create**:

1. **Project name:** `nas4webtrees`.
2. **Storage path:** **Create folder** → `nas4webtrees` → *Confirm*, den neuen Ordner auswählen → *Confirm*.
3. In **Compose configuration** diesen Text einfügen – er kann genau so bleiben:

```yaml
services:
  webtrees:
    image: ghcr.io/thobgg/nas4webtrees:latest
    container_name: webtrees
    restart: unless-stopped
    ports:
      - "8095:80"
    volumes:
      - ./webtrees:/webtrees
      - ./backup:/backup
    environment:
      TZ: Europe/Berlin
```

4. Den Haken **Run immediately after creation** setzen → **Deploy**.

Die beiden Ordner `webtrees` (Programm und Daten) und `backup` (Sicherung) entstehen von selbst unter
`docker/nas4webtrees`.

## 3. Einrichten im Browser

Im Browser `http://<Adresse deiner NAS>:8095` öffnen. Es erscheint **„Willkommen bei webtrees“**:

- Name des Stammbaums, dein Benutzername, dein Name, E-Mail, Passwort (zweimal).
- Den Haken **„Stammbaum nur für angemeldete Benutzer“** für einen Familien-Stammbaum drin lassen.
- **Stammbaum einrichten** – nach einem Moment erscheint die Anmeldung von webtrees.

Fragt die Seite nach einem **Einrichtungscode**, kommst du nicht aus dem Heimnetz. Der Code steht im
Protokoll des Containers (Abschnitt 6).

## 4. Die Apps verbinden

In webtrees erscheint oben ein Hinweis mit **wtWin einrichten** (am Handy: **App einrichten**). Auf der
Seite „App“ zuerst wtWin herunterladen und installieren, dann **Mit wtWin verbinden** klicken – wtWin
übernimmt Adresse und Anmeldung von selbst. Fürs Handy den QR-Code mit wtAnd scannen. Mehr dazu in der
[Synology-Anleitung, Abschnitt 7](../synology/anleitung.de.md#7-die-apps-verbinden).

## 5. Sicherung und Updates

- **Sicherung:** Jede Nacht um 3 Uhr landen in `docker/nas4webtrees/backup` jeder Stammbaum als
  GEDCOM-Datei, die Datenbank und die Fotos. Nimm den Ordner in deine Datensicherung auf.
- **Eigenen Stammbaum übernehmen:** in webtrees unter *Verwaltung → Stammbäume → GEDCOM-Datei
  importieren*, oder die `.ged`-Datei in `backup/import` legen und den Container einmal neu starten.
- **webtrees** aktualisierst du in webtrees selbst unter *Verwaltung → Aktualisierung*.
- **nas4webtrees** (Umgebung und api4webtrees): *Docker* → **Project** → nas4webtrees; meldet UGOS ein
  neues Image, das Update dort starten. Stammbaum und Konten bleiben erhalten.

## 6. Wenn etwas nicht klappt

- **Protokoll:** *Docker* → **Container** → `webtrees` → **Log**. Die Zeilen mit `[nas4webtrees]`
  beschreiben jeden Schritt, dort steht auch der Einrichtungscode.
- **Dateien lassen sich über das Netzwerk nicht bearbeiten:** Sie gehören dem Webserver im Container.
  Wer das ändern will, trägt unter `environment` zusätzlich `PUID` und `PGID` mit den Nummern seines
  Kontos ein.
- **Port belegt:** `8095:80` zum Beispiel in `8096:80` ändern.
- **Fragen und Fehler:** [Issues auf GitHub](https://github.com/thobgg/nas4webtrees/issues)
