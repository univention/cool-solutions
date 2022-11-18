# Cool Solution - Restore LDAP objects, attributes and memberships

## Installation
After enabling the Cool Solutions Repository (<https://help.univention.com/t/cool-solutions-articles-and-repository/11517>)
 you can install the package with the following command:
`univention-install univention-ldap-restore`

## Usage
After the package is installed you can restore a given DN from a backup file.

The usage is as follows:

`univention-restore-ldap-object-from-backup --dn [DN] -b [backup file]`

The script provides the following options:

| Option                                    | Effect                                                                    |
| ----                                      | ----                                                                      |
| -h, --help                                | show help message and exit                                                |
| -b BACKUP_FILE, --backup-file BACKUP_FILE | gz ldif backup file (/var/univention-backup/ldap-backup_20180604.ldif.gz) |
| -d DN, --dn DN                            | LDAP DN to look for in backup                                             |
| -l, --list-dns                            | list all LDAP DNs from backup and exit                                    |
| -v, --verbose                             | verbose output                                                            |
| -m, --restore-membership                  | restore uniqueMember of DN                                                |
| -r, --delete-missing                      | delete LDAP object if object is not in backup                             |
| -n, --dry-run                             | dry run, make no changes in LDAP                                          |

The script behaves as follows:
| DN was not found in LDAP, found in backup



The script behaves as follows:
| Prerequisite                                                                                                | Behaviour                                                      |
| ---                                                                                                         | ---                                                            |
| DN was not found in LDAP, found in backup                                                                   | object is restored from backup                                 |
| DN was found in LDAP, found in backup                                                                       | the object's attributes are restored (overwritten) from backup |
| uid, uidNumber, sambaSID, entryUUID of specified DN was found in other object than the specified DN in LDAP | no changes are made                                            |
| DN was found in LDAP, not found in backup, --delete-missing is set                                          | object is deleted from LDAP                                    |

## Usage examples

Restore deleted user object or overwrite attributes of existing user object with uid:
`example-user1` using backup file from 2018-06-14:

```
univention-restore-ldap-object-from-backup -d uid=example-user1,cn=users,dc=ucs,dc=demo \
-b /var/univention-backup/ldap-backup_20180614.ldif.gz
```

Restore deleted user object or overwrite attributes of existing user object with uid:
`example-user1` with group memberships using backup file from 2018-06-14:

```
univention-restore-ldap-object-from-backup -m -d uid=example-user1,cn=users,dc=ucs,dc=demo \
-b /var/univention-backup/ldap-backup_20180614.ldif.gz
```

Delete existing user object with uid example-user1 because it's not present in backup:

```
univention-restore-ldap-object-from-backup -r -d uid=example-user1,cn=users,dc=ucs,dc=demo \
-b /var/univention-backup/ldap-backup_20180614.ldif.gz
```
