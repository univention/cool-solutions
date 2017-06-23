#! /bin/bash -e
#
# Univention SSL
#  gencertificate script
#
# Copyright 2004-2016 Univention GmbH
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

if [ -n "$sslbase" ]; then
	SSLBASE="$sslbase"
else
	SSLBASE=/etc/univention/ssl
fi

if [ -n "$ca" ]; then	
	CA="$ca"
else
	CA=ucsCA
fi

DEFAULT_DAYS=$(/usr/sbin/univention-config-registry get ssl/usercert/days)
if [ -z "$DEFAULT_DAYS" ]; then
	DEFAULT_DAYS=1825
fi
DEFAULT_MD="$(/usr/sbin/univention-config-registry get ssl/default/hashfunction)"
if [ -z "$DEFAULT_MD" ]; then
	DEFAULT_MD=sha256
fi
DEFAULT_BITS="$(/usr/sbin/univention-config-registry get ssl/default/bits)"
if [ -z "$DEFAULT_BITS" ]; then
	DEFAULT_BITS="2048"
fi

if test -e "$SSLBASE/password"; then
	PASSWD=`cat "$SSLBASE/password"`
else
	PASSWD=""
fi

mk_config () {

	local outfile=$1;
	local password=$2;
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
		rm $outfile;
	fi
	touch $outfile;
	chmod 0600 $outfile;

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
default_days        = $days
default_crl_days    = 30
default_md          = ${DEFAULT_MD}
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

default_bits		= $DEFAULT_BITS
default_keyfile 	= privkey.pem
default_md          = ${DEFAULT_MD}
distinguished_name	= req_distinguished_name
attributes		= req_attributes
x509_extensions		= v3_ca

EOF

if [ "$password" ]; then
cat <<EOF >>$outfile
input_password = $password
output_password = $password
EOF
fi;

cat <<EOF >>$outfile

string_mask = nombstr
req_extensions = v3_req

[ req_distinguished_name ]

countryName			= Country Name (2 letter code)
countryName_default		= $ssl_country
countryName_min			= 2
countryName_max			= 2

stateOrProvinceName		= State or Province Name (full name)
stateOrProvinceName_default	= $ssl_state

localityName			= Locality Name (eg, city)
localityName_default		= $ssl_locality

0.organizationName		= Organization Name (eg, company)
0.organizationName_default	= $ssl_organization

organizationalUnitName		= Organizational Unit Name (eg, section)
organizationalUnitName_default	= $ssl_organizationalunit

commonName			= Common Name (eg, YOUR name)
commonName_max			= 64
commonName_default		= $name

emailAddress			= Email Address
emailAddress_max		= 60
emailAddress_default		= $ssl_email

[ req_attributes ]

challengePassword		= A challenge password
challengePassword_min		= 4
challengePassword_max		= 20

unstructuredName		= An optional company name
unstructuredName_default	= Univention GmbH

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

move_cert () {
    local new;
    local count=0;
    local linkname;
    local hash;
    local OPWD=`pwd`;
    cd "$SSLBASE"

    for i; do
	if [ -f "$i" ]; then
	    new="${SSLBASE}/${CA}/certs/"`basename $i`;
	    mv "$i" "$new";
	    hash=`openssl x509 -hash -noout -in "$new"`;
	    while :; do
		linkname="${CA}/certs/""$hash"".""$count";
		if [ -h "$linkname" ]; then
			count=$((count + 1));
		    continue;
		else
		    ln -s "$new" "$linkname";
		    break;
		fi;
	    done;
	fi;
    done;
    cd "$OPWD"
}

init () {
	# remove old stuff
	rm -rf "$SSLBASE"

	# create the base directory
	mkdir -p "$SSLBASE"

	# make sure we have a password, generate one if we don't
	if ! test -e "$SSLBASE/password"; then
		touch "$SSLBASE/password"
		chmod 600 "$SSLBASE/password"
		makepasswd > "$SSLBASE/password"
	fi
	PASSWD=`cat "$SSLBASE/password"`

	local OPWD=`pwd`;

	# create directory infrastructure
	cd "$SSLBASE"
	mkdir -m 700 -p ${CA};
	mkdir -p ${CA}/{certs,crl,newcerts,private};
	echo "01" > ${CA}/serial;
	touch ${CA}/index.txt;

	eval "$(ucr shell ssl/common)"

	# make the root-CA configuration file
	mk_config openssl.cnf $PASSWD $DEFAULT_DAYS "$ssl_common"


	openssl genrsa -des3 -passout pass:"$PASSWD" -out ${CA}/private/CAkey.pem 2048
	yes '' | openssl req -config openssl.cnf -new -x509 -days 730 -key ${CA}/private/CAkey.pem -out ${CA}/CAcert.pem

	# copy the public key to a place, from where browsers can access it
	openssl x509 -in ${CA}/CAcert.pem -out /var/www/ucs-root-ca.crt

	# mv the certificate to the certs dir and link it to its hash value
	cp ${CA}/CAcert.pem ${CA}/newcerts/00.pem
	move_cert ${CA}/newcerts/00.pem

	# generate root ca request
	openssl x509 -x509toreq -in ${CA}/CAcert.pem -signkey ${CA}/private/CAkey.pem -out ${CA}/CAreq.pem -passin pass:$PASSWD

	find ${CA} -type f | xargs chmod 600
	find ${CA} -type d | xargs chmod 700
	
	chmod 755 ${CA}
	chmod 644 ${CA}/CAcert.pem
	#generate empty crl at installation time	
	openssl ca -config openssl.cnf -gencrl -out ${CA}/crl/crl.pem -passin pass:"$PASSWD"
	openssl crl -in ${CA}/crl/crl.pem -out /var/www/${CA}.crl -inform pem -outform der
	cp "${CA}/crl/${CA}.crl" /var/www/

	if getent group 'DC Backup Hosts' >/dev/zero
	then
		chgrp -R 'DC Backup Hosts' -- "$SSLBASE"
		chmod -R g+rwX -- "$SSLBASE"
	fi

	cd "$OPWD"
}


list_cert_names () {
   local OPWD=`pwd`
   cd "$SSLBASE"
   awk 'BEGIN { FS="\t"; }
    { if ( $1 == "V" )
	{
	    split ( $6, X, "/" );
	    for ( i=2; X[i] != ""; i++ ) {
		if ( X[i] ~ /^CN=/ ) {
		    split ( X[i], Y, "=" );
		    print $4 "\t" Y[2];
		}
	    }
	}
    }'< ${CA}/index.txt
    cd "$OPWD"
}


has_valid_cert () {
    list_cert_names | egrep -q "$1$";
}

renew_cert () {
	local OPWD=`pwd`;
	local path="$1";
	local cn="$2";
	local days="$3";
	local owner="$4"
	local extfile="$5"
	cd "$SSLBASE";
	
	if [ -z "$owner" ]; then
		owner="cert"
	fi

	if [ -z "$cn" ]; then
		echo "missing certificate name" 1>&2;
		return 1;
	fi
	
	local NUM=`list_cert_names | grep "$cn$" | sed -e 's/^\([0-9A-Fa-f]*\).*/\1/1'`;
	if [ -z "$NUM" ]; then
		echo "no certificate for $cn registered" 1>&2;
		return 1;
	fi;
	
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
	move_cert ${CA}/newcerts/*;
	cd "$OPWD";
}

# Parameter 1: Name des CN dessen Zertifikat wiederufen werden soll

revoke_cert () {
	local OPWD=`pwd`;
	local cn="$1";
	cd "$SSLBASE";

	if [ -z "$cn" ]; then
		echo "missing certificate name" 1>&2;
		return 1;
	fi

	local NUM=`list_cert_names | grep "$cn$" | sed -e 's/^\([0-9A-Fa-f]*\).*/\1/1'`;
	if [ -z "$NUM" ]; then
		echo "no certificate for $1 registered" 1>&2;
		return 1;
	fi;
	openssl ca -config openssl.cnf -revoke ${CA}/certs/${NUM}.pem -passin pass:"$PASSWD"
	openssl ca -config openssl.cnf -gencrl -out ${CA}/crl/crl.pem -passin pass:"$PASSWD"
	openssl crl -in ${CA}/crl/crl.pem -out /var/www/${CA}.crl -inform pem -outform der

	cd "$OPWD";
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
	    revoke_cert "$2";
	fi;

	if [ -z "$days" ]; then
		days=$DEFAULT_DAYS
	fi

	# generate a key pair
	mkdir -pm 700 $path
	mk_config "$path/openssl.cnf" "" $days "$cn" "$email" "$organizationalunit" "$country" "$state" "$locality" "$organization"
	openssl genrsa -out "$path/private.key" "$DEFAULT_BITS"
	yes '' | openssl req -config "$path/openssl.cnf" -new -key "$path/private.key" -out "$path/req.pem"

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
	move_cert ${CA}/newcerts/*;

	find $path -type f | xargs chmod 600
	find $path -type d | xargs chmod 700
	cd "$OPWD"
}
