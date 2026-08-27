# FOOKE-Kataloge

Dieses Repository enthält die versionierten, statischen Kataloge für die
FOOKE-Anwendungen. Anwendungscode, Katalogparser und lokale Datenhaltung
verbleiben in `fooke-diagnostics-platform`.

## Repository-Struktur

```text
public/
└── catalogs/
    └── <catalog-id>/
        ├── index.json
        └── versions/
            └── <catalog-version>/
                ├── manifest.json
                └── <catalog-data>.json
```

Jeder Katalog besitzt ein eigenes Verzeichnis unter `public/catalogs`. Dadurch
können neben dem Allergenkatalog später weitere Kataloge unabhängig
versioniert und gepflegt werden. Zum veröffentlichten Datenbestand gehören nur
die Inhalte von `public`; Dokumentation, Prüfwerkzeuge und Tests gehören nicht
zum Katalogpaket.

## Lokale Prüfung

Die folgenden Befehle werden im Stammverzeichnis des Repositorys ausgeführt:

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_catalogs.py
```

Die allgemeine Prüfung kontrolliert die Übereinstimmung von Index und
Manifest, relative Ressourcenpfade, Dateigröße, SHA-256-Prüfsummen und
katalogspezifische Regeln. Ein neuer Katalog mit eigenen fachlichen Regeln
erhält gleichzeitig eine eigene Prüfung und passende Tests.

## Versionierung

Eine bereits veröffentlichte Katalogversion wird nicht nachträglich verändert
oder entfernt. Korrekturen erhalten eine neue Katalogversion und werden über
die jeweilige `index.json` bekannt gemacht. Noch nicht veröffentlichte
Vorabversionen dürfen nur nach ausdrücklicher Bestätigung entfernt werden.
