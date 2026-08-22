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

## Sperre mot gjetting (brute force)

| Opsjon | Standard | Beskrivelse |
|---|---|---|
| `max_failures` | 20 | Antall feilede innlogginger som utløser blokkering |
| `window_hours` | 12 | Rullende vindu feilene telles innenfor |
| `block_hours` | 0 | 0 = blokkeringen varer til den fjernes manuelt |
| `trust_proxy` | false | Bruk `X-Forwarded-For` som nøkkel. Kun hvis du faktisk har en proxy foran – ellers deler alle nøkkel |
| `never_block` | `[]` | Ekstra IP-er/CIDR som aldri blokkeres |

**Private IP-er blokkeres aldri.** Det er en bevisst sikring så du ikke kan låse
deg selv ute hjemmefra. Merk at Pythons `is_private` også dekker
dokumentasjonsområdene (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24) – bruk
ekte offentlige adresser hvis du skal teste sperren.

En blokkert IP får 403 på alt unntatt `/health`, også med riktig brukernavn.

### Blokkeringer i Configuration

Blokkerte IP-er ligger i add-on-opsjonen `blocked_ips`, så de vises og kan
redigeres direkte i HA sitt Configuration-skjema. Fjerner du en IP der, er den
fri innen ~20 sekunder – add-onet spør Supervisor med jevne mellomrom.
Legger du til en IP manuelt, blokkeres den på samme måte.

Dette krever `hassio_api: true`, siden add-onet må lese og skrive sine egne
opsjoner. To ting er verdt å vite:

- `/data/options.json` skrives **bare ved oppstart**, så den kan ikke brukes
  til å oppdage endringer. Derfor spør add-onet Supervisor-API-et i stedet.
- Redigerer du andre opsjoner i UI-et samtidig som en ny blokkering skrives,
  kan den ene overskrive den andre. Sjelden, men mulig.

Feiltellerne ligger fortsatt i `/data/blocks.json` – de hører ikke i et
konfigurasjonsskjema.

### Oppheve blokkeringer

Brukere med `admin: true` får siden `/blokkeringer`: oversikt over IP-er med
feilforsøk, hvilke som er blokkert, og knapper for å oppheve enkeltvis eller
alle. Opphevinger logges med hvem som gjorde det.

Har du ingen admin-bruker, kan blokkeringer også fjernes ved å slette
`/data/blocks.json` i add-onet og restarte.
