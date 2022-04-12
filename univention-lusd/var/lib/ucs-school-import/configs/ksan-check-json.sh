#!/bin/bash
#
# alle json-Dateien auf Validität überprüfen.
# Benötigt das Paket jsonlint
#                 Thorsten Strusch 2020-03-10

#(for i in /var/lib/ucs-school-import/configs/*json; do echo -n "$(basename $i) :"; jsonlint-php $i; done)|column -t -s:
(for i in /var/lib/ucs-school-import/configs/*json; do echo -n "$(basename $i) :"; python -m json.tool $i; done)|column -t -s:
