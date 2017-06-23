#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
#
# Univention SSL
#  listener ssl module for user certificates
#
# Copyright (C) 2004-2016 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# Binary versions of this file provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

__package__ = ''         # workaround for PEP 366

import listener
import univention.debug as ud
import univention.misc
import univention.config_registry
import univention.uldap

import os
import subprocess
import ldap
import copy
import cPickle

FN_CACHE = '/var/cache/univention-usercert/univention-usercert.pickle'

name = 'manageusercertificate'
description = 'Manage User Certificates'
filter = '(|(objectClass=posixAccount)(objectClass=univentionWindows))'
attributes = []
ssl = "/usr/sbin/univention-certificate-user"
runparts = "/usr/lib/univention-ssl-usercert/"
modrdn = '1'


def initialize():
	ud.debug(ud.LISTENER, ud.INFO, 'manageusercertificate: Initialize')


def handler(dn, new, old, command):
	ud.debug(ud.LISTENER, ud.INFO, 'manageusercertificate: handler')

	# load config registry
	cr = univention.config_registry.ConfigRegistry()
	cr.load()

	# only on master and backup
	if cr['server/role'] != 'domaincontroller_master':
		ud.debug(
			ud.LISTENER,
			ud.PROCESS,
			'manageusercertificate: this is not a master'
		)
		return

	# copy object "old" - otherwise it gets modified for other listener modules
	old = copy.deepcopy(old)

	# do nothing if command is 'r' ==> modrdn
	if command == 'r':
		listener.setuid(0)
		try:
			with open(FN_CACHE, 'w+') as f:
				os.chmod(FN_CACHE, 0600)
				cPickle.dump(old, f)
		except Exception, e:
			ud.debug(
				ud.LISTENER,
				ud.ERROR,
				'manageusercertificate: failed to open/write pickle file: %s' % str(e))
		listener.unsetuid()
		return

	# check modrdn changes
	if os.path.exists(FN_CACHE):
		listener.setuid(0)
		try:
			with open(FN_CACHE, 'r') as f:
				old = cPickle.load(f)
		except Exception, e:
			ud.debug(
				ud.LISTENER,
				ud.ERROR,
				'manageusercertificate: failed to open/read pickle file: %s' % str(e))
		try:
			os.remove(FN_CACHE)
		except Exception, e:
			ud.debug(
				ud.LISTENER,
				ud.ERROR,
				'manageusercertificate: cannot remove pickle file: %s' % str(e))
			ud.debug(
				ud.LISTENER,
				ud.ERROR,
				'manageusercertificate: for safty reasons manageusercertificate ignores change of LDAP object: %s' % dn)
			listener.unsetuid()
			return
		listener.unsetuid()

	retval = 0

	# object deleted
	if old and not new:
		retval = doit("revoke", old, dn, cr)
	# pki option deleted
	elif old and new and "pkiUser" in old.get('objectClass', []) and "pkiUser" not in new.get("objectClass", []):
		retval = doit("revoke", new, dn, cr)
	# object created/changed
	else:
		# create cert
		if 'univentionCreateRevokeCertificate' in new and new['univentionCreateRevokeCertificate'][0] == "1":
			if 'univentionCreateRevokeCertificate' not in old:
				retval = doit("create", new, dn, cr)

		# revoke cert
		if 'univentionCreateRevokeCertificate' in old and old['univentionCreateRevokeCertificate'][0] == "1":
			if 'univentionCreateRevokeCertificate' not in new:
				retval = doit("revoke", new, dn, cr)
			if 'univentionCreateRevokeCertificate' in new and new['univentionCreateRevokeCertificate'][0] == "0":
				retval = doit("revoke", new, dn, cr)

		# renew cert
		if 'univentionRenewCertificate' in new and new['univentionRenewCertificate'][0] == "1":
			retval = doit("renew", new, dn, cr)
	# fin
	if retval:
		ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: handler unsuccessfully finished")
	else:
		ud.debug(ud.LISTENER, ud.INFO, "manageusercertificate: handler successfully finished")


