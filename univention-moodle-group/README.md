# Cool Solution - Install Moodle / Advanced LDAP Enrollment

[help.univention.de](https://help.univention.com/t/cool-solution-install-moodle-advanced-ldap-enrollment/21318)

UCS@School contains students and teachers in one group with the same attributes in the LDAP. Moodle, however, expects them to be in different groups or LDAP attributes. This Cool Solution contains a listener that places the users in different attributes depending on their UCS@School role.

**Prerequisites**

This article is based on a successful installation of Moodle and one authentication method accomplished by following our [Cool Solution - Install Moodle](https://help.univention.com/t/cool-solution-install-moodle/12258) and assumes you already have authentication configured either via [SAML authentication](https://help.univention.com/t/cool-solution-install-moodle-saml-authentication/12299) or [LDAP authentication](https://help.univention.com/t/cool-solution-install-moodle-ldap-authentication/12297).

Tested with moodle 4.1.2

**LDAP Search User**
If you are using SAML, you will need to set up a simple authentication account for the LDAP lookups. Follow [Cool Solution - LDAP search user / simple authentication account](https://help.univention.com/t/cool-solution-ldap-search-user-simple-authentication-account/11818) to do so now.

**Installing the Cool Solution Listener**
Please enable the [Cool-Solutions Repository for UCS 5.0](https://help.univention.com/t/cool-solutions-articles-and-repository/11517) Afterward, you can install the Listener with:
```
univention-install univention-moodle-group
```
The listener will now place students in univentionFreeAttribute20 and teachers into univentionFreeAttribute19.

**Enabling the LDAP enrollment plugin**
After successfully setting up an authentication method, you can now configure LDAP enrolments to enroll your UCS@school users into moodle courses automatically.

First, enable the LDAP enrolment plugin under Site Administration -> Plugins -> Enrolments. This plugin is already installed and only needs to be activated by pressing the icon in the Enable section.

To log in with the local moodle administrator account after you have set up SAML authentication, use https://<YOUR_MOODLE_SERVER_FQDN>/moodle/login/index.php?saml=off

To open the login page and sign in.

**LDAP enrollment settings**

After the plugin is enabled, open the plugin-settings.

LDAP Server Settings
| Setting | Value|
|---|---|
| Host URL | ldaps://<server FQDN>:7636 |
| Use TLS | No |
| Version | 3 |
| LDAP encoding| utf-8 |
| Page size | 250 |
Bind settings:
| Setting | Value|
|---|---|
| Bind user distinguished name | uid=<Bind/User/Cn>,cn=users,<ldap/base> |
| Password | Password |
Role Mapping:
| Role | LDAP contexts| Ldap member attribute |
|---|---|---|
|Teacher| ou=<School/OU>,<ldap/base> | univentionFreeAttribute19 |
|Student| ou=<School/OU>,<ldap/base> | univentionFreeAttribute20 |
Role Settings:
| Setting | Value|
|---|---|
| Search subcontexts | Yes |
| Member attributes uses dn | Yes |
| Contexts | cn=schueler,cn=groups,ou=<School/OU>,<ldap/base>;cn=lehrer,cn=groups,ou=<School/OU>,<ldap/base> |
| Search subcontexts | Yes |
| User type | Default |
| Dereference aliases | No |
| UD number attribute | uidnumber |
Course enrolment settings:
| Setting | Value|
|---|---|
| Object Class | objectClass=posixGroup |
| ID number | cn |
| Short name | cn |
| Full name | cn |
| Summary |  description|
| Ignore hidden courses | No |
| External unenroll action | Unenrol user from course |
Automatic course creation settings:
| Setting | Value|
|---|---|
| Auto create | Yes |
| Category | Miscellaneous |
| Template |  |
Automatic course update settings:
| Setting | Value|
|---|---|
| Update short name | Yes |
| Update full name | Yes |
| Update summary | Yes |
Nested groups settings:
| Setting | Value|
|---|---|
| Nested groups | Yes |
| 'Member of' attribute | memberof |

Nested groups allow you to assign groups to classes and workgroups instead of adding individual users.

**Troubleshooting**

If you run into issues regarding permissions or elements of the moodle webpage not loading properly, you can try to solve the issue by executing the following commands from the “Install Moodle” 14 Cool Solution:

`chown www-data:www-data /var/www/moodle/config.php`

`chmod 640 /var/www/moodle/config.php`

`chown -R www-data:www-data /var/moodledata`

`find /var/moodledata -type f -exec chmod 600 {} \;`

`find /var/moodledata -type d -exec chmod 700 {} \;`

**Further links**

Moodle LDAP enrollment documentation: [Moodle docs](https://docs.moodle.org/39/en/LDAP_enrolment)
