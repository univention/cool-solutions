## Package: univention-sanis

A helper for UCS@school user import from SANIS (official name 'moin.schule')
In diesem Paket finden Sie ein Werkzeug, mit dem Sie Benutzerdaten aus SANIS (offizieller Projektname: moin.schule) importieren können.

### Inhalt

* Ein Hilfsskript `create_input_files`, welches Daten aus SANIS liest, Konfiguration vorbereitet, und einzelne Importdateien (pro Schule und Benutzerrolle) aus dem Datenbestand extrahiert.
* Eine für diesen Anwendungsfall vorbereitete Konfiguration. Zusätzlich wird die beschriebene Konfiguration für "[Single source, Partial import](http://docs.software-univention.de/ucsschool-umc-user-import/5.0/de/single-source.html)" benutzt, um einen Schulwechsel zu ermöglichen
   * z.B. /usr/share/ucs-school-import/scripts/create_ou limbo

### E-Mail Support

Der SANIS-Connector kann E-Mail-Adressen aus moin.schule extrahieren und in die CSV-Importdateien einbinden.

#### Konfiguration

```bash
# E-Mail-Support aktivieren
ucr set sanis_import/include_school_email=true

# E-Mail-Support deaktivieren (Standard)
ucr set sanis_import/include_school_email=false
# oder
ucr unset sanis_import/include_school_email
```

#### CSV-Mapping für E-Mails

Wenn E-Mail-Support aktiviert ist, enthält die CSV-Datei eine "EMail"-Spalte. Um diese E-Mails in UCS zu importieren, konfigurieren Sie das Mapping in `/var/lib/ucs-school-import/configs/user_import_sanis.json`:

```json
{
    "csv": {
        "mapping": {
            "ID": "record_uid",
            "Vorname": "firstname",
            "Familienname": "lastname",
            "Geburtstag": "birthday",
            "Klassen": "school_classes",
            "Schule": "school",
            "Schulen": "schools",
            "EMail": "email"
        }
    }
}
```

**Standard-Verhalten:** Das `"EMail"`-Feld wird auf `email`und dadurch auf`mailPrimaryAddress` in UCS gemappt.

**Alternative E-Mail-Felder:** Sie können E-Mails auch in andere UCS-Felder mappen:
```json
"EMail": "mailAlternativeAddress"    // Alternative E-Mail
"EMail": "e-mail"                    // Kontakt-E-Mail
```

**Mehrere E-Mail-Felder:** Für die Verteilung einer E-Mail auf mehrere UCS-Felder können Sie Schemes verwenden:

```json
{
    "csv": {
        "mapping": {
            "EMail": "mailAlternativeAddress"
        }
    },
    "scheme": {
        "e-mail": "<mailAlternativeAddress>[0]",
        "testmail": "<mailAlternativeAddress>[0]"
    }
}
```
https://docs.software-univention.de/ucsschool-import/5.0/de/configuration/format.html#cmdoption-arg-scheme-udm

#### Mail-Domains

**Wichtig:** Die E-Mail-Domain muss in UCS konfiguriert sein, damit E-Mails in `mailPrimaryAddress` importiert werden können:
Alternativ können Sie E-Mails etwa in `mailAlternativeAddress` importieren, welches keine Domain-Validierung hat.

### Sorgeberechtigte

Der Konnektor kann Sorgeberechtigte (SANIS-Rolle `SorgBer`) als eigene Rolle exportieren und
sie mit ihren Kindern verknüpfen. Das Feature ist standardmäßig aus:

```bash
# Sorgeberechtigten-Export aktivieren
ucr set sanis_import/activate_legal_guardians=yes

# deaktivieren (Standard)
ucr unset sanis_import/activate_legal_guardians
```

Ist es aktiv, entsteht zusätzlich die Datei `legal_guardian.csv` mit der Spalte `Kinder`,
die die recordUIDs (SANIS `person.id`) der zugeordneten Kinder kommagetrennt enthält. Im
SiSoPi-Modus wird die Rolle übersprungen, siehe Hinweise.

#### Voraussetzungen

* UCS@school 5.2 v4 oder neuer, mindestens `ucs-school-import` 19.2.5. Der Hook kam mit
  19.2.2, 19.2.5 korrigiert den Umgang mit nicht gemappten `legal_guardian`- und
  `legal_ward`-Spalten. Die installierte Version zeigt `dpkg -l ucs-school-import`. Das Paket
  erzwingt das nicht über `Depends`, damit Installationen ohne dieses Feature nicht vom Update
  ausgeschlossen werden.
