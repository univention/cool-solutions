#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention homedir autocreation
#  listener module
#
# Copyright 2009-2023 Univention GmbH
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

import re
import os
from typing import List

import listener

import univention.debug as ud
from univention.config_registry import ucr

name = "homedir-autocreate"
description = "Generate homedir on usercreation"
prettyFilter = '(&\
                    (|\
                        (&\
                            (objectClass=posixAccount)\
                            (objectClass=shadowAccount)\
                        )\
                        (objectClass=univentionMail)\
                        (objectClass=sambaSamAccount)\
                        (objectClass=simpleSecurityObject)\
                        (&\
                            (objectClass=person)\
                            (objectClass=organizationalPerson)\
                            (objectClass=inetOrgPerson)\
                        )\
                    )\
                    (!\
                        (uidNumber=0)\
                    )\
                    (!\
                        (uid=*$)\
                    )\
                )'
filter = "".join(prettyFilter.split())
attributes = []  # type: List

PATH_SU = "/bin/su"
PATH_MKDIR = "/bin/mkdir"
PATH_CHOWN = "/bin/chown"
PATH_CHMOD = "/bin/chmod"


def handler(dn: str, new: "dict[str, list[bytes]]", old: "dict[str, list[bytes]]") -> None:
    # create users homedir only on user creation
     if not old and new:
        ud.debug(
            ud.LISTENER,
            ud.WARN,
            "%s: Check home directory for user %s"
            % (
                name,
                new["uid"][0].decode("utf-8"),
            ),
        )
        # if homeDirectory is not set OR ( homeDirectory is missing and not '/dev/null' ) then ....
        if not new["homeDirectory"][0].decode("utf-8") or not os.path.exists(
            new.get("homeDirectory", [b"/"])[0].decode("UTF-8")
        ):
            if not new.get("automountInformation"):
                # check for uid
                if new.get("uid"):
                    ud.debug(
                        ud.LISTENER,
                        ud.INFO,
                        "%s: starting %s for %s %s"
                        % (
                            name,
                            PATH_SU,
                            new["uid"][0].decode("utf-8"),
                            new["homeDirectory"][0].decode("utf-8"),
                        ),
                    )
                    listener.run(
                        PATH_SU,
                        [PATH_SU, "-c", "echo", "-", new["uid"][0].decode("utf-8")],
                    )
                    ud.debug(
                        ud.LISTENER,
                        ud.WARN,
                        "%s: created home directory %s for user %s"
                        % (
                            name,
                            new["homeDirectory"][0].decode("utf-8"),
                            new["uid"][0].decode("utf-8"),
                        ),
                    )
            elif (new.get("automountInformation")[0].decode("UTF-8") in ucr["hostname"]):
                if new.get("uid"):
                    automount_information = new.get("automountInformation", [ucr["hostname"].encode("utf8")])
                    path = re.split(b' +', automount_information, 1)[1].split(b':', 1)[1].decode('UTF-8')
                    listener.run(PATH_MKDIR, [PATH_MKDIR, path])
                    listener.run(
                        PATH_CHOWN,
                        [PATH_CHOWN, new["uid"][0].decode("utf-8"), path],
                    )
                    listener.run(PATH_CHMOD, [PATH_CHMOD, "0700", path])
                    ud.debug(
                        ud.LISTENER,
                        ud.WARN,
                        "%s: created home directory %s on share for user %s"
                        % (
                            name,
                            new["homeDirectory"][0].decode("utf-8"),
                            new["uid"][0].decode("utf-8"),
                        ),
                    )
