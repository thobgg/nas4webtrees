# nas4webtrees

**English** · [Deutsch](README.de.md)

The original, unmodified [webtrees](https://webtrees.net/) for NAS devices and home servers — with
[api4webtrees](https://github.com/thobgg/api4webtrees) included, so the apps **wtAnd** (Android),
**wtWin** (Windows) and **wtTux** (Linux) from [app4webtrees](https://github.com/thobgg/app4webtrees)
connect right away.

- **Native webtrees, no fork.** On first start the official release file from
  [fisharebest/webtrees](https://github.com/fisharebest/webtrees/releases) (checksum-verified) is
  unpacked into your volume. From then on the installation belongs to webtrees: update it as
  usual under *Control panel → Upgrade*. A new image never touches it and never downgrades it.
- **No database server.** SQLite by default — one file. MySQL/MariaDB and PostgreSQL work too.
- **Your GEDCOM file, every night.** Each family tree is exported to `backup/gedcom/<tree>.ged`
  (fixed name, plus 30 older states), together with a consistent copy of the database and a
  mirror of all media. Reinstall next to the backup and the latest state comes back.
- **Bring your tree.** Drop a GEDCOM file into `backup/import/` and restart: it is imported into
  the (still empty) family tree.
- amd64, arm64 and armv7.

## Where it runs

| Platform | How |
| - | - |
| Synology (DSM 7.2+, models with Container Manager) | Package with installation wizard: download `nas4webtrees-….spk` from [Releases](https://github.com/thobgg/nas4webtrees/releases), then Package Center → Manual Install |
| TrueNAS SCALE 25.04+ | Apps → Discover → *Install via YAML* with [`compose/docker-compose.yml`](compose/docker-compose.yml) |
| UGREEN (UGOS Pro) | Docker → Project → Create, paste the compose file |
| TerraMaster (TOS 6) | Docker Manager → Project, paste the compose file |
| Asustor (ADM) | Portainer from App Central → Stacks, paste the compose file |
| Unraid | Template [`unraid/nas4webtrees.xml`](unraid/nas4webtrees.xml) |
| QNAP | Container Station → Applications, paste the compose file |
| Raspberry Pi, any Linux server | `docker compose up -d` |

## Synology in short

1. Install **Container Manager** from Package Center (once).
2. Download `nas4webtrees-….spk` from [Releases](https://github.com/thobgg/nas4webtrees/releases).
3. Package Center → *Manual Install* → choose the file → confirm the third-party notice → fill in the wizard
   (family tree name, administrator, port, shared folder for the backup).
4. Open webtrees from the DSM main menu (*nas4webtrees*). The entry *nas4webtrees – Apps verbinden* leads to
   the page for the apps.

## Quick start (Docker Compose)

```sh
mkdir webtrees && cd webtrees
curl -O https://raw.githubusercontent.com/thobgg/nas4webtrees/main/compose/docker-compose.yml
echo 'a-long-password' > webtrees_admin_password.txt   # first admin password
# edit docker-compose.yml: name, email, port, time zone
docker compose up -d
```

Open `http://<your-nas>:8095`. Without `WT_USER`/`WT_EMAIL`/`WT_PASS` the webtrees setup wizard
appears instead — choose *SQLite* there.

## Settings

| Variable | Default | Meaning |
| - | - | - |
| `WT_USER`, `WT_NAME`, `WT_EMAIL` | – | Administrator created on first start |
| `WT_PASS` / `WT_PASS_FILE` | – | Their password (prefer the file variant: Docker secret) |
| `WT_LANG` | `en-US` | Language for setup (`de`, `nl`, `fr`, …) |
| `WT_TREE`, `WT_TREE_TITLE` | `tree1`, `My family tree` | First family tree |
| `WT_RESTORE` | `true` | Restore from `/backup` on a fresh install |
| `WT_PRIVATE` | `true` | New family tree only for signed-in users, no self-registration (the administrator creates accounts). `false` keeps the webtrees default: public tree, living people hidden |
| `TZ` | – | Time zone, e.g. `Europe/Berlin` |
| `PUID`, `PGID` | 33 | Owner of the files (Unraid: 99/100) |
| `WRITE_GID` | – | Group that may write on ACL-managed shares; used only if the files are not writable otherwise |
| `BASE_URL`, `PRETTY_URLS` | – | Only if you need them; set on every start |
| `BACKUP_HOUR` | `3` | Hour of the nightly backup |
| `BACKUP_KEEP_GEDCOM`, `BACKUP_KEEP_DB` | `30`, `7` | States kept |
| `DB_TYPE`, `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS(_FILE)`, `DB_NAME`, `DB_PREFIX` | `sqlite`, …, `webtrees`, `wt_` | Other databases |
| `PHP_MEMORY_LIMIT`, `PHP_MAX_EXECUTION_TIME`, `PHP_UPLOAD_MAX_FILE_SIZE`, `PHP_POST_MAX_SIZE` | `1024M`, `90`, `64M`, `64M` | PHP limits |

Volumes: `/webtrees` (program and data), `/backup` (backup and import folder).

## Access from outside

Put the reverse proxy of your NAS in front (Synology: *Control Panel → Login Portal → Advanced →
Reverse Proxy*), HTTPS outside, `http://localhost:8095` inside. The image honours
`X-Forwarded-Proto`, so webtrees produces `https://` links.

## Connecting the apps

Sign in to webtrees, open the menu entry **App** and follow the two steps there. Details:
[api4webtrees](https://github.com/thobgg/api4webtrees#readme).

## Not an official webtrees project

nas4webtrees is an independent community project that packages webtrees for NAS devices. It is
not affiliated with or endorsed by the webtrees project. For webtrees itself, see
[webtrees.net](https://webtrees.net/).

## License

GPL-3.0-or-later, like webtrees and api4webtrees. webtrees is © the webtrees development team;
this project only packages it.
