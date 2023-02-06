# Readme for univention-munin

This package is part of [cool-solutions](https://wiki.univention.de/index.php/Category:Cool_Solutions_Repository#Integration_in_UCS_3.2.2C_4.0.2C_4.1.2C_4.2.2C_4.3). You need to activate the repository:
```
ucr set repository/online/component/cool-solutions=yes \
repository/online/component/cool-solutions/version="current" \
repository/online/component/cool-solutions/unmaintained=yes \
repository/online/unmaintained='yes'
```
Furter information can be found [here](https://wiki.univention.de/index.php?title=Cool_Solution_-_Install_and_integration_of_Munin).

Packages:
- `univention-munin-server`: Only required once in a domain. Can be installed on every server role.
- `univention-munin-node`: Required on all servers you want to monitor.