* Der Joinscript `35ucs-school-import.inst` muss gelaufen sein (aktuell `VERSION=37`). Er
  legt Container und Gruppe für Sorgeberechtigte an. Lag die zuletzt ausgeführte Version unter
  36, holt er das für alle vorhandenen Schulen nach. Die Namen `cn=sorgeberechtigte` und
  `sorgeberechtigte-<OU>` sind UCR-Vorgaben
  (`ucsschool/ldap/default/container/legal_guardians` und `.../groupprefix/legal_guardians`)
  und können abweichen. Vor dem Rollout prüfen mit `univention-check-join-status`.
* Der Hook, der recordUIDs auflöst, kommt aus dem Paket `ucs-school-import` und muss
  aktiviert werden:

```bash
cp /usr/share/ucs-school-import/pyhooks-available/legal_guardian_as_record_uid.py \
   /usr/share/ucs-school-import/pyhooks/
```

  Er gilt danach für **alle** Importe auf dem System und bleibt aktiv, auch wenn das Feature
  abgeschaltet oder dieses Paket entfernt wird. Andere Importe stört er nur, wenn deren
  Konfiguration `legal_wards` oder `legal_guardians` mit Benutzernamen statt recordUIDs mappt.
  `create_import_files` prüft, ob der Hook aktiviert ist, und bricht sonst ab, bevor der erste
  Import läuft. Der Abbruch liefert seit 1.0.10 den Exit-Code 1, wie jeder andere Fehler des
  Skripts auch. Wer es aus einem Cronjob oder Wrapper heraus aufruft, sollte den Rückgabewert
  prüfen.

#### CSV-Mapping für Sorgeberechtigte

Die Spalte `Kinder` wird auf das Import-Attribut `legal_wards` gemappt. **Dieses Mapping
darf nur für die Rolle `legal_guardian` gelten**, sonst brechen die Schüler- und
Lehrer-Importe. Dafür liegt eine fertige Konfiguration bei:

```bash
cp /usr/share/univention-sanis/user_import_sanis_legal_guardian_example.json \
   /var/lib/ucs-school-import/configs/user_import_sanis_legal_guardian.json
```

Das erzeugte `run_import` übergibt sie beim Import der Sorgeberechtigten, die anderen Rollen
benutzen weiter `user_import_sanis.json`. Fehlt die Datei bei eingeschaltetem Feature, bricht
`create_import_files` mit einem Hinweis ab.

Der Unterschied zur allgemeinen `user_import_sanis_example.json` liegt neben der Spalte
`Kinder` in den `mandatory_attributes`: Die allgemeine Beispielkonfiguration verlangt
`birthday`, das in SANIS aber häufig leer ist. Bliebe `birthday` Pflichtfeld, bräche der
Lauf bei der ersten solchen Zeile ab, weil `tolerate_errors` per Default 0 ist. Die
Sorgeberechtigten-Konfiguration übernimmt deshalb die `mandatory_attributes` des
UCS@school-Standards aus `user_import_defaults.json`.

#### Hinweise

* **Die Sorgeberechtigten müssen nach den Schülern importiert werden**, weil der Importer
  nur auf bereits existierende Benutzer verlinken kann. Das erzeugte `run_import` hält diese
  Reihenfolge ein und bricht mit `set -e` und `set -o pipefail` ab, sobald ein Schritt
  fehlschlägt.
* **Sorgeberechtigte tragen die `source_uid` der Schüler.** Der Hook sucht die Kinder mit der
  `source_uid` des gerade laufenden Imports (`(&(ucsschoolSourceUID=…)(ucsschoolRecordUID=…))`).
  `run_import` importiert sie deshalb mit `--source_uid sanis_student`. Für die Löscherkennung
  ist das unschädlich, sie filtert zusätzlich nach der Rolle. Die Rolle steht dafür in der
  mitgelieferten Konfiguration (`"user_role": "legal_guardian"`), `run_import` übergibt sie
  zusätzlich als Argument. Fehlt sie an beiden Stellen, bricht der Lauf schon beim Lesen der
  ersten Zeile mit `No role in configuration` ab, bevor irgendetwas geschrieben wird.
