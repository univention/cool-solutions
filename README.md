
**Note:** Cool Solutions are articles documenting additional functionality based on Univention products. Packages provided by a Cool Solutions Repository are built by Univention professional service, but will not necessarily be maintained. Not all the shown steps in the article are covered by Univention Support. For questions about your support coverage, contact your contact person at Univention before you want to implement one of the shown steps.

Further documentation & discussion at: <https://help.univention.com/t/cool-solutions-articles-and-repository/11517>


# Introduction

Cool Solutions are articles documenting additional functionality based on Univention products. Packages provided by a Cool Solutions Repository are built by Univention, but will not be maintained.
Not all of the shown steps in the article are covered by Univention Support. For questions about your support coverage contact your contact person at Univention before you want to implement one of the shown steps.

# Repository integration

Some solutions need special packages build by Univention. These packages are provided in a Cool Solutions Repository. There are different possibilities to integrate the Cool Solutions Repository.

In the Univention Management Console, Software tab, open the module *Repository settings* and add a new repository component with Component Name *cool-solutions* and Advanced Setting *Use unmaintained repositories*.

Alternatively, set the following Univention Configuration Registry variables on the console:

> ucr set repository/online/component/cool-solutions=yes \\
> repository/online/component/cool-solutions/version=current \\
> repository/online/component/cool-solutions/unmaintained=yes

# Upgrade
If you have a cool solution repository integrated and plan to upgrade, please check if the Cool Solution is already available for your target UCS Version.

# Source Code

All Cool Solutions packages and their source code can be found at our [github mirror](https://github.com/univention/cool-solutions). Feel free to fork the code repository, enhance a package and start a pull request.


# Overview of packages

| Name                                      | description                                                                                 | state                        | Link                                                                                                               | Comment                                                       | Customer(s)   | responsible  |
|-------------------------------------------|---------------------------------------------------------------------------------------------|------------------------------|--------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------|---------------|--------------|
| `univention-custom-ldap-acls`             | LDAP attributes to define custom LDAP ACLs                                                  | in progress                  | [Issue](https://git.knut.univention.de/univention/prof-services/cool-solutions/-/issues/6)                         |                                                               |               |              |
| `univention-demo-data`                    | Demo data provied by the "Deutsche Wolke"                                                   | outdated                     |                                                                                                                    | Jan-Luca: Used for our demo instance demo.univention.de       | univention    |              |
| `univention-guacamole-ldap-connection`    | Guacamole installation wrapper                                                              | superseded by Appcenter      | [Appcenter](https://www.univention.de/produkte/univention-app-center/app-katalog/guacamole/)                       |                                                               |               |              |
| `univention-ldap-restore`                 | Restore LDAP objects from LDIF backups                                                      | ported to UCS5               | [Help](https://help.univention.com/t/cool-solution-restore-ldap-objects-attributes-and-memberships/20839)          | Dirk, Oliver                                                  |               |              |
| `univention-lusd`                         | Custom UCS@school import reader class for an import of XML encrypted data (LUSD)            | ported to UCS5               | [Help](https://help.univention.com/t/cool-solution-lusd-erweiterung-fur-ucs-5-0/20176)                             | Stadt Kassel, LK Kassel, Fulda, Wetteraukreis                 | Tim, Oliver   |              |
| `univention-moodle-group`                 | Put Teachers and Students into extended attributes for moodle                               | ported to UCS5, docs missing |                                                                                                                    | Kevin: Developed for UCS 5 (Q2/2022) | Digital Cloak | Kevin        |
| `univention-munin`                        | munin server and node support                                                               | not tested for UCS5          | [Wiki](https://wiki.univention.de/index.php?title=Cool_Solution_-_Install_and_integration_of_Munin)                |                                                               |               |              |
| `univention-nextcloud-groupfolders-sync`  | sync UCS groups to nextcloud groupfolders                                                   | outdated                     |                                                                                                                    | Robert: maybe still needed in Fulda (UCS5 upgrade in Q1/2023) | Fulda         | Robert       |
| `univention-nextcloud-samba-share-config` | listener module configuration of Samba share access in Nextcloud                            | in progress                  | [Merge Request](https://git.knut.univention.de/univention/prof-services/cool-solutions/-/merge_requests/11)        |                                                               |               |              |
| `univention-printer-assignment`           | Assign printers to groups containing computers                                              | not tested for UCS5          |                                                                                                                    | Seems to still work with python 2.7                           | LMZ           | LukasR       |
| `univention-ro-wo-group-dirs`             | Listener module to configure read-only and write-only folders in class and workgroup shares | not tested for UCS5          |                                                                                                                    |                                                               |               |              |
| `univention-samba-config-ransomware`      | Configuration for Samba to implement full_audit logging for shares                          | not tested for UCS5          |                                                                                                                    |                                                               |               |              |
| `univention-set-samba4-profile-path`      | Bulk setting of the samba 4 profile path                                                    | not tested for UCS5          |                                                                                                                    |                                                               |               |              |
| `univention-sudo-ldap-host`               | sudo-ldap integration - host integration                                                    | not tested for UCS5          |                                                                                                                    |                                                               |               |              |
| `univention-sudo-ldap-server`             | sudo-ldap integration - domain integration                                                  | in progress                  | [Merge Request](https://git.knut.univention.de/univention/prof-services/cool-solutions/-/merge_requests/14)        |                                                               |               |              |
| `univention-user-group-sync-dest`         | import transferred user and group information                                               | in progress                  | [Merge Request](https://git.knut.univention.de/univention/prof-services/cool-solutions/-/merge_requests/9)         |                                                               |               |              |
| `univention-user-group-sync-source`       | store user and group information to be transferred                                          | in progress                  | [Merge Request](https://git.knut.univention.de/univention/prof-services/cool-solutions/-/merge_requests/9)         |                                                               |               |              |
| `univention-usercert`                     | usercert extension                                                                          | ported to UCS5               | [Help](https://help.univention.com/t/cool-solution-creation-and-management-of-user-and-windows-certificates/11782) |                                                               | LTBB          | Timo, Jannik |

