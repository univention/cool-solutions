#!/bin/bash
#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention homedir autocreation
#  listener module
#
# Copyright 2023 Univention GmbH
#
# https://www.univention.de/
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

#This is a test script to test the functionality of the univention-homedir-autocreate listener module.
#It creates users from the list below and checks if their home directories exist.

# List of random names
names=("Alice" "Bob" "Charlie")

# Base DN for user creation
base_dn="cn=users,$(ucr get ldap/base)"

# Array to store usernames
usernames=()

lastname="Doe"
# Loop to create users and collect usernames
for name in "${names[@]}"; do
	# Generate random username, lastname, and password
	username=$(echo "$name" | tr '[:upper:]' '[:lower:]')
	usernames+=("$username")
	password=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 12 | head -n 1)

	# Create the user using the command
	udm users/user create --position "$base_dn" --set username="$username" --set lastname="$lastname" --set password="$password"

	echo "User created: Username=$username, Lastname=$lastname, Password=$password"
done

sleep 30

# Check if home directories exist
for username in "${usernames[@]}"; do
	home_directory="/home/$username"
	if [ ! -d "$home_directory" ]; then
		echo "Error: Home directory '$home_directory' does not exist."
		exit 1
	else
		echo "Home directory '$home_directory' exists."
	fi
done
