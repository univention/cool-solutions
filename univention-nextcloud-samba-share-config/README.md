# univention-nextcloud-samba-share-config

Nextcloud 7 is a free and open source file hosting service and available in the Univention App Center to easily install it on UCS. Nextcloud is capable of mounting external storages from different backends, including Samba shares. A few packages made by Univention enable you to automatically mount your UCS@school shares such as class or workgroup shares. To install these, the Cool Solutions Repository must be enabled.

## Prerequisites

The Nextcloud server must be able to access the SMB shares you intend to mount. To accomplish this, make sure that Port 445 on the Samba server(s) is reachable from the Nextcloud server.

A good way to test whether access works is smbclient. In a domain with the LDAP base dc=ucs,dc=local and a Samba server called fileserver a command could look as follows:

smbclient -U user@ucs.local //fileserver/share

smbclient will ask for the user’s password and try to connect. If it connects successfully, you will be prompted with an interactive shell on the Samba share.

## Nextcloud on external Host

If you do not use Nextcloud from Univention App Center, further requirements must be met.

The LDAP connection must be set up correctly in Nextcloud. To connect the home shares, the Nextcloud internal user name is used as the share name. By default, Nextcloud sets the UUID as the user name, while the UCS share uses the UID as the share name. Therefore, in Nextcloud under Settings -> LDAP/AD integration -> Expert -> Internal username attribute “uid” must be entered.

To mount Samba shares in Nextcloud the files_external Nextcloud app must be enabled. To enable the app, login to Nextcloud with an admin user (e.g. Administrator) and switch to Settings -> Apps. Look for External Storage support and click Enable. Alternatively, the app can be activated via the command line tool “occ”::

`sudo -u www-data php /var/www/html/occ app:enable files_external`

Replace “www-data” with the web server user and “/var/www/html/occ” with the path to occ.

To ensure that the external Nextcloud is actually used by the Cool Solution, the path to occ must be stored in the Univention Configuration Registry:

`ucr set nextcloud-samba-common/occ_path=/var/www/html/occ` → Path to occ on remote Nextcloud host

For the connection setup, the connection data to the Nextcloud host is set in UCR:

```
ucr set nextcloud-samba-share-config/nc_admin=nc_admin				# Nextcloud Admin User
ucr set nextcloud-samba-share-config/remoteUser=USER 				# user to SSH into remote Nextcloud host
ucr set nextcloud-samba-share-config/remotePwFile=/etc/nextcloudpw 	# PASSWORD FILE for USER on remote Nextcloud host
ucr set nextcloud-samba-share-config/remoteHost=nextcloud.localhost	# HOSTNAME or IP of remote Nextcloud host
```

## Enabling Nextcloud for users and groups

Nextcloud access can be enabled manually via the web interface UMC using the Users or Groups module. In the Users module, open a specific user, switch to Apps and tick the checkbox for Nextcloud Hub . In the Groups module, open a specific group, switch to Apps and tick the checkbox for Nextcloud Hub. After Nextcloud is installed, newly created users are automatically enabled in Nextcloud.

The package univention-nextcloud-enable-for-classes-and-workgroups from the Cool Solutions Repository enables all classes, workgroups and Domain Users groups for Nextcloud. This is required for the groups to show up in Nextcloud and be used there to limit access to shares to their respective groups. The package must be installed on the domaincontroller master of your domain!

univention-install univention-nextcloud-enable-for-classes-and-workgroups

## Mounting shares

Once the files_external app is enabled, external storage mounts can be configured via Settings → Administration → External Storages.
To configure external storages the share’s windows domain must be set in Nextcloud. Note that the windows domain might change between Samba updates. The windows domain can be obtained via UCR:

`ucr get windows/domain`

### Manual Configuration

A mount can be configured very easily with a generic mount. Configure the mount as follows and save it by clicking on the small tick icon. A red square (bad) or green circle (good) tells you whether access to the share was successful, with the currently logged in user.

Folder name: Home
External Storage: SMB/CIFS
Authentication: Log-in credentials, save in session
Configuration Host: hostname or ip
Configuration Share: /
Configuration Remote Subfolder: $user (for home share) or share name
Configuration Domain: windows domain
Available for: empty

### Automatic Configuration

The more shares and share servers there are, as with UCS@school multi-server environments with file servers at each school, the more time-consuming the manual setup becomes. To automate the configuration, Univention developed packages for that purpose, depending on the share type. The packages can be installed from the Cool Solutions Repository.

To automatically configure Home share mounts for ALL schools and Users in the domain, install the “univention-nextcloud-samba-home-share-config” package:

`univention-install univention-nextcloud-samba-home-share-config`

The package “univention-nextcloud-samba-group-share-config” automatically checks all groups that are enabled for Nextcloud and configures a mount for a share of the same name, if there is one.

If a Domain Users group is enabled, it configures the common share Marktplatz for that OU.
If you don’t want mounts for the Marktplatz share, set the following variable on the Nextcloud host before you install the package univention-nextcloud-samba-group-share-config:

`ucr set nextcloud-samba-group-share-config/ignoreMarktplatz=true`

The module can also configure mounts for UCS@school roleshares. Those are mostly used to give teachers access to student’s home directories. Since roleshares are not active and the relevant package is not installed by default, an UCR variable must be set before the installation to make the package configure mounts for them:

`ucr set nextcloud-samba-group-share-config/configureRoleshares=true`

The package comes from the Cool Solutions Repository and must be installed on the UCS server on which the shares are configured.

`univention-install univention-nextcloud-samba-group-share-config`

By default a common share called “Marktplatz” is configured for every school in UCS@school. Users can also create more shares available for all users via the web interface and mount them for all users in the Windows logon scripts using the UCR variable `ucsschool/userlogon/commonshares`.

To also configure a mount for all common shares on a certain server, the package univention-nextcloud-samba-common-share-config from the Cool Solutions Repository can be used. It is triggered on changes of ucsschool/userlogon/commonshares and configures a mount for the shares from that variable.

First, set a variable to configure univention-nextcloud-samba-common-share-config:

`ucr set nextcloud-samba-share-config/nextcloudGroup=nextcloud-users	# GROUP to allow acces to the common shares, should be Domain Users OU in most cases`

Afterwards the package can be installed:

`univention-install univention-nextcloud-samba-common-share-config`

Make sure to separate common shares with commas and no additional spaces like so:

`ucr set ucsschool/userlogon/commonshares=share1,share2`

## Removing mounts

The packages remove mounts when the corresponding group is deleted. To delete all configured mounts, you can use the following commands UCS Nextcloud is installed on:

```
univention-install jq
mountList=$(univention-app shell nextcloud sudo -u www-data /var/www/html/occ files\_external:list --output=json | jq ".\[\] | .mount\_id")
for mount in ${mountList}; do echo "Deleting mount ${mount}" ; univention-app shell nextcloud sudo -u www-data /var/www/html/occ files_external:delete --yes ${mount} ; done
```

## Regenerate mounts

To regenerate all mounts, use univention-directory-listener-ctrl to re-initialize the corresponding listener modules:

`univention-directory-listener-ctrl resync nextcloud-samba-group-share-config`
`univention-directory-listener-ctrl resync nextcloud-samba-home-share-config`,

You can follow the process in the listener.log:

`tail -f /var/log/univention/listener.log`
