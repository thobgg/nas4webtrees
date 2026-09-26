# Synology-Paket

Paket für DSM 7.2+ auf Modellen mit Container Manager: Installationsassistent (Stammbaum,
Administrator, Port, Freigabe für die Sicherung), kein root, kein Web Station, keine MariaDB.
Das Paket zieht das Image `ghcr.io/thobgg/nas4webtrees` und legt Programm und Daten unter
`docker/nas4webtrees/data` ab, die Sicherung unter `<Freigabe>/webtrees-sicherung` (bleibt beim
Deinstallieren stehen).

Bauen: `synology/build.sh` → `dist/webtrees-<version>.spk`, einspielen über
Paket-Zentrum → Manuelle Installation. `--standalone` baut das ganze Image auf der NAS statt es
zu laden.