* **Wer zugleich Schüler und Sorgeberechtigte/r ist, wird nur als Schüler exportiert.**
  UCS@school erkennt ein Konto an `source_uid` und recordUID, und die recordUID gehört zur
  Person. Bei gleicher `source_uid` wären beide Konten nicht unterscheidbar, der Import bräche
  mit `WrongObjectType` ab. Das gilt auch, wenn dem Schüler-Kontext in diesem Lauf nur die
  Klasse fehlt, denn das Schülerkonto steht dann noch im LDAP. Der Konnektor vermerkt jeden
  solchen Fall in `korrekturen.txt`.
* **Ein Rollenwechsel zwischen zwei Läufen lässt sich so nicht abfangen.** Der Konnektor kennt
  nur die Daten des aktuellen Laufs, nicht das LDAP. Wird aus einem Sorgeberechtigten später
  ein Schüler oder umgekehrt, steht das alte Konto noch deaktiviert im LDAP, mit derselben
  `source_uid` und recordUID, so lange `deletion_grace_period` es vorsieht (mitgelieferte
  Beispiele: 90 Tage, UCS@school-Standard: 0). Bis dahin bricht der Lauf der neuen Rolle mit
  `WrongObjectType` ab, beim Wechsel zum Schüler also der **Schüler**-Import. Abhilfe im
  Einzelfall: das alte Konto von Hand löschen.
* **Lehrkräfte, die Sorgeberechtigte sind**, bekommen mit `run_import` zwei Konten: eines als
  Lehrkraft mit `sanis_teacher`, eines als Sorgeberechtigte/r mit `sanis_student`, mit
  eigenem Benutzernamen aus dem Schema (etwa `max.mus2`). Das kollidiert nicht. Wer von Hand
  importiert, darf Lehrkräften **nicht** dieselbe `source_uid` geben wie Schülern und
  Sorgeberechtigten. Sonst bricht der Sorgeberechtigten-Lauf beim
  ersten Elternteil aus dem Kollegium ab.
* **Wer die Schüler bisher von Hand importiert hat**, etwa mit `--source_uid sanis`, darf das
  erzeugte Skript nicht unverändert benutzen: es würde alle Schüler unter `sanis_student` ein
  zweites Mal anlegen. In dem Fall die Sorgeberechtigten ebenfalls von Hand importieren, mit
  derselben `source_uid` wie die Schüler:

```bash
/usr/share/ucs-school-import/scripts/ucs-school-user-import \
  --conffile /var/lib/ucs-school-import/configs/user_import_sanis_legal_guardian.json \
  --user_role legal_guardian --infile legal_guardian.csv \
  --source_uid <source_uid der Schüler>
```

* **Der SiSoPi-Modus wird für Sorgeberechtigte nicht unterstützt.** Dort teilen sich alle
  Rollen die `source_uid` `sanis`. Ein Import der Sorgeberechtigten mit `sanis` bräche bei der
  ersten Lehrkraft mit Kind ab, mit einer anderen `source_uid` fände der Hook keine Kinder.
  Der Konnektor überspringt die Rolle deshalb mit `--sisopi` vollständig: es entsteht weder
  eine CSV noch ein Aufruf in `run_import`. Der Schalter bleibt für die anderen Rollen ohne
  Wirkung, sie werden unverändert exportiert.
* **Die Kinder müssen für den Testlauf schon in UCS@school existieren.** Der Hook läuft im
  Dry-Run mit (`supports_dry_run` wird für `PostReadPyHook` nicht ausgewertet), er löst die
  recordUIDs aber über eine LDAP-Suche auf. Wer Schüler und Sorgeberechtigte in einem Rutsch
  im Dry-Run testet, bekommt für jede Zeile `InvalidLegalWard`, weil die Schüler nur
  probeweise angelegt wurden. Genau das macht `test_run_import`: Fehler beim
  Sorgeberechtigten-Aufruf sind dort für jedes Kind zu erwarten, das noch nicht im LDAP
  steht. Reihenfolge für einen aussagekräftigen Test: Schüler echt importieren, danach die
  Sorgeberechtigten im Dry-Run prüfen.
* UCS@school erlaubt höchstens 10 Kinder je Sorgeberechtigtem und 4 Sorgeberechtigte je
  Kind, fest verdrahtet und auch über UDM durchgesetzt. SANIS kennt diese Grenzen nicht,
  deshalb kürzt der Konnektor beide Listen und vermerkt das in `korrekturen.txt`.
