# Readme for univention-munin

This package is part of [cool-solutions](https://wiki.univention.de/index.php/Category:Cool_Solutions_Repository#Integration_in_UCS_3.2.2C_4.0.2C_4.1.2C_4.2.2C_4.3). You need to activate the repository:
```bash
ucr set repository/online/component/cool-solutions=yes \
repository/online/component/cool-solutions/version="current" \
repository/online/component/cool-solutions/unmaintained=yes \
repository/online/unmaintained='yes'
```
Furter information can be found [here](https://wiki.univention.de/index.php?title=Cool_Solution_-_Install_and_integration_of_Munin).

- `univention-munin-server`: Only required once in a domain. Can be installed on every server role.
- `univention-munin-node`: Required on all servers you want to monitor.

# Hints for QA:
 Du benötigst mindestens einen UCS5.
 Das Paket ist weder gebaut noch veröffentlicht.
 Eine Installation von `univention-munin-server` benötigt die vorherige Installation von `univention-munin-node`.

Ich bin in etwa so vorgegangen:
```bash
apt install ./univention-munin-node_1.2.0-6_all.deb
apt install ./univention-munin-server_1.2.0-6_all.deb

hostname="backup.test.intranet"
ip="10.200.37.61/24"

ucr set munin/node/allowedhosts="$ip"
cat  >> /etc/munin/munin-conf.d/backup.test.intranet <<%EOF
[$hostname]
   address $ip
%EOF
```
`sudo -u munin /usr/bin/munin-cron`: Starte manuell.

Wichtig wären, ob die Konfigurationsdateien und Templates richtig erstellt werden.
