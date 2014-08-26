MULTI-MASTER-SETUP
==================
This listener module pushes local users to a remote global UCS DC-Master
instance, which can then be used as a centralized authentication services.

1. Prerequisites
----------------
1. On the global DC master all LDAP schemas relevant to the users on any
satellite DC master must be installed.

2. The listener runs on the satellite DC masters and currently needs full LDAP
write access to the global DC master.
(In a future version this could be changed to using a dedicated principal which
only has permissions to create LDAP user objects in a dedicated section of the
LDAP DIT. In addition write access to the
"cn=uidNumber,cn=temporary,cn=univention,${ldap_base}" is needed for allocating
unique UID numbers.)

2. Installation
---------------

2.1 On global DC master
.......................
# Create group for all satellites or multiple groups for each satellite:
udm groups/group create --position "cn=groups,$(ucr get ldap/base)" --set name="dom1"

# Collect the following informations from the global DC master:
global_master="$(getent hosts "$HOSTNAME" | cut -d\  -f1)"
global_base="$(ucr get ldap/base)"
global_group="cn=DOM1,cn=groups,$global_base"
global_admin="cn=admin,$global_base"
global_users="cn=users,$global_base"
global_passwd="$(cat /etc/ldap.secret)"
global_krbrealm="$(ucr get kerberos/realm)"

2.2 On satellite DC masters
...........................
# Include Cool-Solutions repository on satellite DC masters:
ucr set repository/online/component/cool-solutions=yes repository/online/component/cool-solutions/parts=unmaintained

# Install packages on satellite DC masters:
univention-install multi-master-setup

# Configure satellites:
local_suffix=dom1
(umask 0600 ; echo -n "${global_passwd}" >/etc/ldap-global.secret ; chmod 0600 /etc/ldap-global.secret )
ucr set \
	multi-master-setup/remote/ldapuri="ldap://${global_master}:7389" \
	multi-master-setup/remote/binddn="${global_admin}" \
	multi-master-setup/remote/basedn="${global_base}" \
	multi-master-setup/remote/groupdn="${global_group}" \
	multi-master-setup/remote/suffix="$local_suffix" \
	multi-master-setup/remote/position="${global_users}" \
	multi-master-setup/remote/krbrealm="${global_krbrealm}" \
	multi-master-setup/remote/bindpw="/etc/ldap-global.secret" \
	multi-master-setup/local/pending="/var/lib/multi-master-setup"
invoke-rc.d univention-directory-listener restart


3. Operation
------------
Creating users on the satellites triggers the listener, which pushes the newly
created user to the global DC master. Several attributes are modified:

dn:
	All users are always placed in the ${global_base} container

uid:
	"_${local_suffix}" is appended to the satellite user name, that is phahn
	on the satellite becomes phahn_dom1 on the global DC master.

gidNumber:
	The gid number of the group specified via ${global_group} is always used instead.

sambaPrimarySID:
	The SID of the group specified via ${global_group} is always used instead.

homeDirectory:
	${local_suffix} is inserted before the last directory name component, that
	is /home/phahn on the satellite becomes /home/dom1/phahn on the global
	DC master.

uidNumber:
	A new unique uid number is always allocated the on global DC master.

entryUUID, entryDN, entryCSN, creatorsName, createTimestamp, modifiersName, modifyTimestamp, structuralObjectClass, hasSubordinates, subschemaSubentry:
	These OpenLDAP internal operational attributes are excluded from being
	synchronized.

All other attributes are synchronized 1:1, which requires all LDAP schemas used
on any satellite DC master to be also installed on the global DC master!