# create config config
def create_config(object, dn, cr):
	if not os.path.isfile(ssl):
		ud.debug(ud.LISTENER, ud.ERROR, 'manageusercertificate: could not find %s' % ssl)
		return 0

	# get ucr ssl config
	email = cr.get('ssl/usercert/default/email')
	organizationalunit = cr.get('ssl/usercert/default/organizationalunit')
	organization = cr.get('ssl/usercert/default/organization')
	locality = cr.get('ssl/usercert/default/locality')
	state = cr.get('ssl/usercert/default/state')
	country = cr.get('ssl/usercert/default/country')

	host = "univentionWindows" in object.get("objectClass", [])

	if host:
		mapping_cn = cr.get('ssl/windowscert/certldapmapping/cn')
		mapping_email = cr.get('ssl/windowscert/certldapmapping/email')
		mapping_organizationalunit = cr.get('ssl/windowscert/certldapmapping/organizationalunit')
		mapping_organization = cr.get('ssl/windowscert/certldapmapping/organization')
		mapping_state = cr.get('ssl/windowscert/certldapmapping/state')
		mapping_locality = cr.get('ssl/windowscert/certldapmapping/locality')
		certpath = cr.get('ssl/windowscert/certpath', "/etc/univention/ssl/hosts")
		admingroup = cr.get('ssl/windowscert/admingroup', "Domain Admins")
		days = cr.get('ssl/windowscert/days', "1825")
		scripts = cr.get('ssl/windowscert/scripts', "yes")
		ldapimport = cr.get('ssl/windowscert/ldapimport', "yes")
		sslbase = cr.get('ssl/windowscert/sslbase', "/etc/univention/ssl")
		ca = cr.get('ssl/windowscert/ca', "ucsCA")
	else:
		mapping_cn = cr.get('ssl/usercert/certldapmapping/cn')
		mapping_email = cr.get('ssl/usercert/certldapmapping/email')
		mapping_organizationalunit = cr.get('ssl/usercert/certldapmapping/organizationalunit')
		mapping_organization = cr.get('ssl/usercert/certldapmapping/organization')
		mapping_state = cr.get('ssl/usercert/certldapmapping/state')
		mapping_locality = cr.get('ssl/usercert/certldapmapping/locality')
		certpath = cr.get('ssl/usercert/certpath', "/etc/univention/ssl/user")
		admingroup = cr.get('ssl/usercert/admingroup', "Domain Admins")
		days = cr.get('ssl/usercert/days', "1825")
		scripts = cr.get('ssl/usercert/scripts', "yes")
		ldapimport = cr.get('ssl/usercert/ldapimport', "yes")
		sslbase = cr.get('ssl/userscert/sslbase', "/etc/univention/ssl")
		ca = cr.get('ssl/usercert/ca', "ucsCA")

	# get user ldap info
	cn = None
	uid = None
	if mapping_cn in object:
		cn = object[mapping_cn][0]
	if mapping_email in object:
		email = object[mapping_email][0]
	if mapping_organizationalunit in object:
		organizationalunit = object[mapping_organizationalunit][0]
	if mapping_organization in object:
		organization = object[mapping_organization][0]
	if mapping_locality in object:
		locality = object[mapping_locality][0]
	if mapping_state in object:
		state = object[mapping_state][0]
	if 'uid' in object:
		uid = object['uid'][0]
	if 'univentionCertificateDays' in object:
		days = object['univentionCertificateDays'][0]

	# get extensions file
	extFile = cr.get('ssl/usercert/extensionsfile', "")
	if uid:
		extFile = cr.get('ssl/usercert/%s/extensionsfile' % uid, extFile)

	if host:
		extFile = cr.get('ssl/windowscert/extensionsfile', "")
		if uid:
			extFile = cr.get('ssl/windowscert/%s/extensionsfile' % uid, extFile)

	# cfg hash
	cfg = {
		"certpath": certpath,
		"admingroup": admingroup,
		"days": days,
		"ca": ca,
		"sslbase": sslbase,
		"email": email,
		"organizationalunit": organizationalunit,
		"cn": cn,
		"uid": uid,
		"ssl": ssl,
		"ldapimport": ldapimport,
		"organization": organization,
		"locality": locality,
		"state": state,
		"country": country,
		"scripts": scripts,
		"runparts": runparts,
		"extFile": extFile,
		"isHost": host,
		"dn": dn
	}

	if not cfg["uid"]:
		ud.debug(
			ud.LISTENER,
			ud.ERROR,
			"manageusercertificate: uid is empty, don't know what to do"
		)
		return 0

	return cfg


