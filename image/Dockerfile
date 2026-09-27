# nas4webtrees — das originale webtrees für NAS und Heimserver, mit api4webtrees.
#
# Gebaut in GitHub Actions für amd64, arm64 und armv7 (.github/workflows/image.yml).
# Versionen und Prüfsummen kommen als Build-Argumente aus ../VERSIONS.
FROM php:8.4-apache

# PHP-Erweiterungen, die webtrees braucht oder nutzt (imagick: schnellere Vorschaubilder).
# install-php-extensions holt je Architektur die passenden Pakete und räumt danach auf.
COPY --from=mlocati/php-extension-installer:2.12.0 /usr/bin/install-php-extensions /usr/local/bin/
RUN install-php-extensions gd intl zip exif pdo_mysql pdo_pgsql imagick \
 && apt-get update \
 && apt-get install -y --no-install-recommends python3 curl unzip \
 && rm -rf /var/lib/apt/lists/*

# Die Build-Argumente erst hier: Jede neue Versionsnummer macht den Zwischenspeicher für alle
# folgenden RUN-Schritte ungültig. Stünden sie oben, würden bei jedem Modul-Update auch die
# PHP-Erweiterungen neu kompiliert — unter Emulation für arm64/armv7 rund 40 Minuten.
ARG WEBTREES_VERSION
ARG WEBTREES_SHA256
ARG API4WEBTREES_VERSION
ARG API4WEBTREES_SHA256

# Offizielle Release-Datei von github.com/fisharebest/webtrees, unverändert. Sie wird erst beim
# ersten Start in das Volume entpackt; danach gehört die Installation webtrees selbst und wird
# über Verwaltung → Aktualisierung gepflegt.
RUN mkdir -p /opt/nas4webtrees/modules \
 && curl -fsSL -o /opt/nas4webtrees/webtrees.zip \
      "https://github.com/fisharebest/webtrees/releases/download/${WEBTREES_VERSION}/webtrees-${WEBTREES_VERSION}.zip" \
 && echo "${WEBTREES_SHA256}  /opt/nas4webtrees/webtrees.zip" | sha256sum -c - \
 && curl -fsSL -o /tmp/api4webtrees.zip \
      "https://github.com/thobgg/api4webtrees/releases/download/v${API4WEBTREES_VERSION}/api4webtrees-v${API4WEBTREES_VERSION}.zip" \
 && echo "${API4WEBTREES_SHA256}  /tmp/api4webtrees.zip" | sha256sum -c - \
 && unzip -q /tmp/api4webtrees.zip -d /opt/nas4webtrees/modules \
 && rm /tmp/api4webtrees.zip \
 && test -f /opt/nas4webtrees/modules/api4webtrees/module.php

COPY rootfs/ /
RUN a2enmod rewrite headers \
 && a2dissite 000-default \
 && a2ensite webtrees \
 && a2enconf nas4webtrees \
 && mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini" \
 && chmod 755 /usr/local/bin/nas4webtrees-entry.py \
 && mkdir -p /webtrees /backup /config

ENV WEBTREES_BUNDLED_VERSION="${WEBTREES_VERSION}" \
    API4WEBTREES_VERSION="${API4WEBTREES_VERSION}"
LABEL org.opencontainers.image.title="nas4webtrees" \
      org.opencontainers.image.description="The original webtrees for NAS and home servers, with api4webtrees for the wtAnd, wtWin and wtTux apps" \
      org.opencontainers.image.source="https://github.com/thobgg/nas4webtrees" \
      org.opencontainers.image.licenses="GPL-3.0-or-later"

# /webtrees: Programm und Daten (webtrees aktualisiert sich hier selbst)
# /backup:   nächtliche Sicherung (GEDCOM, Datenbank, Medien) und Import-Ordner
# /config:   optional, Einrichtungsdatei setup.json (Synology-Paket)
VOLUME ["/webtrees", "/backup"]
EXPOSE 80
# Eine statische Datei: webtrees' Robotersperre beantwortet curl auf PHP-Seiten mit 4xx.
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s \
  CMD curl -fsS -o /dev/null http://127.0.0.1/public/css/webtrees.min.css || exit 1
ENTRYPOINT ["/usr/local/bin/nas4webtrees-entry.py"]
