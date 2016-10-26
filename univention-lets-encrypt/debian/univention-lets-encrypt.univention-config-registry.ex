Type: module
Module: univention-lets-encrypt.py
Variables: univention-lets-encrypt/.*

Type: file
File: etc/univention-lets-encrypt.conf
Variables: univention-lets-encrypt/.*

Type: multifile
File: etc/univention-lets-encrypt.conf

Type: subfile
File: etc/univention-lets-encrypt.conf
Variables: univention-lets-encrypt/.*
