Erste öffentliche Version.

### Installation
HACS → ⋮ → Benutzerdefinierte Repositories → `https://github.com/Darkwulf183/smart-dashboard-switcher` (Typ: Integration). Danach Home Assistant neu starten. Details stehen in der README.

### Inhalt
- Automatischer Wechsel zwischen zwei Dashboard-Ansichten je nach Zustand einer Entität (`switch`, `binary_sensor`, `input_boolean`)
- Getrennte Verzögerung für EIN und AUS mit Countdown
- Eigenes Dashboard wird automatisch angelegt und kann im Profil als Standard gewählt werden
- Mehrere Instanzen möglich
- Eigene Icons im Ordner `brand/` (ab HA 2026.3)

### Korrekturen gegenüber der Vorabversion
- Fehler beim Entladen bzw. Neuladen der Integration behoben
- Übersetzungen werden jetzt angezeigt (Ordner `translations/`)
- Endlosschleife verhindert, wenn das eigene Dashboard als Ziel eingetragen ist
- Nach einem Ladefehler wird es nach 15 s erneut versucht
- `CONFIG_SCHEMA` für Hassfest ergänzt
