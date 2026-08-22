# Garasjeport – Home Assistant add-on repository

Add-on som hoster en enkel nettside med én knapp som åpner garasjeporten
(Hörmann HSE2-868 via ESP32 + CC1101, styrt gjennom Home Assistant).

## Installasjon

Settings → Add-ons → Add-on Store → ⋮ → Repositories → legg inn:

```
https://github.com/owanvik/hass-garasjeport-web
```

Installer **Garasjeport Web**, sett `username` i Configuration, og start.

## App-ikon

Originalen ligger i [`assets/garasje-original.png`](assets/garasje-original.png).
Ikonene som serveres genereres fra den:

```
python3 assets/lag-ikoner.py
```

Skriptet fyller de gjennomsiktige hjørnene med bakgrunnsfargen, fordi
`apple-touch-icon` ikke skal ha runde hjørner selv – iOS legger på sin egen
maske, og et ikon med runde hjørner blir rundet to ganger med mørke kanter.

## Add-ons

- [`garasjeport_web`](garasjeport_web/) – nettside med åpne-knapp
