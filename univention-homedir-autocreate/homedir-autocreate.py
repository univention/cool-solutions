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

__package__ = ""  # workaround for PEP 366

import listener
import os
import univention.debug
from univention.config_registry import ConfigRegistry
from typing import Dict
from typing import List

ucr = ConfigRegistry()
ucr.load()

name = "homedir-autocreate"
description = "Generate homedir on usercreation"
filter =    "(&\
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
            )"
attributes = [] # type: List

PATH_SU = "/bin/su"
PATH_MKDIR = "/bin/mkdir"
PATH_CHOWN = "/bin/chown"
PATH_CHMOD = "/bin/chmod"


def initialize():
    univention.debug.debug(
        univention.debug.LISTENER, univention.debug.INFO, "%s: initialize" % name
    )
    return


def handler(
    dn, new, old
):  # type: (str, Dict[str, List[bytes]], Dict[str, List[bytes]]) -> None
    # create users homedir only on user creation
    if not old and new:
        # if homeDirectoy is not set OR ( homeDirectoy is missing and not '/dev/null' ) then ....
        if not new.get("homeDirectory") or (
            new.get("homeDirectory", ["/"])[0] != "/dev/null"
            and not os.path.exists(new.get("homeDirectory", ["/"])[0])
        ):
            if not new.get("automountInformation"):
                # check for uid
                if new.get("uid"):
                    listener.setuid(0)
                    try:
                        univention.debug.debug(
                            univention.debug.LISTENER,
                            univention.debug.INFO,
                            "%s: starting %s for %s %s"
                            % (
                                name,
                                PATH_SU,
                                new.get("uid")[0],
                                str(new.get("homeDirectory", [])),
                            ),
                        )
                        listener.run(
                            PATH_SU, [PATH_SU, "-c", "echo", "-", new.get("uid")[0]]
                        )
                        univention.debug.debug(
                            univention.debug.LISTENER,
                            univention.debug.WARN,
                            "%s: created home directory %s for user %s"
                            % (
                                name,
                                str(new.get("homeDirectory", [])),
                                new.get("uid")[0],
                            ),
                        )
                    finally:
                        listener.unsetuid()
            elif (
                ucr["hostname"] in new.get("automountInformation", [ucr["hostname"]])[0]
            ):
                if new.get("uid"):
                    listener.setuid(0)
                    path = new.get("automountInformation", [ucr["hostname"]])[0].split(
                        ":"
                    )[1]
                    listener.run(PATH_MKDIR, [PATH_MKDIR, path])
                    listener.run(PATH_CHOWN, [PATH_CHOWN, new.get("uid")[0], path])
                    listener.run(PATH_CHMOD, [PATH_CHMOD, "0700", path])
                    univention.debug.debug(
                        univention.debug.LISTENER,
                        univention.debug.WARN,
                        "%s: created home directory %s on share for user %s"
                        % (name, str(new.get("homeDirectory", [])), new.get("uid")[0]),
                    )
                    listener.unsetuid()
            else:
                # debuglevel changes temporary from info to warn
                univention.debug.debug(
                    univention.debug.LISTENER,
                    univention.debug.WARN,
                    "%s: created home directory %s for user %s on host %s"
                    % (
                        name,
                        str(new.get("homeDirectory", [])),
                        new.get("uid")[0],
                        new.get("automountInformation", [ucr["hostname"]])[0]
                        .split(" ")[1]
                        .split(":")[0],
                    ),
                )


def clean():
    return


def postrun():
    return