* **Liefert moin.schule keine einzige Beziehung, bricht der Lauf ab.** Eine leere Spalte
  `Kinder` löscht bestehende Verknüpfungen in UCS@school. Die API unterscheidet aber nicht
  zwischen „noch keine Beziehungen gepflegt“ und „Parameter nicht unterstützt“. Das Feature
  daher erst einschalten, wenn in moin.schule Beziehungen gepflegt sind.
* **Diese Bremse greift nur beim Totalausfall.** Fehlen die Beziehungen nur für einen Teil der
  Schüler, etwa weil eine Schule sie noch nicht pflegt, laufen die betroffenen
  Sorgeberechtigten mit leerer Spalte `Kinder` durch, und ihre bestehenden Verknüpfungen in
  UCS@school werden gelöscht. Eine leere Spalte ist für den Importer kein „unverändert“,
  sondern „keine Kinder mehr“. Der Konnektor zählt diese Fälle deshalb und meldet sie mit
  `WARNUNG` in der Ausgabe und in `korrekturen.txt`. Springt die Zahl gegenüber dem letzten
  Lauf, ist das der einzige Hinweis auf einen Teilausfall: Der Import meldet keinen Fehler.
* **`sanis_import/include_school_email` wirkt auch auf Sorgeberechtigte.** Ist die Variable
  aktiv, landet die schulische E-Mail-Adresse aus dem Personenkontext auch in der
  Sorgeberechtigten-CSV. Bei Eltern steht in diesem Feld erfahrungsgemäß eine **private**
  Adresse. Die mitgelieferte Beispielkonfiguration mappt die Spalte deshalb nicht. Wer sie
  mappen will, darf sie nicht auf `email` legen: Das zielt auf `mailPrimaryAddress`, die
  domänenweit eindeutig sein muss und eine konfigurierte Maildomain verlangt. Zwei Elternteile
  mit derselben Familienadresse schlagen dort fehl. Geeignet sind Kontaktfelder wie
  `PasswordRecoveryEmail` oder `e-mail`.
* Kinder, die der Konnektor ohnehin nicht exportiert (etwa Schüler ohne Klassenmitglied-
  schaft), werden nicht verknüpft. Verweise auf nicht importierte Personenkontexte landen
  ebenfalls in `korrekturen.txt`.
* SANIS hinterlegt die Beziehung nur am Schüler-Kontext. Der Konnektor lässt sie sich über
  den Parameter `hat_als_beziehungen=ja` im bestehenden Sammelabruf von `/personen`
  mitliefern und dreht sie um. Das kostet keine zusätzlichen API-Abfragen, vergrößert aber
  die Antwort, die vollständig im Speicher gehalten wird.
* Wird das Feature später wieder abgeschaltet, erzeugt der Konnektor keine
  Sorgeberechtigten-CSV mehr. Die bereits angelegten Konten und ihre Verknüpfungen bleiben
  dann ohne Löscherkennung in UCS@school stehen und müssen von Hand aufgeräumt werden.

### Benutzung

#### Abstimmung

