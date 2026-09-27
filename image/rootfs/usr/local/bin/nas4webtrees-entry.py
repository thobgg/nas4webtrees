#!/usr/bin/env python3
"""Einstieg des Images nas4webtrees.

Bereitet vor, startet einen Nebenprozess und ersetzt sich dann per exec durch Apache.

- Programm: Beim ersten Start die offizielle, unveränderte webtrees-Release-Datei nach
  /webtrees entpacken. Eine vorhandene Installation wird nie angefasst — sie gehört webtrees und
  wird über dessen eigene Aktualisierung gepflegt; das übersteht jedes neue Image. api4webtrees
  wird installiert, wenn es fehlt, und ersetzt, wenn das Image eine neuere Fassung mitbringt.
- Einrichtung: Mit Angaben (Umgebung WT_USER, WT_EMAIL, WT_PASS_FILE … oder /config/setup.json)
  füllt der Nebenprozess den Einrichtungsassistenten von webtrees selbst aus — SQLite, sofern nichts
  anderes verlangt ist; ein Passwort aus setup.json wird danach aus der Datei gelöscht. Ohne Angaben
  erscheint im Browser eine eigene, kurze Einrichtungsseite (/opt/nas4webtrees/setup): Stammbaum,
  Konto, privat ja/nein — keine Datenbankfrage. Ihre Angaben verarbeitet der Nebenprozess genauso.
- Wiederherstellung: Neuinstallation neben einer vorhandenen Sicherung übernimmt deren letzten
  Stand, aber nie über eine vorhandene Datenbank.
- Ersteinrichtung: Zeitzone, ein leerer Stammbaum, optional GEDCOM-Import aus /backup/import.
- Nächtliche Sicherung nach /backup: GEDCOM je Baum (unter festem Namen plus Verlauf), eine
  konsistente Kopie der SQLite-Datenbank und ein Spiegel der Mediendateien.
"""
import datetime
import glob
import json
import os
import pwd
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ENV = os.environ
ROOT = ENV.get("WEBTREES_ROOT", "/webtrees")
DATA = os.path.join(ROOT, "data")
CONFIG = os.path.join(DATA, "config.ini.php")
STATE = os.path.join(DATA, ".nas4webtrees")  # Merkzettel, liegt bei den Daten
BUNDLE = "/opt/nas4webtrees"
CONFIG_DIR = ENV.get("NAS4WEBTREES_CONFIG", "/config")
SETUP_FILE = os.path.join(CONFIG_DIR, "setup.json")
BACKUP_ROOT = ENV.get("BACKUP_ROOT", "/backup")
BACKUP_DIR = os.path.join(BACKUP_ROOT, ENV.get("BACKUP_SUBDIR", ""))
BACKUP_HOUR = int(ENV.get("BACKUP_HOUR", "3"))
KEEP_GEDCOM = int(ENV.get("BACKUP_KEEP_GEDCOM", "30"))
KEEP_DB = int(ENV.get("BACKUP_KEEP_DB", "7"))
NO_TARGET_MARK = ".nas4webtrees-no-target"  # vom Synology-Paket, wenn die Freigabe fehlt
TBLPFX = ENV.get("DB_PREFIX", "wt_")
# Einrichtung im Browser: Apache leitet um, solange SETUP_PAGE existiert (webtrees.conf).
RUN_DIR = "/run/nas4webtrees"
SETUP_PAGE = os.path.join(RUN_DIR, "setup-page")
SETUP_REQUEST = os.path.join(RUN_DIR, "setup-request.json")
SETUP_ERROR = os.path.join(RUN_DIR, "setup-error")
SETUP_CODE = os.path.join(RUN_DIR, "setup-code")
SETUP_DEFAULTS = os.path.join(RUN_DIR, "setup-defaults.json")


def log(msg):
    print(f"[nas4webtrees] {msg}", file=sys.stderr, flush=True)


def truthy(v, default=False):
    if v is None or v == "":
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


# ── Einstellungen: Umgebung vor setup.json ───────────────────────────────────────────────


