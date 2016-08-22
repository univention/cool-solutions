Implementation notes for update-univention-printer-assignment:

The script is given a backlog file by the listener module.
The backlog file contains one DN per line. The script tries to load
all given objects of the backlog file and additionally it tries to
step the tree downwards to the hosts (Printer ==> Group ==> Host)
and loads those objects, too. E.g. if a printer DN is within the 
backlog file, then all groups referring to the printer are loaded and
in the next step all hosts that are member of the groups.

All objects that are loaded by the script, are cached in memory to avoid 
duplicate LDAP searches. After all backlog entries are processed, the
dictionary cache_hosts contains all hosts the vbscript has to be updated 
for.

In a second step for each host object of the host cache, the assigned 
printers are determined by looking at the host object itself or checking
all group objects the host ist member of. If all URNs for the assigned 
printers and the default printer is fetched, a vbscript template is loaded
and the variables (removeall, debug, printer list, default printer) is 
replaced by static values and written to disk as hostspecific vbscript.

The DNs may also be specified on the command line (instead of the backlog file).

There are three special cases:
1) A host object has been deleted
The script has no information about removed objects though it is not able to
determine the vbscript's filename of the deleted host.

2) A group object has been deleted
In this case the listener module does not write the group DN to the backlog file
but the DNs of all group members. If the DN of windows hosts are among them, the
vbscript will be updated accordingly.

3) A printer object has been deleted
Since the reference to printer objects is stored at host und computer objects, 
the script has to look for host and computer objects that are assigned to the
removed printer. This check is done, if a DN in the backlog is found that is 
no longer available in LDAP. It doesn't matter if the given DN of the deleted
object was no printer DN.
