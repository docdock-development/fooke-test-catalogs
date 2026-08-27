# Repository-Anweisungen

## Allgemeine Katalogregeln

1. Lege alle auslieferbaren Ressourcen unter
   `public/catalogs/<catalog-id>/` ab. Werkzeuge, Tests und Dokumentation
   bleiben außerhalb von `public`.
2. Behandle jedes Katalogverzeichnis als unabhängig versionierte Ressource.
   Seine `index.json` bestimmt die aktuelle Version. Alle darin aufgeführten
   Manifeste und Datendateien müssen relativ adressiert, auflösbar und im
   selben Katalogverzeichnis enthalten sein.
3. Prüfe vor jeder Veröffentlichung das gesamte Repository. Ein neuer Katalog
   mit eigenen fachlichen Regeln benötigt im selben Änderungsschritt eine
   eigene Prüfung und fokussierte Tests.
4. Verändere oder entferne keine bereits veröffentlichte Katalogversion.
   Korrekturen werden als neue Version veröffentlicht. Vorabversionen dürfen
   nur entfernt werden, wenn ausdrücklich bestätigt wurde, dass sie noch nicht
   veröffentlicht wurden.
5. Pflege keine zweite, unabhängig bearbeitete Kopie desselben Katalogstands.
6. Verwende zum Löschen, Verschieben und Umbenennen versionierter Dateien
   ausschließlich Git-Befehle.
7. Lege in diesem Repository nur Inhalte ab, die für die öffentliche
   Katalogpflege und -auslieferung bestimmt sind.

## Invarianten des Allergenkatalogs

1. Die UUIDv7-Identität eines Allergens bleibt bei Änderungen an Metadaten,
   Labels, Genehmigungszuständen sowie bei Korrekturen der Reihenfolge
   unveränderter Mischungskomponenten erhalten. Erhöhe bei jeder Änderung
   `updated_at`, ohne `created_at` oder `deleted_at` neu zu schreiben.
2. Das Hinzufügen, Entfernen, Ersetzen oder Umadressieren einer
   Mischungskomponente ändert die fachliche Identität der Mischung. Setze beim
   bisherigen Eintrag `deleted_at` und erstelle den Ersatz mit einer neuen
   UUIDv7.
3. Jedes vom aktuellen Schema verlangte Feld ist für aktive und stillgelegte
   Einträge verpflichtend. Füge keine Kompatibilitätsstandardwerte oder
   Migrationen hinzu, sofern dies nicht ausdrücklich verlangt wurde.
4. Eine `approved`-Mischung darf ausschließlich `approved`-Komponenten
   referenzieren. Diese Regel gilt transitiv für verschachtelte Mischungen.
   Wird eine Komponente auf `not_approved` gesetzt, müssen alle davon
   abhängigen genehmigten Mischungen ebenfalls auf `not_approved` gesetzt
   werden, ohne ihre UUID zu ändern.
5. Die erneute Genehmigung einer Komponente genehmigt davon abhängige
   Mischungen nicht automatisch. Jede Mischung benötigt eine eigene
   ausdrückliche fachliche Genehmigung.
6. Mischungskomponenten müssen geordnet, eindeutig, auflösbar,
   nicht-selbstreferenziell und azyklisch sein.
7. Die Standard-Auftragssuche liefert ausschließlich aktive, `approved`
   Allergene. Eine spätere optionale Einbeziehung von `not_approved`-Allergenen
   muss ausdrücklich erfolgen und den Genehmigungszustand an den Anwendungs-
   und Befehlsgrenzen sichtbar halten.
8. Allergencodes, die ohne Beachtung der Groß-/Kleinschreibung mit `R` oder `N`
   beginnen, kennzeichnen rekombinante Allergene. Eine Änderung dieser
   katalogeigenen Metadaten behält UUIDv7 und `created_at` bei, erhöht
   `updated_at` und verändert keine Mischungsidentität.
