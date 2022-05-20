#! /bin/bash -e
#
# Univention SSL
#  gencertificate script
#
# Copyright 2004-2022 Univention GmbH
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

# See:
# http://www.ibiblio.org/pub/Linux/docs/HOWTO/other-formats/html_single/SSL-Certificates-HOWTO.html
# http://www.pca.dfn.de/dfnpca/certify/ssl/handbuch/ossl092/

DEFAULT_DAYS=$(/usr/sbin/univention-config-registry get ssl/usercert/days)
. /usr/share/univention-ssl/make-certificates.sh
[ -n "$ca" ] && CA="${ca}"

mk_config () {
	local outfile=$1
	local password=$2
	local days=$3
	local name=$4

	local ssl_email=$5
	local ssl_organizationalunit=$6
	local ssl_country=$7
	local ssl_state=$8
	local ssl_locality=$9
	local ssl_organization=${10}
	
	if test -z $ssl_country; then eval `univention-config-registry shell ssl/country`; fi
	if test -z $ssl_state; then eval `univention-config-registry shell ssl/state`; fi
	if test -z $ssl_locality; then eval `univention-config-registry shell ssl/locality`; fi
	if test -z $ssl_organization; then eval `univention-config-registry shell ssl/organization`; fi
	if test -z $ssl_organizationalunit; then eval `univention-config-registry shell ssl/organizationalunit`; fi
	if test -z $ssl_email; then eval `univention-config-registry shell ssl/email`; fi

	if test -e $outfile; then
		rm $outfile
	fi
	touch $outfile
	chmod 0600 $outfile

    cat <<EOF >>$outfile

# HOME			= .
# RANDFILE		= \$ENV::HOME/.rnd
# oid_section		= new_oids
#
# [ new_oids ]
#

path		= $SSLBASE

[ ca ]
default_ca	= CA_default

[ CA_default ]

dir                 = \$path/${CA}
certs               = \$dir/certs
crl_dir             = \$dir/crl
database            = \$dir/index.txt
new_certs_dir       = \$dir/newcerts

certificate         = \$dir/CAcert.pem
serial              = \$dir/serial
crl                 = \$dir/crl.pem
private_key         = \$dir/private/CAkey.pem
RANDFILE            = \$dir/private/.rand

x509_extensions     = ${CA}_ext
crl_extensions     = crl_ext
copy_extensions     = copy
default_days        = $days
default_crl_days    = \$ENV::DEFAULT_CRL_DAYS
default_md          = \$ENV::DEFAULT_MD
preserve            = no

policy              = policy_match

[ policy_match ]

countryName		= match
stateOrProvinceName	= supplied
localityName		= optional
organizationName	= supplied
organizationalUnitName	= optional
commonName		= supplied
emailAddress		= optional

[ policy_anything ]

countryName		= match
stateOrProvinceName	= optional
localityName		= optional
organizationName	= optional
organizationalUnitName	= optional
commonName		= supplied
emailAddress		= optional

[ req ]

default_bits		= \$ENV::DEFAULT_BITS
default_keyfile 	= privkey.pem
default_md          = \$ENV::DEFAULT_MD
distinguished_name	= req_distinguished_name
attributes		= req_attributes
x509_extensions		= v3_ca
prompt		= no
${password:+input_password = $password}
${password:+output_password = $password}
string_mask = nombstr
req_extensions = v3_req

[ req_distinguished_name ]

C	= $(echo -n "$ssl_country" | _escape)
ST	= $(echo -n "$ssl_state" | _escape)
L	= $(echo -n "$ssl_locality" | _escape)
O	= $(echo -n "$ssl_organization" | _escape)
OU	= $(echo -n "$ssl_organizationalunit" | _escape)
CN	= $(echo -n "$name" | _escape)
emailAddress	= $(echo -n "$ssl_email" | _escape)

[ req_attributes ]

challengePassword		= A challenge password
unstructuredName	= Univention GmbH

[ ${CA}_ext ]

basicConstraints        = CA:FALSE
# keyUsage                = cRLSign, keyCertSign
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid,issuer:always
# subjectAltName          = email:copy
# issuerAltName           = issuer:copy
# nsCertType              = sslCA, emailCA, objCA
# nsComment               = signed by Univention Corporate Server Root CA

[ v3_req ]

basicConstraints = critical, CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
${SAN_txt:+subjectAltName = $SAN_txt}

[ v3_ca ]

basicConstraints        = critical, CA:TRUE
subjectKeyIdentifier    = hash
authorityKeyIdentifier  = keyid:always,issuer:always
keyUsage                = cRLSign, keyCertSign
nsCertType              = sslCA, emailCA, objCA
subjectAltName          = email:copy
issuerAltName           = issuer:copy
nsComment               = This certificate is a Root CA Certificate

[ crl_ext ]

issuerAltName           = issuer:copy
authorityKeyIdentifier  = keyid:always,issuer:always
EOF
chmod 0600 $outfile
}

