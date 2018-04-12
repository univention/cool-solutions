#/bin/bash
#
# Univention set samba4 profile
#
# Copyright 2009-2018 Univention GmbH
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

if [ ! -n "$1" ]; then
        echo "Usage $0 SERVERFQDN <OU>"
        exit 1
fi

if [ ! -n "$2" ]; then
        IFS=$'\n'
        for i in $(univention-directory-manager users/user list | grep DN: | sed -e 's/DN: //'); do
                univention-directory-manager users/user modify --dn "$i" --set "profilepath=\\\\${1}\\%UserName%\\windows-profiles"
        done
else
        IFS=$'\n'
        for i in $(univention-directory-manager users/user list | grep DN: | grep ${2} | sed -e 's/DN: //'); do
                univention-directory-manager users/user modify --dn "$i" --set "profilepath=\\\\${1}\\%UserName%\\windows-profiles"
        done
fi

exit 0
