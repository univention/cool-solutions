## Package: univention-sanis

A helper for UCS@school user import from SANIS (official name 'moin.schule')

<img src="flowchart.png" alt="flowchart" style="width:70%;"/>

### Contents

* A helper script that imports the current user data from SANIS, using a well-documented REST API, using contractually agreed credentials. The script produces CSV files suited for a so-called SiSoPi import (single source, partial import) into all schools of one UCS@school domain.
* An import config file that matches the API conditions, field names and other details needed for the SiSoPi import.

### Usage

#### Preparation

These steps have only to be done once, or again when important conditions change (credentials etc.)

* Activate SiSoPi import configuration according to docs: https://.... using the sanis import config file (/usr/share/..wo liegen die.../import-sanis.json)
* Create an API configuration file containing the credentials (Client ID, client secret) for API access. (FIXME: command line to make the file)

#### Run import

Whenever you want to start an import using SANIS data, you have to run:-

* Run the script `/usr/share/univention-sanis/create-import-files`. This will create CSV files with timestamped names plus a script that can import these files in one run.
* Run the script created in step #1.