def load_setup_file():
    try:
        with open(SETUP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log(f"WARNUNG: {SETUP_FILE} unlesbar ({e})")
        return {}


def read_secret(name):
    """WT_PASS oder WT_PASS_FILE (Docker-Secrets-Konvention)."""
    if ENV.get(name):
        return ENV[name]
    path = ENV.get(name + "_FILE")
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError as e:
            log(f"WARNUNG: {name}_FILE unlesbar ({e})")
    return ""


def settings():
    f = load_setup_file()
    s = {
        "user": ENV.get("WT_USER") or f.get("user", ""),
        "name": ENV.get("WT_NAME") or f.get("name", ""),
        "email": ENV.get("WT_EMAIL") or f.get("email", ""),
        "password": read_secret("WT_PASS") or f.get("password", ""),
        "lang": ENV.get("WT_LANG") or f.get("lang") or "en-US",
        "tree": ENV.get("WT_TREE") or f.get("tree") or "tree1",
        "tree_title": ENV.get("WT_TREE_TITLE") or f.get("tree_title") or "My family tree",
        "restore": truthy(ENV.get("WT_RESTORE"), f.get("restore", True)),
        # Familien-Stammbaum: nur für angemeldete Benutzer, Konten legt der Administrator an.
        "private": truthy(ENV.get("WT_PRIVATE"), f.get("private", True)),
        "dbtype": ENV.get("DB_TYPE", "sqlite"),
        "dbhost": ENV.get("DB_HOST", ""),
        "dbport": ENV.get("DB_PORT", ""),
        "dbuser": ENV.get("DB_USER", ""),
        "dbpass": read_secret("DB_PASS"),
        "dbname": ENV.get("DB_NAME", "webtrees"),
    }
    s["name"] = s["name"] or s["user"]
    s["from_file"] = bool(f)
    return s


def db_file(s):
    return os.path.join(DATA, s["dbname"] + ".sqlite")


# ── Hilfen ───────────────────────────────────────────────────────────────────────────────


def www():
    return pwd.getpwnam("www-data")


def chown_www(path):
    u = www()
    for dirpath, dirs, files in os.walk(path):
        os.chown(dirpath, u.pw_uid, u.pw_gid)
        for n in dirs + files:
            os.lchown(os.path.join(dirpath, n), u.pw_uid, u.pw_gid)


def wt(*args, cwd=None, check=True):
    """webtrees-Kommandozeile als www-data."""
    u = www()
    r = subprocess.run(
        ["php", os.path.join(ROOT, "index.php"), "--no-interaction", *args],
        cwd=cwd or ROOT, user=u.pw_uid, group=u.pw_gid, capture_output=True, text=True,
    )
    if check and r.returncode != 0:
        raise RuntimeError(f"webtrees {' '.join(args)}: {r.stdout.strip()} {r.stderr.strip()}")
    return r


def db_query(s, sql, params=()):
    con = sqlite3.connect(f"file:{db_file(s)}?mode=ro", uri=True, timeout=30)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def trees(s):
    if s["dbtype"] == "sqlite":
        return [r[0] for r in db_query(s, f"SELECT gedcom_name FROM {TBLPFX}gedcom WHERE gedcom_id > 0 ORDER BY gedcom_id")]
    # MySQL/PostgreSQL: über die Kommandozeile (Tabelle mit Rahmen, erste Spalte = Name)
    out = wt("tree-list").stdout
    return [m.group(1) for m in re.finditer(r"^\|\s*(\S+)\s*\|", out, re.M) if m.group(1).lower() != "name"]


def tree_is_empty(s, name):
    """Leer heißt: keine Familie und höchstens der Platzhalter, den webtrees in jeden neuen Baum
    legt („John /DOE/“ mit dem Hinweis, ihn durch eigene Angaben zu ersetzen)."""
    if s["dbtype"] != "sqlite":
        return False
    fams = db_query(s, f"SELECT COUNT(*) FROM {TBLPFX}families f JOIN {TBLPFX}gedcom g ON g.gedcom_id = f.f_file"
                       " WHERE g.gedcom_name = ?", (name,))[0][0]
    indis = db_query(s, f"SELECT i.i_gedcom FROM {TBLPFX}individuals i JOIN {TBLPFX}gedcom g ON g.gedcom_id = i.i_file"
                        " WHERE g.gedcom_name = ? LIMIT 2", (name,))
    if fams or len(indis) > 1:
        return False
    return not indis or "replace their details with your own" in indis[0][0]


def state_get(key):
    try:
        with open(os.path.join(STATE, key), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def state_set(key, value):
    os.makedirs(STATE, exist_ok=True)
    with open(os.path.join(STATE, key), "w", encoding="utf-8") as f:
        f.write(str(value))


def set_config_line(key, value):
    with open(CONFIG, encoding="utf-8") as f:
        lines = f.readlines()
    new = f'{key}="{value}"\n'
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            if line == new:
                return
            lines[i] = new
            break
    else:
        lines.append(new)
    with open(CONFIG, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ── Vor dem Start (als root, vor Apache) ─────────────────────────────────────────────────


def apply_timezone():
    tz = ENV.get("TZ", "")
    if not tz:
        try:
            with open(os.path.join(CONFIG_DIR, "timezone"), encoding="utf-8") as f:
                tz = f.read().strip()
        except OSError:
            tz = ""
    if tz:
        ENV["TZ"] = tz
        time.tzset()
        zone = os.path.join("/usr/share/zoneinfo", tz)
        if os.path.isfile(zone):
            try:
                os.remove("/etc/localtime")
            except FileNotFoundError:
                pass
            os.symlink(zone, "/etc/localtime")
    return tz


def apply_ids():
    """PUID/PGID (Unraid und Co.): www-data auf die gewünschten IDs setzen."""
    uid, gid = ENV.get("PUID"), ENV.get("PGID")
    if gid and gid.isdigit():
        subprocess.run(["groupmod", "-o", "-g", gid, "www-data"], check=False)
    if uid and uid.isdigit():
        subprocess.run(["usermod", "-o", "-u", uid, "www-data"], check=False, capture_output=True)


def apply_php_ini(tz):
    vals = {
        "memory_limit": ENV.get("PHP_MEMORY_LIMIT", "1024M"),
        "max_execution_time": ENV.get("PHP_MAX_EXECUTION_TIME", "90"),
        "post_max_size": ENV.get("PHP_POST_MAX_SIZE", "64M"),
        "upload_max_filesize": ENV.get("PHP_UPLOAD_MAX_FILE_SIZE", "64M"),
        # https://webtrees.net/admin/performance/
        "opcache.enable": "1",
        "opcache.revalidate_freq": "60",
        "opcache.revalidate_path": "0",
    }
    if tz:
        vals["date.timezone"] = tz
    with open("/usr/local/etc/php/conf.d/zz-nas4webtrees.ini", "w", encoding="utf-8") as f:
        f.write("; von nas4webtrees-entry.py bei jedem Start erzeugt\n")
        f.writelines(f"{k} = {v}\n" for k, v in vals.items())


def ensure_webtrees():
    """Offizielle webtrees-Fassung entpacken, wenn noch keine da ist."""
    if os.path.isfile(os.path.join(ROOT, "index.php")):
        return
    log(f"Erstinstallation: offizielle webtrees-Release-Datei {ENV.get('WEBTREES_BUNDLED_VERSION', '')} wird entpackt")
    os.makedirs(ROOT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".unzip-", dir=ROOT)
    with zipfile.ZipFile(os.path.join(BUNDLE, "webtrees.zip")) as z:
        z.extractall(tmp)
    src = os.path.join(tmp, "webtrees")
    for name in os.listdir(src):
        dst = os.path.join(ROOT, name)
        if os.path.isdir(dst):
            # data/ kann durch eine Wiederherstellung schon gefüllt sein — nur Fehlendes ergänzen.
            shutil.copytree(os.path.join(src, name), dst, dirs_exist_ok=True)
        else:
            shutil.move(os.path.join(src, name), dst)
    shutil.rmtree(tmp)
    # webtrees aktualisiert sich selbst und muss dafür seine eigenen Dateien schreiben dürfen.
    chown_www(ROOT)


def module_version(folder):
    for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not fn.endswith(".php"):
            continue
        try:
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                m = re.search(r"function customModuleVersion\(\)[^{]*\{\s*return '([^']+)'", f.read())
        except OSError:
            continue
        if m:
            try:
                return tuple(int(x) for x in m.group(1).split("."))
            except ValueError:
                return ()
    return ()


def ensure_modules():
    """Mitgelieferte Module installieren oder auf die mitgelieferte Fassung heben — nie zurück."""
    bundled = os.path.join(BUNDLE, "modules")
    for name in sorted(os.listdir(bundled)):
        src = os.path.join(bundled, name)
        dst = os.path.join(ROOT, "modules_v4", name)
        new, cur = module_version(src), module_version(dst)
        if os.path.isdir(dst):
            if cur and cur >= new:
                continue
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
        chown_www(dst)
        v = lambda t: ".".join(map(str, t)) or "?"  # noqa: E731
        log(f"Modul {name} {v(new)} " + (f"(vorher {v(cur)})" if cur else "installiert"))


def fix_ownership():
    """Nach geändertem PUID/PGID gehören Programm und Daten sonst dem alten Konto."""
    u = www()
    st = os.stat(ROOT)
    if (st.st_uid, st.st_gid) != (u.pw_uid, u.pw_gid):
        log(f"Besitzer von {ROOT} wird auf {u.pw_uid}:{u.pw_gid} gesetzt")
        chown_www(ROOT)


def can_write(uid, gid, path):
    probe = os.path.join(path, ".nas4webtrees-probe")
    r = subprocess.run(["setpriv", f"--reuid={uid}", f"--regid={gid}", "--clear-groups",
                        "sh", "-c", f"touch '{probe}' && rm -f '{probe}'"], capture_output=True)
    return r.returncode == 0


def write_gid_hint():
    """Gruppe, die auf dem Gerät schreiben darf (Synology: administrators, vom Paket ermittelt)."""
    v = ENV.get("WRITE_GID", "")
    if not v:
        try:
            with open(os.path.join(CONFIG_DIR, "write-gid"), encoding="utf-8") as f:
                v = f.read().strip()
        except OSError:
            v = ""
    return int(v) if v.isdigit() else None


def ensure_writable():
    """webtrees muss in seinen eigenen Dateien schreiben dürfen — sonst scheitert schon die
    Einrichtung. Auf Synology entscheidet die ACL der Freigabe, nicht der Besitzer: Dort dürfen
    nur administrators und ContainerManager schreiben, www-data fällt unter „everyone: lesen“.

    Reihenfolge: (A) mit der Gruppe laufen, die laut Gerät schreiben darf; (B) sonst die
    Linux-Rechte auf dem eigenen Ordner setzen. Beides nur, wenn nötig.
    """
    u = www()
    paths = [ROOT, DATA]
    if all(can_write(u.pw_uid, u.pw_gid, p) for p in paths):
        return
    gid = write_gid_hint()
    if gid is not None and gid != u.pw_gid and all(can_write(u.pw_uid, gid, p) for p in paths):
        subprocess.run(["groupmod", "-o", "-g", str(gid), "www-data"], check=False)
        chown_www(ROOT)
        log(f"Schreibrechte über die Gruppe {gid} (Rechteliste des Geräts)")
        return
    subprocess.run(["chmod", "-R", "u+rwX,g+rwX", ROOT], check=False)
    if all(can_write(u.pw_uid, u.pw_gid, p) for p in paths):
        log(f"Schreibrechte über Linux-Rechte auf {ROOT} gesetzt")
        return
    log(f"FEHLER: webtrees darf in {ROOT} nicht schreiben — Rechte der Freigabe prüfen "
        "(der Benutzer des Containers braucht Lesen und Schreiben)")


def restore_from_backup(s):
    """Neuinstallation neben einer vorhandenen Sicherung: letzten Stand übernehmen.

    Nie über eine vorhandene Datenbank — lieber einmal zu wenig wiederherstellen als einen
    laufenden Stammbaum mit einer älteren Sicherung zu überschreiben.
    """
    if s["dbtype"] != "sqlite" or os.path.exists(db_file(s)) or os.path.isfile(CONFIG):
        return False
    snaps = sorted(glob.glob(os.path.join(BACKUP_DIR, "database", f"{s['dbname']}_*.sqlite")))
    if not snaps:
        return False
    log(f"Wiederherstellung aus {snaps[-1]}")
    os.makedirs(DATA, exist_ok=True)
    shutil.copy2(snaps[-1], db_file(s))
    saved_cfg = os.path.join(BACKUP_DIR, "database", "config.ini.php")
    if os.path.isfile(saved_cfg):
        shutil.copy2(saved_cfg, CONFIG)
    else:
        with open(CONFIG, "w", encoding="utf-8") as f:
            f.write('; <?php return; ?> DO NOT DELETE THIS LINE\n'
                    'dbtype="sqlite"\ndbhost=""\ndbport=""\ndbuser=""\ndbpass=""\n'
                    f'dbname="{s["dbname"]}"\ntblpfx="{TBLPFX}"\nbase_url=""\nrewrite_urls="0"\n')
    media = os.path.join(BACKUP_DIR, "media")
    if os.path.isdir(media):
        shutil.copytree(media, os.path.join(DATA, "media"), dirs_exist_ok=True)
    state_set("initialized", "restored " + os.path.basename(snaps[-1]))
    return True


def apply_config_env():
    """BASE_URL und PRETTY_URLS bei jedem Start übernehmen — nur wenn ausdrücklich gesetzt."""
    if not os.path.isfile(CONFIG):
        return
    if "BASE_URL" in ENV:
        set_config_line("base_url", ENV["BASE_URL"])
    if "PRETTY_URLS" in ENV:
        set_config_line("rewrite_urls", "1" if truthy(ENV["PRETTY_URLS"]) else "0")


# ── Nebenprozess (neben Apache) ──────────────────────────────────────────────────────────


def wait_http(timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen("http://127.0.0.1/public/css/webtrees.min.css", timeout=5)
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run_setup_wizard(s):
    """Den Einrichtungsassistenten von webtrees ausfüllen — derselbe Weg wie im Browser."""
    fields = {
        "lang": s["lang"], "tblpfx": TBLPFX, "baseurl": ENV.get("BASE_URL", ""),
        "dbtype": s["dbtype"], "dbhost": s["dbhost"], "dbport": s["dbport"],
        "dbuser": s["dbuser"], "dbpass": s["dbpass"], "dbname": s["dbname"],
        "wtname": s["name"], "wtuser": s["user"], "wtpass": s["password"], "wtemail": s["email"],
        "step": "6",
    }
    opener = urllib.request.build_opener(_NoRedirect)
    for attempt in range(10):
        try:
            code = opener.open("http://127.0.0.1/", urllib.parse.urlencode(fields).encode(), timeout=120).status
        except urllib.error.HTTPError as e:
            code = e.code
        except (urllib.error.URLError, OSError):
            code = 0
        if code in (200, 302) and os.path.isfile(CONFIG):
            log(f"Einrichtung: Konto {s['user']}, Datenbank {s['dbtype']}")
            return True
        time.sleep(1 + attempt)
    log("FEHLER: automatische Einrichtung fehlgeschlagen — der Assistent steht im Browser bereit")
    return False


def has_setup_data(s):
    return bool(s["user"] and s["email"] and s["password"])


def enable_setup_page(s):
    """Eigene Einrichtungsseite einschalten: nur ohne Einrichtung, ohne Vorgaben und mit SQLite.

    Die Seite (PHP, läuft als www-data) legt ihre Angaben in RUN_DIR ab; der Nebenprozess (root)
    verarbeitet sie. Der Code ist nur für Aufrufe von außerhalb des Heimnetzes nötig.
    """
    shutil.rmtree(RUN_DIR, ignore_errors=True)
    if os.path.isfile(CONFIG) or has_setup_data(s) or s["dbtype"] != "sqlite":
        return False
    u = www()
    os.makedirs(RUN_DIR, mode=0o750)
    os.chown(RUN_DIR, u.pw_uid, u.pw_gid)
    code = f"{int.from_bytes(os.urandom(4), 'big') % 1000000:06d}"
    defaults = {"lang": ENV.get("WT_LANG", ""), "tree_title": ENV.get("WT_TREE_TITLE", "")}
    for path, content in ((SETUP_CODE, code), (SETUP_DEFAULTS, json.dumps(defaults, ensure_ascii=False)), (SETUP_PAGE, "")):
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(path, 0o640)
        os.chown(path, 0, u.pw_gid)
    log("Einrichtung im Browser: webtrees aufrufen und die kurze Seite ausfüllen")
    log(f"Einrichtungscode (nur nötig, wenn der Aufruf nicht aus dem Heimnetz kommt): {code}")
    return True


def await_setup_page(s):
    """Auf die Angaben der Einrichtungsseite warten und webtrees damit einrichten.

    Gibt die Einstellungen mit den Angaben zurück (Stammbaumname, privat, Sprache gelten auch für
    die Ersteinrichtung). Bei einem Fehler bekommt die Seite eine Meldung und zeigt das Formular erneut.
    """
    while not os.path.isfile(CONFIG):
        if not os.path.isfile(SETUP_REQUEST):
            time.sleep(1)
            continue
        try:
            with open(SETUP_REQUEST, encoding="utf-8") as f:
                req = json.load(f)
        except (OSError, ValueError):
            time.sleep(1)  # die Seite schreibt noch
            continue
        s2 = dict(s)
        for key in ("user", "name", "email", "password", "tree_title", "lang"):
            if req.get(key):
                s2[key] = str(req[key])
        s2["private"] = bool(req.get("private", True))
        if run_setup_wizard(s2):
            os.remove(SETUP_REQUEST)
            shutil.rmtree(RUN_DIR, ignore_errors=True)
            s2["password"] = ""
            return s2
        with open(SETUP_ERROR, "w", encoding="utf-8") as f:
            f.write("webtrees hat die Einrichtung abgelehnt – Details im Protokoll des Containers.")
        os.chmod(SETUP_ERROR, 0o644)
        os.remove(SETUP_REQUEST)
    return s


def forget_password():
    """Passwort aus setup.json löschen; die Datei behält ihren Besitzer (Synology-Paketnutzer)."""
    f = load_setup_file()
    if not f.get("password"):
        return
    f.pop("password")
    st = os.stat(SETUP_FILE)
    tmp = SETUP_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(f, fh, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.chown(tmp, st.st_uid, st.st_gid)
    os.replace(tmp, SETUP_FILE)
    log("Startpasswort aus setup.json entfernt")


def make_private(s, name):
    """„Anmeldung erforderlich“ für diesen Baum und kein Konto-Beantragen für Besucher.

    webtrees 2.2.6 hält die Einstellung in der Spalte gedcom.private; der alte Weg über
    setPreference('REQUIRE_AUTHENTICATION') ist veraltet und änderte alle Bäume auf einmal.
    Wer sich registriert, tut das für einen Baum — bei einem privaten Baum geht das ohnehin nicht,
    der Administrator legt die Konten an (Verwaltung → Benutzer).
    """
    if s["dbtype"] == "sqlite":
        u = www()
        code = ("import sqlite3,sys; c=sqlite3.connect(sys.argv[1], timeout=30); "
                f"c.execute('UPDATE {TBLPFX}gedcom SET private=1 WHERE gedcom_name=?', (sys.argv[2],)); c.commit()")
        subprocess.run(["setpriv", f"--reuid={u.pw_uid}", f"--regid={u.pw_gid}", "--clear-groups",
                        "python3", "-c", code, db_file(s), name], check=True)
    else:
        wt("tree-setting", name, "REQUIRE_AUTHENTICATION", "1", check=False)
    wt("site-setting", "USE_REGISTRATION_MODULE", "0", check=False)
    log(f"Stammbaum {name}: nur für angemeldete Benutzer, kein Konto-Beantragen")


def first_run(s, tz):
    if state_get("initialized"):
        return
    if tz:
        wt("site-setting", "TIMEZONE", tz, check=False)
    # Sprache für Besucher und neue Konten; der Assistent setzt sie nur für den Administrator.
    wt("site-setting", "LANGUAGE", s["lang"], check=False)
    if not trees(s):
        wt("tree", s["tree"], "--create", f"--title={s['tree_title']}")
        wt("site-setting", "DEFAULT_GEDCOM", s["tree"], check=False)
        log(f"Stammbaum „{s['tree_title']}“ ({s['tree']}) angelegt")
        if s["private"]:
            make_private(s, s["tree"])
    state_set("initialized", datetime.datetime.now().isoformat(timespec="seconds"))


def backup_target_ok():
    return os.path.isdir(BACKUP_ROOT) and not os.path.exists(os.path.join(BACKUP_ROOT, NO_TARGET_MARK))


def import_waiting_gedcom(s):
    """Eine GEDCOM-Datei in /backup/import landet im ersten Baum — aber nur, wenn der leer ist."""
    inbox = os.path.join(BACKUP_DIR, "import")
    os.makedirs(inbox, exist_ok=True)
    files = sorted(f for f in glob.glob(os.path.join(inbox, "*")) if f.lower().endswith((".ged", ".gedcom")))
    names = trees(s)
    if not files or not names:
        return
    target = names[0]
    if not tree_is_empty(s, target):
        log(f"Import übersprungen: Baum {target} ist nicht leer ({os.path.basename(files[0])} bleibt liegen)")
        return
    src = files[0]
    u = www()
    tmp = tempfile.mkdtemp(prefix="nas4webtrees-import-")
    work = os.path.join(tmp, "import.ged")
    shutil.copy2(src, work)
    os.chown(tmp, u.pw_uid, u.pw_gid)
    os.chown(work, u.pw_uid, u.pw_gid)
    log(f"GEDCOM-Import {os.path.basename(src)} → {target}")
    r = wt("tree-import", target, work, check=False)
    shutil.rmtree(tmp, ignore_errors=True)
    if r.returncode == 0:
        done = os.path.join(inbox, "done")
        os.makedirs(done, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        shutil.move(src, os.path.join(done, f"{stamp}_{os.path.basename(src)}"))
        state_set("last-backup", 0)  # gleich sichern, damit gedcom/<baum>.ged den Import zeigt
        log("Import fertig")
    else:
        log(f"FEHLER beim Import: {r.stdout.strip()} {r.stderr.strip()}")


README = """nas4webtrees backup / Sicherung
===============================

gedcom/<tree>.ged          Latest state of each family tree as a GEDCOM file — any genealogy
                           program can open it. Renewed every night.
                           Aktueller Stand jedes Stammbaums als GEDCOM-Datei, jede Nacht neu.
gedcom/<tree>_<date>.ged   Older states (last {keep_ged}) / ältere Stände.
database/                  Complete copy of the webtrees database incl. users, settings and
                           pending changes (last {keep_db}) / vollständige Datenbank-Kopie.
media/                     Copy of all photos and documents / Kopie aller Fotos und Dokumente.
import/                    Put a GEDCOM file here and restart the container: it is imported
                           into the family tree while that is still empty.
                           GEDCOM-Datei hier hinein und neu starten: Import in den leeren Baum.

Restore: reinstall next to this folder — the latest state from database/ and media/ is taken
over automatically. Wiederherstellen: neu installieren, der letzte Stand wird übernommen.
"""


def prune(pattern, keep):
    for old in sorted(glob.glob(pattern))[:-keep]:
        os.remove(old)


def mirror_media():
    src = os.path.join(DATA, "media")
    dst = os.path.join(BACKUP_DIR, "media")
    n = 0
    for dirpath, _dirs, files in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out, exist_ok=True)
        for fn in files:
            a, b = os.path.join(dirpath, fn), os.path.join(out, fn)
            st = os.stat(a)
            try:
                bt = os.stat(b)
                if bt.st_size == st.st_size and int(bt.st_mtime) == int(st.st_mtime):
                    continue
            except FileNotFoundError:
                pass
            shutil.copy2(a, b)
            n += 1
    return n


def backup_once(s):
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    for sub in ("gedcom", "database", "media", "import"):
        os.makedirs(os.path.join(BACKUP_DIR, sub), exist_ok=True)
    with open(os.path.join(BACKUP_DIR, "README.txt"), "w", encoding="utf-8") as f:
        f.write(README.format(keep_ged=KEEP_GEDCOM, keep_db=KEEP_DB))

    report = []
    u = www()
    tmp = tempfile.mkdtemp(prefix="nas4webtrees-export-")
    os.chown(tmp, u.pw_uid, u.pw_gid)
    try:
        gdir = os.path.join(BACKUP_DIR, "gedcom")
        for name in trees(s):
            wt("tree-export", name, cwd=tmp)
            exported = os.path.join(tmp, name + ".ged")
            shutil.copy2(exported, os.path.join(gdir, f"{name}_{stamp}.ged"))
            shutil.copy2(exported, os.path.join(gdir, f".{name}.ged.tmp"))
            os.replace(os.path.join(gdir, f".{name}.ged.tmp"), os.path.join(gdir, f"{name}.ged"))
            prune(os.path.join(gdir, f"{name}_*.ged"), KEEP_GEDCOM)
            report.append(f"GEDCOM {name}.ged ({os.path.getsize(exported) // 1024} KB)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if s["dbtype"] == "sqlite":
        # Die Datei im laufenden Betrieb zu kopieren kann eine halbe Transaktion erwischen; die
        # Backup-Schnittstelle von SQLite liefert einen konsistenten Stand.
        ddir = os.path.join(BACKUP_DIR, "database")
        part = os.path.join(ddir, f".{s['dbname']}_{stamp}.part")
        src = sqlite3.connect(f"file:{db_file(s)}?mode=ro", uri=True, timeout=60)
        dst = sqlite3.connect(part)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        os.replace(part, os.path.join(ddir, f"{s['dbname']}_{stamp}.sqlite"))
        shutil.copy2(CONFIG, os.path.join(ddir, "config.ini.php"))
        prune(os.path.join(ddir, f"{s['dbname']}_*.sqlite"), KEEP_DB)
        report.append("database")
    else:
        report.append(f"database ({s['dbtype']}: bitte mit dessen eigenen Mitteln sichern)")

    report.append(f"media ({mirror_media()} new/changed)")
    now = datetime.datetime.now()
    state_set("last-backup", int(now.timestamp()))
    with open(os.path.join(BACKUP_DIR, "LAST-BACKUP.txt"), "w", encoding="utf-8") as f:
        f.write(f"{now:%Y-%m-%d %H:%M}\n" + "\n".join(report) + "\n")
    log("Sicherung: " + ", ".join(report))


def run_backup(s):
    try:
        backup_once(s)
    except Exception as e:  # noqa: BLE001 — eine missglückte Sicherung darf webtrees nicht stoppen
        log(f"FEHLER in der Sicherung: {e}")


def backup_loop(s):
    # Beim Start nachholen, wenn die letzte Sicherung älter als ein Tag ist — das Gerät schläft
    # vielleicht um drei Uhr nachts.
    try:
        last = int(state_get("last-backup") or 0)
    except ValueError:
        last = 0
    if time.time() - last > 86400:
        time.sleep(30)
        run_backup(s)
    while True:
        now = datetime.datetime.now()
        nxt = now.replace(hour=BACKUP_HOUR, minute=0, second=0, microsecond=0)
        if nxt <= now:
            nxt += datetime.timedelta(days=1)
        while datetime.datetime.now() < nxt:
            time.sleep(60)
        run_backup(s)


def helper(s, tz):
    if not wait_http():
        log("WARNUNG: Apache antwortet nicht — keine Einrichtung, keine Sicherung")
        return
    if not os.path.isfile(CONFIG):
        if has_setup_data(s):
            if not run_setup_wizard(s):
                return
        elif os.path.isfile(SETUP_PAGE):
            s = await_setup_page(s)
        else:
            log("Keine Einrichtungsdaten — bitte webtrees im Browser einrichten")
    # Warten, bis webtrees eingerichtet ist (automatisch oder von Hand im Browser).
    while not os.path.isfile(CONFIG):
        time.sleep(10)
    time.sleep(3)
    target_ok = backup_target_ok()
    try:
        if s["from_file"]:
            forget_password()
        first_run(s, tz)
        if target_ok:
            import_waiting_gedcom(s)
    except Exception as e:  # noqa: BLE001
        log(f"FEHLER in der Ersteinrichtung: {e}")
    if target_ok:
        backup_loop(s)
    else:
        log(f"WARNUNG: kein Sicherungsziel unter {BACKUP_ROOT} — keine Sicherung, kein Import")


# ── Hauptprogramm ────────────────────────────────────────────────────────────────────────


def main():
    tz = apply_timezone()
    apply_ids()
    apply_php_ini(tz)
    s = settings()
    if s["restore"] and backup_target_ok():
        restore_from_backup(s)
    ensure_webtrees()
    ensure_modules()
    fix_ownership()
    ensure_writable()
    apply_config_env()
    os.makedirs(BACKUP_DIR, exist_ok=True) if backup_target_ok() else None
    enable_setup_page(s)

    # Nebenprozess in eigener Sitzung. Apache schickt beim Beenden SIGTERM an seine
    # Prozessgruppe; der Nebenprozess ignoriert es, beim Stoppen des Containers endet er ohnehin.
    if os.fork() == 0:
        os.setsid()
        for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
            signal.signal(sig, signal.SIG_IGN)
        try:
            helper(s, tz)
        except BaseException as e:  # noqa: BLE001
            log(f"Nebenprozess beendet: {e!r}")
        os._exit(0)
    os.execvp("apache2-foreground", ["apache2-foreground"])


if __name__ == "__main__":
    main()
