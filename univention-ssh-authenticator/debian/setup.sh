#!/bin/bash

echo "register the LDAP schema for openssh public keys"
. /usr/share/univention-lib/ldap.sh
ucs_registerLDAPSchema openssh-ldap.schema

echo "enable users/self"
ucr unset umc/module/udm/users/self/disabled

eval "$(ucr shell)"

udmname=sshPublicKey
ldapname=sshPublicKey
objectclassname=ldapPublicKey # univentionFreeAttributes

echo "add an attribute for the public key to users"
univention-directory-manager settings/extended_attribute create \
    --position "cn=custom attributes,cn=univention,$ldap_base" \
    --set name="$udmname" \
    --set module="users/user" \
    --set ldapMapping="$ldapname" \
    --set objectClass="$objectclassname" \
    --set longDescription="Public Key that is used by the user for ssh authentification" \
    --set tabName="Authentification" \
    --set multivalue=0 \
    --set syntax="string" \
    --set shortDescription="public ssh key" \
    --set mayChange=1 \
    --set default="\n"

#echo " # append attribute to the user"
#udm settings/extended_attribute modify \
#     --dn "cn=$udmname,cn=custom attributes,cn=univention,$ldap_base" \
#     --append module=users/self

echo "make the attribute editable through self-service "
ucr set self-service/ldap_attributes=$(ucr get self-service/ldap_attributes),$ldapname
ucr set self-service/udm_attributes=$(ucr get self-service/udm_attributes),$udmname


echo "create user for the SSH deamon to search LDAP with"
univention-directory-manager users/ldap create \
	--position "cn=users,$ldap_base" \
	--set username="sshAuthenticator" \
	--set password="univention"

