## Package: univention-sanis

A helper for UCS@school user import from SANIS (official name 'moin.schule')

<img src="flowchart.png" alt="flowchart" style="width:70%;"/>

### Contents

* A helper script that imports the current user data from SANIS, using a well-documented REST API, using contractually agreed credentials. The script produces CSV files suited for a so-called SiSoPi import (single source, partial import) into all schools of one UCS@school domain, and it produces a script that will execute all these imports in one run.
* An import config file that matches the API conditions, field names and other details needed for the SiSoPi import.

### Usage

#### Preparation

These steps have only to be done once, or again when important conditions change (credentials, schools to include, etc.)

* Create the corresponding UCR variables that map between the schools to import and their identification in SANIS:-
   * sanis_import/school_name_attribute: this is expected to be the attribute out of the SANIS organization which is used to associate a school to a SANIS organization.
   * sanis_import/school/<schoolname>=<sanisname> this associates the school <schoolname> (in ucs@school) to a SANIS organization, matching the school_name_attribute above. You should create those tuples for each school that shall be included in the import.

#### Run import

Whenever you want to start an import using SANIS data, you have to:-

* Create a working directory for all the intermediate files, and change into it. This is mainly for auditing purposes; if a given import run finished successfully then you can safely delete this directory and all the files in it. You will find there:
   * the raw JSON files, exactly as the SANIS API returned to us
   * the CSV files extracted from the SANIS data, already split by school and user role, exactly as we'll feed them into UCS@school
   * the merged import config which is to be used to import data into UCS@school
   * NOTE you won't find the import summary or password files of the import jobs here: these are always saved into the central directory below /var/lib/ucs-school-import.
* Create an API configuration file containing the credentials (Client ID, client secret) for API access. The file is expected to be a text file with exactly two lines: the client id and the client secret each on a separate line. If `create-import-files` has finished you can immediately delete this file.
* Run the script `/usr/share/univention-sanis/create-import-files`. This will create CSV files (named by school+user role) plus a script that can import these files in one run.
   * Afterwards, you CAN examine what the import would do. (read all the files it created, and check manually)
   * You can run the script being created with two arguments (school and user role): this will simulate (dry-run) the import and give a summary about the actions. In this case, the import logs aren't written into the central directory but into the current working directory, and the log level is set to verbose.
* Run the script created in step #1 without arguments.
   * You don't have to take care of collecting what the script says: everything is printed on STDERR and simultaneously into a log file.
   * The script prints the names of the log files and password files, separately for each school and user role.
* Transfer the password files (and optionally: the logs) to the corresponding school admins / responsible persons
   * Better you keep the current directory until you have confirmation from all the schools.
   * If you get information that something did not work out: Please never try to edit the files (json, csv or config) and try to rerun the import! This may seem to yield the intended results, but the next SANIS import will likely correct your corrections. The preferred way is to notify the data producers that feed their data into SANIS, let them correct their data, and re-run the full SANIS import.
