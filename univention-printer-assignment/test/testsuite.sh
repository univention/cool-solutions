#!/bin/bash
#
# -*- coding: utf-8 -*-
#
# small and ugly test script
#
# Copyright 2013-2018 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

PREFIX="upa-$$"

eval "$(ucr shell)"

create_printer () {
	local NAME="$1"
	local SAMBANAME=""
	[ -n "$2" ] && SAMBANAME="--set sambaName=$2"
	udm shares/printer create --ignore_exists \
		--position "cn=printers,$ldap_base" \
		--set producer="cn=Generic,cn=cups,cn=univention,$ldap_base" \
		--set spoolHost="$hostname.$domainname" \
		--set name="$NAME" \
		--set uri="cups-pdf://" \
		--set model="foomatic-rip/Generic-PCL_4_Printer-ljetplus.ppd" \
		$SAMBANAME
}

create_group () {
	local NAME="$1"
	local PRINTER=""
	local DEFAULT_PRINTER=""
	local HOSTS=""
	[ -n "$2" ] && PRINTER="--set univention-printer-list=$2"
	[ -n "$3" ] && DEFAULT_PRINTER="--set univention-printer-default=$3"
	[ -n "$4" ] && HOSTS="--set hosts=$4"
	udm groups/group create --ignore_exists \
		--position "cn=groups,$ldap_base" \
		--set name="$NAME" \
		$PRINTER $DEFAULT_PRINTER $HOSTS
}

create_host () {
	local NAME="$1"
	local PRINTER=""
	local DEFAULT_PRINTER=""
	local GROUPLIST=""
	[ -n "$2" ] && PRINTER="--set univention-printer-list=$2"
	[ -n "$3" ] && DEFAULT_PRINTER="--set univention-printer-default=$3"
	[ -n "$4" ] && GROUPLIST="--set groups=$4"
	set -x
	udm computers/windows create --ignore_exists \
		--position "cn=computers,$ldap_base" \
		--set name="$NAME" \
		$PRINTER $DEFAULT_PRINTER $GROUPLIST
	set +x
}

cleanup_hosts () {
	rm -Rf "/var/lib/samba/sysvol/$(echo $kerberos_realm | tr '[:upper:]' '[:lower:]')/scripts/printerassignment/"*
	: > /var/lib/univention-printer-assignment/backlog
}

check_changes () {
	echo "$1"
	sleep 3s
	/usr/share/univention-printer-assignment/update-univention-printer-assignment -d -f /var/lib/univention-printer-assignment/backlog
	ls "/var/lib/samba/sysvol/$(echo $kerberos_realm | tr '[:upper:]' '[:lower:]')/scripts/printerassignment"
	egrep -Hr '^Dim (printerList|defaultPrinter|default_printer)' "/var/lib/samba/sysvol/$(echo $kerberos_realm | tr '[:upper:]' '[:lower:]')/scripts/printerassignment"
	cleanup_hosts
}

create_default_setup () {
	cleanup_hosts
	# some printers
	create_printer "${PREFIX}-Prn1"
	create_printer "${PREFIX}-Prn2" "SpecialPrn"
	create_printer "${PREFIX}-Prn3"
	create_printer "${PREFIX}-Prn4"
	create_printer "${PREFIX}-Prn5"

	# some groups
	create_group "${PREFIX}-Grp1"
	create_group "${PREFIX}-Grp2" "cn=${PREFIX}-Prn4,cn=printers,$ldap_base"
	create_group "${PREFIX}-Grp3" "cn=${PREFIX}-Prn4,cn=printers,$ldap_base" "cn=${PREFIX}-Prn5,cn=printers,$ldap_base"

	# no group members
	create_host "${PREFIX}-Win01"
	check_changes "Win01 angelegt"
	create_host "${PREFIX}-Win02" "cn=${PREFIX}-Prn1,cn=printers,$ldap_base"
	check_changes "Win02 angelegt"
	create_host "${PREFIX}-Win03" "cn=${PREFIX}-Prn2,cn=printers,$ldap_base"
	check_changes "Win03 angelegt"
	create_host "${PREFIX}-Win04" "cn=${PREFIX}-Prn2,cn=printers,$ldap_base" "cn=${PREFIX}-Prn1,cn=printers,$ldap_base"
	check_changes "Win04 angelegt"
	create_host "${PREFIX}-Win05"
	check_changes "Win01 angelegt"

	# members of Grp1
	create_host "${PREFIX}-Win11" "" "" "cn=${PREFIX}-Grp3,cn=groups,$ldap_base"
	check_changes "Win11 angelegt ==> Prn4+5 5=def"
	create_host "${PREFIX}-Win12" "cn=${PREFIX}-Prn1,cn=printers,$ldap_base" "" "cn=${PREFIX}-Grp3,cn=groups,$ldap_base"
	check_changes "Win12 angelegt ==> Prn1+4+5 5=def"
	create_host "${PREFIX}-Win13" "cn=${PREFIX}-Prn2,cn=printers,$ldap_base" "" "cn=${PREFIX}-Grp3,cn=groups,$ldap_base"
	check_changes "Win13 angelegt ==> Prn2+4+5 5=def"
	create_host "${PREFIX}-Win14" "cn=${PREFIX}-Prn2,cn=printers,$ldap_base" "cn=${PREFIX}-Prn1,cn=printers,$ldap_base" "cn=${PREFIX}-Grp3,cn=groups,$ldap_base"
	check_changes "Win14 angelegt ==> Prn1+2+4+5 1=def"

	create_group "${PREFIX}-Grp4" "cn=${PREFIX}-Prn5,cn=printers,$ldap_base" "cn=${PREFIX}-Prn5,cn=printers,$ldap_base" "cn=${PREFIX}-Win05,cn=computers,$ldap_base"
	check_changes "Grp4 angelegt ==> Win01 ==> Prn5 5=def"
}

cleanup () {
	for i in 1 2 3 4 5 ; do
		udm shares/printer remove --dn "cn=${PREFIX}-Prn${i},cn=printers,$ldap_base"
	done
	for i in 1 2 3 4 ; do
		udm groups/group remove --dn "cn=${PREFIX}-Grp${i},cn=groups,$ldap_base"
	done
	for i in 01 02 03 04 11 12 13 14 ; do
		udm computers/windows remove --dn "cn=${PREFIX}-Win${i},cn=computers,$ldap_base"
	done
}

trap cleanup EXIT

create_default_setup