* Für die Verwendung dieser Anbindung von UCS@School an moin.schule ist ein API Key für den Zugriff auf die Schülerdatenbank Niedersachsen nötig. Bitte nehmen Sie [Kontakt mit unserem Vertrieb](https://www.univention.de/kontakt/) auf, so dass auch die entsprechenden Voraussetzungen mit dem Betreiber N21 geklärt werden können.
* Falls bereits eine Installation mit UCS@School aktiv ist, müssen die aktuell gesetzten Attribute `record_uid` und `source_uid` genau betrachtet werden. Eine [Migration von record_uid und source_uid](https://help.univention.com/t/q-a-can-i-set-record-uid-and-or-source-uid-to-users-who-were-added-manually/15393) kann notwendig sein. Es wird empfohlen dies zuerst in einem getrenntem Bereich, abgeschirmt von der produktiven Schul-Umgebung, auszuprobieren.
   * die `source_uid` der Benutzer wird dann "sanis" sein.
   * die `record_uid` enthält die eindeutige Id von moin.schule.
* Es wird die [UCS@school - CLI-Import Schnittstelle](http://docs.software-univention.de/ucsschool-import/5.0/de/) verwendet, mit moin.schule ändert sich ggf. das Mapping der json-Dateien
   * z.B. Nachname wird Familenname

#### Vorbereitung

Diese Schritte müssen nur einmalig getan werden, bevor man den Import zum ersten Mal startet, und natürlich auch, wenn sich an den Bedingungen etwas geändert hat.

* Paket-Installation:
   * Einbindung des [Cool Solutions Repository](https://help.univention.com/t/cool-solutions-articles-and-repository/11517) auf dem primary System.
   * Installation des Pakets `univention-install univention-sanis` sowie benötigte Abhänigkeiten werden automatisch installiert.
* Erzeugen oder überprüfen Sie die UCR Variablen, die von den Skripten benutzt werden:
   * `sanis_import/url/token` und `sanis_import/url/api` sind HTTP(s) Links zu den Eintrittspunkten der SANIS API ("token" für die Anmeldung, "api" für die eigentliche Datenschnittstelle). Das Paket liefert diese beiden Variablen so aus, daß sie auf die Staging-Instanz des Landes Niedersachsen zeigen. Für die Überführung in die produktive Nutzung müssen diese URLs geändert werden.
   * `sanis_import/school_name_attribute`: hier muß der Name des SANIS Attributes angegeben werden, das dazu dient, "Organisationen" (Schulen) zu identifizieren. Die SANIS Datenstruktur erlaubt es, Schulen an den Attributen 'kennung', 'kuerzel' oder 'name' zu identifizieren; voreingestellt ist 'kennung'.
      * z.B. ucr set sanis_import/school_name_attribute=name
   * Weitere Variablen der Form `sanis_import/school/<schulname_in_ucs>=<schulidentifikation_in_sanis>`. Jede dieser Variablen ordnet eine Schule (in UCS@school) einer Organisation in SANIS zu, aus der die Daten für diese Schule zu holen sind.
      * z.B. ucr set sanis_import/school/GB80=Univentionschule1
* Erzeugen Sie die Datei mit den Zugangsdaten, die Sie vom SANIS Projekt erhalten haben:
   * Dateiname: /etc/sanis.secret -> muß genau zwei Zeilen haben, die erste mit der CLIENT_ID, die zweite mit dem CLIENT_SECRET, das Sie erhalten haben.
   * Sie können diesen Schritt auch überspringen: der Skript `create_input_files` kann die Datei auch anlegen, wenn sie noch nicht existiert. Dann werden Sie nach diesen beiden Angaben gefragt, und die Datei wird für Sie angelegt.
   * ACHTUNG: Wenn Sie vom Testbetrieb auf den Produktivbetrieb übergehen, werden Sie neue Zugangsdaten bekommen. Entweder Sie ändern die Zugangsdaten manuell mit einem Editor, oder Sie löschen die Datei /etc/sanis.secret und lassen sie beim nächsten Import wieder erzeugen.
* Kopieren Sie die Datei `/usr/share/univention-sanis/user_import_sanis_example.json` nach `/var/lib/ucs-school-import/configs/user_import_sanis.json`. Überprüfen und ergänzen Sie die kopierte Datei bezüglich der 'csv->mapping' und 'schema' Einträge entsprechend den Vorgaben Ihrer Einrichtung.
* Optionale Aktivierung des Imports von Kursen aus SANIS:
   * Über die Variable `sanis_import/activate_courses_import` kann mit dem Wert `yes` das Auslesen von Gruppenmitgliedschaften des Typs "Kurs" aus SANIS aktiviert werden. Die Kurse werden dann wie die Klassen in die Ausgabedateien geschrieben und bei einem Import auch als UCS@school Klassen behandelt. Zur Identifizierung können Kurse einen zusätzlichen Prefix für den Import erhalten.
   * Der Prefix für Kurse lässt sich über die Variable `sanis_import/courses_prefix` definieren. Ein Trennzeichen, wie z.B. `_`, kann am Ende des Prefix verwendet werden. Ein Leerzeichen und `-` sind als Trennzeichen nicht zulässig, da sie zu Fehlverhalten im Importer führen. Trennzeichen unterliegen ebenfalls der Funktion des Konfigurationsparameter `school_classes_invalid_character_replacement` des Imports, mehr Informationen dazu in der [Dokumentation](https://docs.software-univention.de/ucsschool-import/latest/de/configuration/format.html#cmdoption-arg-school_classes_invalid_character_replacement). Wird kein Prefix definiert, wird nur der aus SANIS ausgelesene Name des Kurses in die Ausgabedatei geschrieben.
   * Kursnamen werden auf Buchstaben und Zahlen bereinigt, Umlaute und Sonderzeichen sowie Leerzeichen werden aus dem Kursnamen entfernt.

#### Run import

Einen Import der SANIS Daten führen Sie dann folgendermaßen durch:

* Erzeugen Sie ein Arbeitsverzeichnis, in dem der Import stattfinden soll, und wechseln Sie in dieses Verzeichnis. Hier werden die Ergebnisse des Imports abgelegt in Form von json und csv Dateien, sowie Skript erzeugt für den regulären Import in UCS@School.
   * z.b. mkdir ~/sanis; cd ~/sanis
* Wenn Sie vorher überprüfen wollen, ob der Import alles so tut wie erwartet, rufen Sie nun `/usr/share/univention-sanis/create_import_files --dry-run` auf. Dies erzeugt eine Reihe von Dateien:
   * sanis_<typ>.json: das sind die Daten, die SANIS geliefert hat, jeweils eine Datei pro abgefragten Objekttyp.
   * store_<typ>.csv: das sind die daraus extrahierten Datentabellen, auch jeweils eine Datei pro Typ. Zu beachten ist, daß aus manchen SANIS Objekttypen mehrere Tabellen entstehen.
   * import_<schule>_<rolle>.csv: dies sind die eigentlichen Importdateien. Es wird pro Schule und Benutzerrolle jeweils eine solche Datei erzeugt.
   * temp_test_import.json: das ist eine für den Testlauf geeignete Importkonfiguration. Sie wird im nächsten Schritt für den Testlauf benutzt.
   * test_run_import: Dies ist der Skript, der alle Importe nacheinander ausführt, alle im `--dry-run` Modus. Es wird also kein wirklicher Import ausgeführt, aber Sie können die Logdateien auswerten, aus denen Sie sehen, was ein wirklicher Import tun würde.
   * führen Sie den Skript aus: `./test_run_import`. Danach finden Sie pro Schule und Benutzerrolle jeweils die Dateien `summary_<schule>_<rolle>.csv` und `import_<schule>_<rolle>.log` vor, die Sie zur Überprüfung heranziehen können.
* Wollen Sie den Import jetzt durchführen, rufen Sie `/usr/share/univention-sanis/create_import_files` auf. Dies erzeugt eine neue Konfiguration `temp_import.json`, einen neuen Skript `run_import` und die dazugehörigen Eingabedateien import_<schule>_<rolle>.csv.
   * Führen Sie den erzeugen Skript `./run_import` aus. Jetzt wird wirklich importiert, das kann lange dauern. Wie bei jedem anderen Import: Sie sollten diesen Vorgang nicht abbrechen.
   * Die Ergebnisdateien (Zusammenfassung und Paßwortdateien für neue Nutzer) finden Sie dann in den Verzeichnissen, die der UCS@school Import dafür vorsieht, siehe [Ablauf des Importvorgangs](https://docs.software-univention.de/ucsschool-import/5.0/de/procedure.html).


#### Hinweise

* Wenn die Ergebnisse eines Importes nicht so sind, wie Sie es erwartet haben: bitte versuchen Sie nicht, an den Zwischendateien Dinge zu ändern und Importe zu wiederholen. Das mag auf den ersten Blick als einfache Lösung erscheinen, aber der nächste Import aus SANIS wird Ihre Änderungen wieder überschreiben. Besser Sie sorgen dafür, daß die Daten in SANIS korrigiert werden, und fahren dann einen weiteren Import.
* Wenn Sie feststellen, daß Benutzerkonten durch den Import gelöscht wurden, so ist das kein großes Problem. Anstatt Nutzer wirklich zu löschen, werden sie nur deaktiviert und in eine sog. "Limbo-OU" verschoben ([Single source, Partial import](http://docs.software-univention.de/ucsschool-umc-user-import/5.0/de/single-source.html)) und verbleiben dort noch 90 Tage deaktiviert. Wenn Sie nach erfolgten Korrekturen den SANIS Import das nächste Mal durchführen und die Benutzer werden nun doch wieder benötigt, werden sie lediglich aus der Limbo-OU zurück in eine reale Schule verschoben und wieder aktiviert.
* Wenn Sie vom Testbetrieb auf den Produktivbetrieb übergehen, müssen Sie die entsprechenden UCR Variablen ändern (URLs zur API, Zuordnung der Schulen) und auch die Datei mit den Zugangsdaten.
