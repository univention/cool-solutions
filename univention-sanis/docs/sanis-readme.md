## Package: univention-sanis

A helper for UCS@school user import from SANIS (official name 'moin.schule')
In diesem Paket finden Sie ein Werkzeug, mit dem Sie Benutzerdaten aus SANIS (offizieller Projektname: moin.schule) importieren können.

### Inhalt

* Ein Hilfsskript `create_input_files`, welches Daten aus SANIS liest, Konfiguration vorbereitet, und einzelne Importdateien (pro Schule und Benutzerrolle) aus dem Datenbestand extrahiert.
* Eine für diesen Anwendungsfall vorbereitete Konfiguration. Zusätzlich wird die beschriebene Konfiguration für "[Single source, Partial import](http://docs.software-univention.de/ucsschool-umc-user-import/5.0/de/single-source.html)" benutzt, um einen Schulwechsel zu ermöglichen
   * z.B. /usr/share/ucs-school-import/scripts/create_ou limbo

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

#### Run import

Einen Import der SANIS Daten führen Sie dann folgendermaßen durch:

* Erzeugen Sie ein Arbeitsverzeichnis, in dem der Import stattfinden soll, und wechseln Sie in dieses Verzeichnis. Hier werden die Ergebnisse des Imports abgelegt in Form von json und csv Dateien, sowie Skript erzeugt für den regulären Import in UCS@School.
   * z.b. mkdir ~/sanis; cd ~/sanis
* Wenn Sie vorher überprüfen wollen, ob der Import alles so tut wie erwartet, rufen Sie nun `/usr/share/univention-sanis/create_import_files --dry-run` auf. Dies erzeugt eine Reihe von Dateien:
   * sanis_<typ>.json: das sind die Daten, die SANIS geliefert hat, jeweils eine Datei pro abgefragten Objekttyp.
   * store_<typ>.csv: das sind die daraus extrahierten Datentabellen, auch jeweils eine Datei pro Typ. Zu beachten ist, daß aus manchen SANIS Objekttypen mehrere Tabellen entstehen.
   * import_<schule>_<rolle>.csv: dies sind die eigentlichen Importdateien. Es wird pro Schule und Benutzerrolle jeweils eine solche Datei erzeugt.
   * temp_test_import.json: das ist eine für den Testlauf geeignete Importkonfiguration. Sie wird im nächsten Schritt für den Testlauf benutzt.
   * run_test_import: Dies ist der Skript, der alle Importe nacheinander ausführt, alle im `--dry-run` Modus. Es wird also kein wirklicher Import ausgeführt, aber Sie können die Logdateien auswerten, aus denen Sie sehen, was ein wirklicher Import tun würde.
   * führen Sie den Skript aus: `./run_test_import`. Danach finden Sie pro Schule und Benutzerrolle jeweils die Dateien `summary_<schule>_<rolle>.csv` und `import_<schule>_<rolle>.log` vor, die Sie zur Überprüfung heranziehen können.
* Wollen Sie den Import jetzt durchführen, rufen Sie `/usr/share/univention-sanis/create_import_files` auf. Dies erzeugt eine neue Konfiguration `temp_import.json`, einen neuen Skript `run_import` und die dazugehörigen Eingabedateien import_<schule>_<rolle>.csv.
   * Führen Sie den erzeugen Skript `./run_import` aus. Jetzt wird wirklich importiert, das kann lange dauern. Wie bei jedem anderen Import: Sie sollten diesen Vorgang nicht abbrechen.
   * Die Ergebnisdateien (Zusammenfassung und Paßwortdateien für neue Nutzer) finden Sie dann in den Verzeichnissen, die der UCS@school Import dafür vorsieht, siehe [Ablauf des Importvorgangs](https://docs.software-univention.de/ucsschool-import/5.0/de/procedure.html).


#### Hinweise

* Wenn die Ergebnisse eines Importes nicht so sind, wie Sie es erwartet haben: bitte versuchen Sie nicht, an den Zwischendateien Dinge zu ändern und Importe zu wiederholen. Das mag auf den ersten Blick als einfache Lösung erscheinen, aber der nächste Import aus SANIS wird Ihre Änderungen wieder überschreiben. Besser Sie sorgen dafür, daß die Daten in SANIS korrigiert werden, und fahren dann einen weiteren Import.
* Wenn Sie feststellen, daß Benutzerkonten durch den Import gelöscht wurden, so ist das kein großes Problem. Anstatt Nutzer wirklich zu löschen, werden sie nur deaktiviert und in eine sog. "Limbo-OU" verschoben ([Single source, Partial import](http://docs.software-univention.de/ucsschool-umc-user-import/5.0/de/single-source.html)) und verbleiben dort noch 90 Tage deaktiviert. Wenn Sie nach erfolgten Korrekturen den SANIS Import das nächste Mal durchführen und die Benutzer werden nun doch wieder benötigt, werden sie lediglich aus der Limbo-OU zurück in eine reale Schule verschoben und wieder aktiviert.
* Wenn Sie vom Testbetrieb auf den Produktivbetrieb übergehen, müssen Sie die entsprechenden UCR Variablen ändern (URLs zur API, Zuordnung der Schulen) und auch die Datei mit den Zugangsdaten.
