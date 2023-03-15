# univention-ssh-key-sync

This cool solution adds SSH keys to your LDAP. This can be used during SSH login to check access of your users against the key stored in LDAP. So you don't need to copy SSH keys between your servers anymore.

Write access to ssh keys is given to members of the Group Domain Admins only.


## Installation

[Enable the cool solutions repository](https://help.univention.com/t/cool-solutions-articles-and-repository/11517) and install the package:
`univention-install univention-ssh-key-sync`


## Test
Before you turn this on, it is recommended to test if this works.

1. Add a public key to a user, e.g. "my_ssh_user". You can do this in the UMC user module under "account"
2. If you execute `/usr/share/univention-ssh-key-sync/ldap-keys.sh <uid>` you should get the SSH key back.

Example:
`/usr/share/univention-ssh-key-sync my_ssh_user`
```
ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC9G9l0yMDQsnt1T89eGaNBcXZQ06sjR4Mbgc0b5/gdFuTyxEdodAq/9SMP/HHg2Hs859fS5IYBWVyPrxK5apCPEDoJQqxvVs23iOoH026aJIXQFS7Q7HiMPX7mJhvrn9wnpxFvbC4T1KNX1b2cIjAZPFO/gwuyxm/QgzlqQha1ZwQr/7IFKy9U4LmFQx83NCk66M05uf1kv89MxAB4MMSTlbasSSDYnjrJha1V+sleo0dnZm4Kl6mI416ZDILYPUtzenAB31h9fh9RNr6580KHmxiOm/ezmARFNiMJ81uh7+KpApm/azg3NaypoAFDHG/Y2RYm4KBsDJcru0BQ61XBSZKYzkoFeAHcMbQZncrHR7Kjq/fW/gePK+4N76/Px60aeZ79kdM4Nvp5hpCB2LdnnAC7YM9JA4RRBfgSoIXXF6QrFpwKFXPuJkJYwSu1/qBGpRfu02QUHJv5OXuUMshmHCJeOg/iZoMmwpGuKUcfJKIzb0Yhx2wMmnCuwZmDHsc=
```

## Configuration

**Attention**: make sure to add your SSH public keys BEFORE you reconfigure your ssh daemon. Otherwise you might lock yourself out!

```
ucr set \
	sshd/AuthorizedKeysCommand="/usr/share/univention-ssh-key-sync/ldap-keys.sh" \
	sshd/AuthorizedKeysCommandUser=root \
	sshd/AuthorizedKeysFile="/etc/ssh/authorized_keys" \
	sshd/ChallengeResponseAuthentication=no \
	sshd/PubkeyAuthentication=yes \
	sshd/UsePAM=no
```
(Or put this into an UCR policy as you might want to have this domain wide)

If you don't set a system-wide, root-owned authorized_keys file, then every user would be able to add own keys to the home folder, which you want to avoid.

The authorized_keys file may be empty, then every SSH login will be checked against the LDAP. You can also add some keys there, with this you **skip the check** for these keys.

Furthermore, we explicitly want password authentication during domain join:
```
ucr set \
    'sshd/config/Match Group="DC Slave Hosts,DC Backup Hosts"' \
    sshd/config/PasswordAuthentication=yes
```
Instead of "DC Slave Hosts" & "DC Backup Hosts", you can choose any other group(s) here, as long as it fulfills the criteria for a [join account](https://docs.software-univention.de/manual/5.0/en/domain-ldap/domain-join.html#domain-ldap-subsequent-domain-joins-with-univention-join).

When done, restart your SSH server: `systemctl restart sshd.service`


## Technical Background


From [man 5 sshd_config](https://www.mankier.com/5/sshd_config#AuthorizedKeysCommand)

> AuthorizedKeysCommand
>
> Specifies a program to be used to look up the user's public keys. The program must be owned by root, not writable by group or others and specified by an absolute path. Arguments to AuthorizedKeysCommand accept the tokens described in the Tokens section. If no arguments are specified then the username of the target user is used.
>
> The program should produce on standard output zero or more lines of authorized_keys output (see AUTHORIZED_KEYS in sshd(8)). AuthorizedKeysCommand is tried after the usual AuthorizedKeysFile files and will not be executed if a matching key is found there. By default, no AuthorizedKeysCommand is run.

Sources:
https://web.archive.org/web/20221129203633/https://harz.freifunk.net/wiki/doku.php/anleitungen/openldap/ssh_pulickey
