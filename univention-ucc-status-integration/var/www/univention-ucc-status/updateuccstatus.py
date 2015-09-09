#!/usr/bin/python2.7
#
# Univention Thin Client Flash status logging
#
# Copyright (C) 2011-2015 Univention GmbH
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

LOG_FILENAME = '/var/log/univention/ucc-clients/ucc-status.log'
ACCESS_DB = '/var/tmp/ucc-status.pickle'
ACCESS_DB_LOCK = '/var/tmp/ucc-status.pickle.lock'
LAST_SEEN_DIFF = 2

import sys
import cgi
import univention.config_registry
import csv
import time
import pickle
import os
import time
import fcntl

def updateAccessDb (access):
	# save access db
	output = open(ACCESS_DB, 'wb')
	pickle.dump(access, output)
	output.close()

print 'Content-type: text/plain'
print 

myTime = time.time()
myIp = os.environ.get("REMOTE_ADDR", "")

# do nothing if no remote address can be found
if not myIp:
	sys.exit(0)

# get lock
lockFile = open(ACCESS_DB_LOCK, 'wb')
fcntl.flock(lockFile.fileno(), fcntl.LOCK_EX)

# read access db into access dict
access = {}
try:
	input = open(ACCESS_DB, 'rb')
	access = pickle.load(input)
	input.close()
except Exception, e:
	pass

# check clients last access time
lastSeen = access.get(myIp, 0)

# ignore clients which accessed us in the last LAST_SEEN_DIFF seconds
# save timestamp for others
if lastSeen:
	if (myTime - lastSeen) <= LAST_SEEN_DIFF:
		sys.exit(0)
access[myIp] = myTime

# clean up access db
for client in access.keys():
	if (myTime - access[client]) > LAST_SEEN_DIFF:
		del access[client]

# get data
form = cgi.FieldStorage()
data = []
size = 0
for key in form.keys():
	tmp = key + "=" +form.getvalue(key)
	size += len(tmp)
	data.append(tmp)

tmp="ip=%s" % myIp
size += len(tmp)
data.append(tmp)

# simple test to restrict the size of post
if size > 4096:
	updateAccessDb(access)
	sys.exit(0)

data.append("time=" + str(time.time()))

# write to log
log = csv.writer(open(LOG_FILENAME, 'ab'), delimiter="\t", quotechar='|', quoting=csv.QUOTE_MINIMAL)
log.writerow(data)

# update access db
updateAccessDb(access)

# release lock
lockFile.close()

