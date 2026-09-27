# nas4webtrees auf TrueNAS – Schritt für Schritt

Für TrueNAS Community Edition / SCALE ab 25.04. Rechne mit einer Viertelstunde. Du brauchst keinen
Datenbank-Server; alles läuft in einem Container. Die Bezeichnungen unten stammen aus der englischen
Oberfläche von TrueNAS.

nas4webtrees ist ein Gemeinschaftsprojekt und kein offizieller Teil von webtrees.

## 1. Voraussetzungen

- TrueNAS 25.04 oder neuer mit eingerichteten **Apps**. Beim allerersten Mal fragt TrueNAS unter
  *Apps*, auf welchem Pool die Apps liegen sollen – einfach den Pool wählen.
- Internet während der Installation (das Image hat einige hundert MB).

## 2. Ordner anlegen

*Datasets* → deinen Pool wählen → **Add Dataset**:

1. Name `nas4webtrees`, **Dataset Preset: Apps** → *Save*.
2. Darin zwei weitere Datasets, ebenfalls mit Preset **Apps**: `webtrees` und `backup`.

Die Vorlage „Apps“ gibt dem App-Benutzer von TrueNAS (Nummer 568) Schreibrechte. Lege die Ordner
nicht unter `ix-apps` an.

## 3. Installieren

*Apps* → **Discover** → oben rechts das Menü **⋮** → **Install via YAML**.

- **Name:** `nas4webtrees` (nur Kleinbuchstaben und Ziffern).
- **Custom Config:** den folgenden Text einfügen und `tank` zweimal durch den Namen deines Pools ersetzen:

```yaml
services:
  webtrees:
    image: ghcr.io/thobgg/nas4webtrees:latest
    restart: unless-stopped
    ports:
      - "8095:80"
    volumes:
      - /mnt/tank/nas4webtrees/webtrees:/webtrees
      - /mnt/tank/nas4webtrees/backup:/backup
    environment:
      TZ: Europe/Berlin
      PUID: "568"
      PGID: "568"
```

**Save**. Nach ein bis zwei Minuten steht die App unter *Apps → Installed* auf **Running**.

`PUID` und `PGID` 568 sorgen dafür, dass die Dateien dem App-Benutzer gehören – passend zur Vorlage
„Apps“ aus Schritt 2. Ohne sie darf webtrees nicht in die Ordner schreiben.

## 4. Einrichten im Browser

Im Browser `http://<Adresse deines TrueNAS>:8095` öffnen. Es erscheint **„Willkommen bei webtrees“**:

- Name des Stammbaums, dein Benutzername, dein Name, E-Mail, Passwort (zweimal).
- Den Haken **„Stammbaum nur für angemeldete Benutzer“** für einen Familien-Stammbaum drin lassen.
- **Stammbaum einrichten** – nach einem Moment erscheint die Anmeldung von webtrees.

Fragt die Seite nach einem **Einrichtungscode**, kommst du nicht aus dem Heimnetz. Der Code steht im
Protokoll des Containers (Abschnitt 7).

## 5. Die Apps verbinden

In webtrees erscheint oben ein Hinweis mit **wtWin einrichten** (am Handy: **App einrichten**). Auf der
Seite „App“ zuerst wtWin herunterladen und installieren, dann **Mit wtWin verbinden** klicken – wtWin
übernimmt Adresse und Anmeldung von selbst. Fürs Handy den QR-Code mit wtAnd scannen. Mehr dazu in der
[Synology-Anleitung, Abschnitt 7](../synology/anleitung.de.md#7-die-apps-verbinden) – dort ist es
genauso.

## 6. Sicherung und Updates

- **Sicherung:** Jede Nacht um 3 Uhr landen im Dataset `backup` jeder Stammbaum als GEDCOM-Datei, die
  Datenbank und die Fotos. Nimm das Dataset in deine Snapshots oder Replikation auf.
- **Eigenen Stammbaum übernehmen:** in webtrees unter *Verwaltung → Stammbäume → GEDCOM-Datei
  importieren*, oder die `.ged`-Datei in `backup/import` legen und die App einmal neu starten.
- **webtrees** aktualisierst du in webtrees selbst unter *Verwaltung → Aktualisierung*.
- **nas4webtrees** (Umgebung und api4webtrees): *Apps → Installed* → nas4webtrees → im Kasten
  *Application Info* das Menü **⋮** → **Update**, sobald TrueNAS ein neues Image meldet. Stammbaum und
  Konten bleiben erhalten.

## 7. Wenn etwas nicht klappt

- **Protokoll:** *Apps → Installed* → nas4webtrees → Kasten **Workloads** → Symbol **View Logs** →
  *Connect*. Die Zeilen mit `[nas4webtrees]` beschreiben jeden Schritt, dort steht auch der
  Einrichtungscode.
- **„webtrees darf nicht schreiben“** im Protokoll: Die Datasets haben nicht die Vorlage „Apps“, oder
  `PUID`/`PGID` fehlen. Schritt 2 und 3 prüfen.
- **Port belegt:** in der YAML `8095:80` zum Beispiel in `8096:80` ändern.
- **Fragen und Fehler:** [Issues auf GitHub](https://github.com/thobgg/nas4webtrees/issues)
