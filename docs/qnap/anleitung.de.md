# nas4webtrees auf einer QNAP – Schritt für Schritt

Für QNAP mit QTS 5.x oder QuTS hero und **Container Station 3**. Rechne mit einer Viertelstunde. Du
brauchst keinen Datenbank-Server; alles läuft in einem Container. Die Bezeichnungen unten stammen aus
der englischen Oberfläche.

nas4webtrees ist ein Gemeinschaftsprojekt und kein offizieller Teil von webtrees.

## 1. Voraussetzungen

- **Container Station** aus dem *App Center* installieren (einmalig). Dabei entsteht der freigegebene
  Ordner `Container`.
- Internet während der Installation (das Image hat einige hundert MB).

## 2. Ordner anlegen

In der *File Station* im Ordner `Container` einen Ordner `nas4webtrees` anlegen, darin die beiden
Ordner `webtrees` und `backup`.

## 3. Installieren

*Container Station* → **Applications** → **Create**:

1. **Application name:** `nas4webtrees`.
2. Diesen Text einfügen – nur mit Leerzeichen eingerückt, Tabulatoren lehnt Container Station ab:

```yaml
services:
  webtrees:
    image: ghcr.io/thobgg/nas4webtrees:latest
    container_name: webtrees
    restart: unless-stopped
    ports:
      - "8095:80"
    volumes:
      - /share/Container/nas4webtrees/webtrees:/webtrees
      - /share/Container/nas4webtrees/backup:/backup
    environment:
      TZ: Europe/Berlin
```

3. **Validate** (optional) → **Create**.

## 4. Einrichten im Browser

Im Browser `http://<Adresse deiner QNAP>:8095` öffnen. Es erscheint **„Willkommen bei webtrees“**:

- Name des Stammbaums, dein Benutzername, dein Name, E-Mail, Passwort (zweimal).
- Den Haken **„Stammbaum nur für angemeldete Benutzer“** für einen Familien-Stammbaum drin lassen.
- **Stammbaum einrichten** – nach einem Moment erscheint die Anmeldung von webtrees.

Fragt die Seite nach einem **Einrichtungscode**, kommst du nicht aus dem Heimnetz. Der Code steht im
Protokoll des Containers (Abschnitt 7).

## 5. Die Apps verbinden

In webtrees erscheint oben ein Hinweis mit **wtWin einrichten** (am Handy: **App einrichten**). Auf der
Seite „App“ zuerst wtWin herunterladen und installieren, dann **Mit wtWin verbinden** klicken – wtWin
übernimmt Adresse und Anmeldung von selbst. Fürs Handy den QR-Code mit wtAnd scannen. Mehr dazu in der
[Synology-Anleitung, Abschnitt 7](../synology/anleitung.de.md#7-die-apps-verbinden).

## 6. Sicherung und Updates

- **Sicherung:** Jede Nacht um 3 Uhr landen in `Container/nas4webtrees/backup` jeder Stammbaum als
  GEDCOM-Datei, die Datenbank und die Fotos. Nimm den Ordner in deine Datensicherung auf (Hybrid Backup Sync).
- **Eigenen Stammbaum übernehmen:** in webtrees unter *Verwaltung → Stammbäume → GEDCOM-Datei
  importieren*, oder die `.ged`-Datei in `backup/import` legen und den Container einmal neu starten.
- **webtrees** aktualisierst du in webtrees selbst unter *Verwaltung → Aktualisierung*.
- **nas4webtrees** (Umgebung und api4webtrees): *Container Station* → **Applications** → nas4webtrees
  auswählen → Pfeil neben **Edit** → **Recreate** → Haken bei „Try pulling the image from the registry
  before creating the container“ → **Update**. Stammbaum und Konten bleiben erhalten, weil alles in den
  beiden Ordnern liegt.

## 7. Wenn etwas nicht klappt

- **Protokoll:** *Container Station* → **Containers** → `webtrees` → Reiter **Logs**. Die Zeilen mit
  `[nas4webtrees]` beschreiben jeden Schritt, dort steht auch der Einrichtungscode.
- **Port belegt:** `8095:80` zum Beispiel in `8096:80` ändern (8080 und 443 nutzt meist QTS selbst).
- **Fragen und Fehler:** [Issues auf GitHub](https://github.com/thobgg/nas4webtrees/issues)
