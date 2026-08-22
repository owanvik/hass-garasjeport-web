# Garasjeport Web

Nettside med én stor knapp som kaller `button.press` på garasjeport-entiteten
i Home Assistant. Laget for å nås fra mobil, også utenfra via port-forward.

## Konfigurasjon

| Opsjon | Beskrivelse |
|---|---|
| `username` | Det eneste som kreves for å komme inn. **Brukernavnet er i praksis et passord** – velg noe langt og ugjettbart. |
| `entity_id` | HA-entiteten som skal trykkes. Standard: `button.garasjeport_garasjeport_apne` |
| `cooldown_seconds` | Sperre mot dobbelttrykk. Standard 5. |

## Sikkerhet – les dette

«Auth» er kun et brukernavn, uten passord. Det er et bevisst valg, men det betyr:

- Brukernavnet er den *eneste* beskyttelsen. Behandle det som et passord.
- Eksponerer du porten mot internett, kan hvem som helst som gjetter eller
  får tak i brukernavnet åpne garasjen din.
- Trafikken er HTTP, ikke HTTPS. Brukernavnet går i klartekst over nettet.
  Bruk det kun over et nett du stoler på, eller sett en reverse proxy med TLS foran.

Feil brukernavn gir 1 sekunds forsinkelse, som bremser gjetting noe – men det
erstatter ikke et langt brukernavn.

## Endepunkter

- `GET /` – login eller knappeside
- `GET /?u=<brukernavn>` – ett-klikks innlogging, egnet for bokmerke
- `POST /open` – trykker knappen (krever gyldig cookie)
- `GET /health` – helsesjekk
- `GET /logout` – glem cookie
