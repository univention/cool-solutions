#!/bin/bash
#
# -*- coding: utf-8 -*-
#
# small and ugly test script
#
# Copyright 2013-2023 Univention GmbH
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
PREFIX="uugs-$$"
CONTROL="/tmp/ssh-control-$(date +%s)-$RANDOM-$$"

eval "$(ucr shell)"

echo "Please enter the root password for '$ldap_sync_destination' for the SSH connection"
ssh -NfM -S "$CONTROL" "$ldap_sync_destination"

run_ssh_command () {
	local COMMAND="$1"
	ssh -S "$CONTROL" "$ldap_sync_destination" $COMMAND
}

force_sync () {
	sudo -u ucs-sync univention_user_group_sync_source_synchronize
	run_ssh_command univention_user_group_sync_dest.py
}

get_udm_property () {
	local MODULE="$1"
	local FILTER="$2"
	local KEY="$3"
	run_ssh_command "udm $MODULE list --filter $FILTER | sed -ne \"s/\ \ $KEY: //p\""
}

delete_udm_object () {
	local MODULE="$1"
	local DN="$2"
	udm "$MODULE" delete --dn "$DN"
}

modify_udm_object () {
	local MODULE="$1"
	local DN="$2"
	local ACTION="$3"
	local KEY="$4"
	local VALUE="$5"
	udm "$MODULE" modify --dn "$DN" \-\-"$ACTION" "$KEY"="$VALUE"
}

create_group () {
	local NAME="$1"
	udm groups/group create --ignore_exists \
		--position "cn=groups,$ldap_base" \
		--set name="$NAME"
}

delete_group () {
	local NAME="$1"
	delete_udm_object groups/group "cn=$NAME,cn=groups,$ldap_base"
}

create_user () {
	local NAME="$1"
	udm users/user create --ignore_exists \
		--position "cn=users,$ldap_base" \
		--set username="$NAME" \
		--set lastname="$NAME" \
		--set password="12345678" \
		--set disabled=1
}

delete_user () {
	local NAME="$1"
	delete_udm_object users/user "uid=$NAME,cn=users,$ldap_base"
}

test_new_user () {
	local NAME="$PREFIX-test"

	create_user $NAME
	force_sync

	[ "$(get_udm_property users/user "uid=$NAME" username | wc -l)" -eq 1 ]
	echo $?

	cleanup
}

test_modify_user () {
	local NAME="$PREFIX-test"
	local NEW_NAME="$PREFIX-Mustermann"

	create_user "$NAME"
	force_sync
	
	modify_udm_object users/user "uid=$NAME,cn=users,$ldap_base" set lastname "$NEW_NAME"
	force_sync

	[ "$(get_udm_property users/user "uid=$NAME" lastname)" = "$NEW_NAME" ]
	echo $?

	cleanup
}

test_new_group () {
	local NAME="$PREFIX-test"

	create_group "$NAME"
	force_sync

	[ "$(get_udm_property groups/group "cn=$NAME" name)" = "$NAME" ]
	echo $?

	cleanup
}

test_modify_group () {
	local NAME="$PREFIX-test"
	local NEW_NAME="$PREFIX-test-group"

	create_group "$NAME"
	force_sync

	modify_udm_object groups/group "cn=$NAME,cn=groups,$ldap_base" set name "$NEW_NAME"
	force_sync

	[ "$(get_udm_property groups/group "cn=$NEW_NAME" name)" = "$NEW_NAME" ]
	echo $?

	cleanup
}

test_delete_group_with_member () {
	local USER_NAME="$PREFIX-test-user"
	local GROUP_NAME="$PREFIX-test-group"

	create_user "$USER_NAME"
	create_group "$GROUP_NAME"
	modify_udm_object users/user "uid=$USER_NAME,cn=users,$ldap_base" append groups "cn=$GROUP_NAME,cn=groups,$ldap_base"
	force_sync

	local COUNT_OF_GROUPS="$(get_udm_property users/user "uid=$USER_NAME" groups | wc -l)"

	delete_group "$GROUP_NAME"
	force_sync

	[ $(get_udm_property users/user "uid=$USER_NAME" groups | wc -l) -eq $(($COUNT_OF_GROUPS - 1)) ]
	echo $?

	cleanup
}

test_delete_user_while_group_member () {
	local NAME="$PREFIX-test"

	create_user "$NAME"
	force_sync

	local COUNT_OF_USERS="$(get_udm_property groups/group "cn=Domain\ Users" users | wc -l)"

	delete_user "$NAME"
	force_sync

	[ $(get_udm_property groups/group "cn=Domain\ Users" users | wc -l) -eq $(($COUNT_OF_USERS - 1)) ]
	echo $?

	cleanup
}

cleanup () {
	delete_user "$PREFIX-test"
	delete_user "$PREFIX-test-user"
	delete_group "$PREFIX-test"
	delete_group "$PREFIX-test-group"
	force_sync
}

end_tests () {
	cleanup
	
	ssh -O exit -S "$CONTROL" "$ldap_sync_destination"
	if [ $? -ne 0 ]; then
        echo "Error: Unable to close SSH session, killing the process."
        kill -9 "$MASTERPID"
    fi
}

trap end_tests EXIT

test_new_user
test_new_group
test_modify_user
test_modify_group
test_delete_group_with_member
test_delete_user_while_group_member

end_tests
