# Garasjeport Web

Nettside med én stor knapp som kaller `button.press` på garasjeport-entiteten i
Home Assistant. Flere brukere, og alt som skjer havner i en adgangslogg.

## Konfigurasjon

```yaml
users:
  - username: portner-3ab2edfcd3   # dette skriver man inn
    label: Olai                    # dette vises i loggen
    enabled: true                  # sett false for å sperre uten å slette
  - username: nabo-9f2c1ab77e
    label: Nabo 1C
entity_id: button.garasjeport_garasjeport_apne
cooldown_seconds: 5                # sperre mot dobbelttrykk
log_max_lines: 5000                # loggen roteres på denne grensen
```

| Opsjon | Beskrivelse |
|---|---|
| `users[].username` | Det eneste som kreves for å komme inn. **Er i praksis passordet** – gjør det langt og ugjettbart. |
| `users[].label` | Navnet som vises i adgangsloggen. Faller tilbake til `username`. |
| `users[].enabled` | `false` sperrer brukeren umiddelbart, uten å slette oppføringen. |
| `entity_id` | HA-entiteten som skal trykkes. |
| `cooldown_seconds` | Minste tid mellom to trykk. |
| `log_max_lines` | Loggen beholder de nyeste N linjene. |

## Adgangslogg

Alt logges til add-on-loggen og til `/data/access.log` (JSONL, overlever restart).
Se den i nettleseren på `/logg` – krever innlogging.

Hendelser: `login_ok`, `login_fail`, `open_ok`, `open_fail`, `logout`.
Hver linje har tidspunkt, hendelse, hvilken bruker, klient-IP og en detalj.
Avviste innlogginger logger hva som ble forsøkt, så du ser gjettingsforsøk.

## Ingen tilbakemelding fra porten

Hörmann HSE2-868 er en **enveis fast-kode-sender**. Motoren har ingen
returkanal, så systemet kan aldri vite om porten faktisk åpnet seg.
`open_ok` i loggen betyr «kommandoen ble sendt», ikke «porten gikk opp».
Formuler aldri meldinger som antyder noe annet.

## Sikkerhet – les dette

«Auth» er kun et brukernavn, uten passord. Bevisst valg, men det betyr:

- Brukernavnet er den *eneste* beskyttelsen. Behandle det som et passord, og gi
  hver person sitt eget – da viser loggen faktisk hvem som gjorde hva.
- Trafikken er **HTTP, ikke HTTPS**. Eksponerer du porten mot internett, går
  brukernavnet i klartekst over nettet og kan snappes opp på veien. Sett en
  reverse proxy med TLS foran hvis dette skal stå permanent.
- Feil brukernavn gir 401 og 1 sekunds forsinkelse. Det bremser gjetting, men
  erstatter ikke et langt brukernavn.
- Cookien inneholder brukernavnet, altså hemmeligheten. Den settes `HttpOnly`
  og `SameSite=Lax`, men uten HTTPS er den ikke beskyttet mot avlytting.

## Endepunkter

| Rute | Beskrivelse |
|---|---|
| `GET /` | Login, eller knappesiden hvis innlogget |
| `GET /?u=<brukernavn>` | Ett-klikks innlogging, egnet for bokmerke |
| `POST /open` | Trykker knappen. Krever gyldig cookie. |
| `GET /logg` | Adgangsloggen. Krever innlogging. |
| `GET /health` | Helsesjekk + antall aktive brukere |
| `GET /logout` | Glem cookie |
