# Garasjeport – Home Assistant add-on repository

Add-on som hoster en enkel nettside med én knapp som åpner garasjeporten
(Hörmann HSE2-868 via ESP32 + CC1101, styrt gjennom Home Assistant).

## Installasjon

Settings → Add-ons → Add-on Store → ⋮ → Repositories → legg inn:

```
https://github.com/owanvik/hass-garasjeport-web
```

Installer **Garasjeport Web**, sett `username` i Configuration, og start.

## Add-ons

- [`garasjeport_web`](garasjeport_web/) – nettside med åpne-knapp