_escape () {
	sed 's/["$]/\\\0/g'
}

renew_cert () {
	local OPWD=`pwd`
	local path="$1"
	local cn="$2"
	local days="$3"
	local owner="$4"
	local extfile="$5"
	cd "$SSLBASE"
	
	if [ -z "$owner" ]; then
		owner="cert"
	fi

	if [ -z "$cn" ]; then
		echo "missing certificate name" 1>&2
		return 1
	fi
	
	local NUM=`list_cert_names | grep "$cn$" | sed -e 's/^\([0-9A-Fa-f]*\).*/\1/1'`
	if [ -z "$NUM" ]; then
		echo "no certificate for $cn registered" 1>&2
		return 1
	fi
	
	if [ -z "$days" ]; then
		days=$DEFAULT_DAYS
	fi
	
	# revoke cert
	revoke_cert "$cn"
	
	# extensions?
	if [ -f "$extfile" ]; then
		local ext="-extfile $(bash ${extfile})"
	fi

	# makepasswd chars
	local chars=$(ucr get ssl/usercert/passwordchars)
	if [ -n "$chars" ]; then
		chars="--chars=$chars"
	fi

	# sign the request
	openssl ca -batch -config openssl.cnf $ext -days $days -in "$path/req.pem" -out "$path/cert.pem" -passin pass:"$PASSWD"
	openssl x509 -outform der -in "$path/cert.pem" -out "$path/cert.cer"
	makepasswd $chars > "$path/$owner-p12-password.txt"
	openssl pkcs12 -export -in "$path/cert.pem" -inkey "$path/private.key" -chain -CAfile ucsCA/CAcert.pem -out "$path/$owner.p12" -passout file:"$path/$owner-p12-password.txt"

	# move the new certificate to its place
	move_cert ${CA}/newcerts/*

	find $path -type f | xargs chmod 400
	find $path -type d | xargs chmod 500
	cd "$OPWD"
}

# Parameter 1: Name des Unterverzeichnisses, in dem das neue Zertifikat abgelegt werden soll
# Parameter 2: Name des CN für den das Zertifikat ausgestellt wird.
# Parameter 3 (opt): email Adresse
# Parameter 4 (opt): Organisation

gencert () {
	local path="$1"
	local cn="$2"

	local days="$3"
	local email="$4"
	local organizationalunit="$5"
	local country="$6"
	local state="$7"
	local locality="$8"
	local organization="$9"
	local owner="${10}"
	local extfile="${11}"

	if [ -z "$owner" ]; then
		owner="cert"
	fi

	local OPWD=`pwd`
	cd "$SSLBASE"
	if has_valid_cert "$2"; then
	    revoke_cert "$2"
	fi

	if [ -z "$days" ]; then
		days=$DEFAULT_DAYS
	fi

	# generate a key pair
	mkdir -pm 500 $path
	mk_config "$path/openssl.cnf" "" $days "$cn" "$email" "$organizationalunit" "$country" "$state" "$locality" "$organization"
	openssl genrsa -out "$path/private.key" "$DEFAULT_BITS"
	openssl req -batch -config "$path/openssl.cnf" -new -key "$path/private.key" -out "$path/req.pem"

	# extensions?
	if [ -f "$extfile" ]; then
		local ext="-extfile $(bash ${extfile})"
	fi

	# makepasswd chars
	local chars=$(ucr get ssl/usercert/passwordchars)
	if [ -n "$chars" ]; then
		chars="--chars=$chars"
	fi

	# sign the key
	openssl ca -batch -config openssl.cnf $ext -days $days -in "$path/req.pem" -out "$path/cert.pem" -passin pass:"$PASSWD"
	openssl x509 -outform der -in "$path/cert.pem" -out "$path/cert.cer"
	makepasswd $chars > "$path/$owner-p12-password.txt"
	openssl pkcs12 -export -in "$path/cert.pem" -inkey "$path/private.key" -chain -CAfile ucsCA/CAcert.pem -out "$path/$owner.p12" -passout file:"$path/$owner-p12-password.txt"

	# move the new certificate to its place
	move_cert ${CA}/newcerts/*

	find $path -type f | xargs chmod 400
	find $path -type d | xargs chmod 500
	cd "$OPWD"
}