def saveCert(dn, cfg, ldapObject, delete=False):
	if cfg["ldapimport"].lower() in ("true", "yes"):
		listener.setuid(0)
		try:
			cert = ""
			if not delete:
				with open(os.path.join(cfg["certpath"], cfg["uid"], "cert.cer"), "r") as fd:
					cert = fd.read()
			lo = univention.uldap.getAdminConnection()
			oldValue = ldapObject.get('userCertificate;binary', [""])[0]
			modlist = [('userCertificate;binary', oldValue, cert)]
			try:
				lo.modify(dn, modlist)
			except ldap.NO_SUCH_OBJECT:
				# object was probably deleted
				pass
		except Exception, e:
			ud.debug(
				ud.LISTENER,
				ud.ERROR,
				'manageusercertificate: failed to add certificate to %s (%s)' % (dn, str(e))
			)
		finally:
			listener.unsetuid()


# manage certificates
def doit(action, object, dn, cr):
	cfg = create_config(object, dn, cr)

	if not cfg:
		return 1

	# create the cert
	if action == "create":
		ud.debug(ud.LISTENER, ud.INFO, "manageusercertificate: create cert %s" % cfg["uid"])

		# parameter test
		for x in ["uid", "cn", "days", "email", "organizationalunit", "certpath", "sslbase", "ca", "admingroup", "dn", "ldapimport", "state", "organization", "country", "locality"]:
			if not cfg.get(x, False):
				ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: %s is missing" % x)
				return 1

		# test for valid certificate with the same cn
		cmd = "%s check" % cfg["ssl"]
		cmd = cmd + " -name '%s'" % cfg["uid"]
		cmd = cmd + " -cn '%s'" % cfg["cn"]
		cmd = cmd + " -sslbase '%s'" % cfg["sslbase"]
		cmd = cmd + " -ca '%s'" % cfg["ca"]

		if run_cmd(cmd, 1):
			ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: a certificate for cn \"%s\" already exists" % cfg["cn"])
			return 1

		# create command
		cmd = "%s new" % cfg["ssl"]
		cmd = cmd + " -name '%s'" % cfg["uid"]
		cmd = cmd + " -cn '%s'" % cfg["cn"]
		cmd = cmd + " -days '%s'" % cfg["days"]
		cmd = cmd + " -email '%s'" % cfg["email"]
		cmd = cmd + " -organizationalunit '%s'" % cfg["organizationalunit"]
		cmd = cmd + " -certpath '%s'" % cfg["certpath"]
		cmd = cmd + " -sslbase '%s'" % cfg["sslbase"]
		cmd = cmd + " -ca '%s'" % cfg["ca"]
		cmd = cmd + " -admingroup '%s'" % cfg["admingroup"]
		cmd = cmd + " -state '%s'" % cfg["state"]
		cmd = cmd + " -organization '%s'" % cfg["organization"]
		cmd = cmd + " -country '%s'" % cfg["country"]
		cmd = cmd + " -locality '%s'" % cfg["locality"]

		# append extensions optiones
		if cfg["extFile"]:
			cmd = cmd + " -extfile '%s'" % cfg["extFile"]

		if run_cmd(cmd, 0):
			return 1

		# save cert in ldap if ucr import var is true
		saveCert(dn, cfg, object)

	# revoke the cert
	if action == "revoke":
		ud.debug(ud.LISTENER, ud.INFO, "manageusercertificate: revoke cert %s" % cfg["uid"])

		# parameter test
		for x in ["uid", "cn", "sslbase", "ca", "dn"]:
			if not cfg.get(x, False):
				ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: %s is missing" % x)
				return 1

		# create command
		cmd = "%s revoke" % cfg["ssl"]
		cmd = cmd + " -name '%s'" % cfg["uid"]
		cmd = cmd + " -cn '%s'" % cfg["cn"]
		cmd = cmd + " -sslbase '%s'" % cfg["sslbase"]
		cmd = cmd + " -ca '%s'" % cfg["ca"]

		if run_cmd(cmd, 0):
			return 1

		# delete cert ldap entry
		saveCert(dn, cfg, object, delete=True)

	# renew the cert
	if action == "renew":
		ud.debug(ud.LISTENER, ud.INFO, "manageusercertificate: renew cert %s" % cfg["uid"])

		# parameter test
		for x in ["uid", "cn", "days", "certpath", "sslbase", "ca", "admingroup", "dn", "ldapimport"]:
			if not cfg.get(x, False):
				ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: %s is missing" % x)
				return 1

		# reset renew ldap entry
		listener.setuid(0)
		try:
			lo = univention.uldap.getAdminConnection()
			modlist = [('univentionRenewCertificate', object['univentionRenewCertificate'][0], 0)]
			lo.modify(dn, modlist)
			ud.debug(ud.LISTENER, ud.INFO, 'manageusercertificate: reset univentionRenewCertificate successfully')
		except Exception, e:
			ud.debug(ud.LISTENER, ud.ERROR, 'manageusercertificate: cannot reset univentionRenewCertificate in LDAP (%s): %s' % (dn, str(e)))
			return 1
		finally:
			listener.unsetuid()

		# renew only if certificate is saved in user ldap object
		if not object.get('userCertificate;binary'):
			ud.debug(ud.LISTENER, ud.WARN, "manageusercertificate: could not find imported user cert, will not renew cert")
			return 0

		# create/run command
		# univention-certificate-user renew \
		# -name 'test' \
		# -cn 'Vorname Nachname' \
		# -days '7300' \
		# -cert-path '/etc/univention/ssl/user/' \
		# -ssl-base '/etc/univention/ssl/' \
		# -ca  'ucsCA'

		cmd = "%s renew" % cfg["ssl"]
		cmd = cmd + " -name '%s'" % cfg["uid"]
		cmd = cmd + " -cn '%s'" % cfg["cn"]
		cmd = cmd + " -days '%s'" % cfg["days"]
		cmd = cmd + " -certpath '%s'" % cfg["certpath"]
		cmd = cmd + " -sslbase '%s'" % cfg["sslbase"]
		cmd = cmd + " -ca '%s'" % cfg["ca"]

		# append extensions optiones
		if cfg["extFile"]:
			cmd = cmd + " -extfile '%s'" % cfg["extFile"]

		if run_cmd(cmd, 0):
			return 1

		# save cert in ldap if ucr import var is true
		saveCert(dn, cfg, object)

	# run additional scripts with the following arguments
	# action dn uid certpath
	if cfg["scripts"].lower() in ("true", "yes"):
		if os.path.isdir(cfg["runparts"]):
			ud.debug(ud.LISTENER, ud.INFO, 'manageusercertificate: running scripts in %s' % cfg["runparts"])
			cmd = "run-parts %s -a %s -a %s -a %s -a %s" % (cfg["runparts"], action, cfg["dn"], cfg["uid"], cfg["certpath"])
			if run_cmd(cmd, 0):
				return 1

	return 0


# run a given command as root and return the exit code
def run_cmd(command, expected_retval):
	ud.debug(ud.LISTENER, ud.INFO, "manageusercertificate: run %s" % command)
	listener.setuid(0)
	proc = subprocess.Popen(command, bufsize=0, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	stdout = None
	stderr = None
	retval = 0
	try:
		(stdout, stderr) = proc.communicate()
	finally:
		listener.unsetuid()

	if proc.returncode != expected_retval:
		retval = 1
		ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: run %s" % command)
		ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: command failed with exit code: %s" % proc.returncode)
		ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: stderr: %s" % stderr)
		ud.debug(ud.LISTENER, ud.ERROR, "manageusercertificate: stdout: %s" % stderr)

	return retval


def clean():
	return


def postrun():
	return
