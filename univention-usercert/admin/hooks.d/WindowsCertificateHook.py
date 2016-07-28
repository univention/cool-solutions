from univention.admin.hook import simpleHook
import univention.debug as ud

import M2Crypto
import re
import string
import base64


class WindowsCertificateHook(simpleHook):

	type = 'WindowsCertificateHook'

	def __mapCertificate(self, module, ml):
		if module.hasChanged("windowsCertificate"):
			newml = []
			for i in ml:
				if i[0] != "userCertificate;binary":
					newml.append(i)
			newml.append((
				"userCertificate;binary",
				module.oldattr.get("userCertificate;binary", [""])[0],
				base64.decodestring(module["windowsCertificate"])))
			ml = newml
		return ml

	def hook_open(self, module):
		if module.get("windowsCertificate"):
			try:
				x509 = M2Crypto.X509.load_cert_der_string(module["windowsCertificate"])
				subject = str(x509.get_subject())
				issuer = str(x509.get_issuer())
				notAfter = str(x509.get_not_after())
				notBefore = str(x509.get_not_before())
				for i in subject.split('/'):
					if re.match('^CN=', i):
						module.info["certificateSubjectCommonNameWindows"] = string.split(i, '=')[1]
				for i in issuer.split('/'):
					if re.match('^CN=', i):
						module.info["certificateIssuerCommonNameWindows"] = i.replace("CN=", "")

				module.info["certificateDateNotBeforeWindows"] = notBefore
				module.info["certificateDateNotAfterWindows"] = notAfter
			except Exception, e:
				ud.debug(
					ud.ADMIN,
					ud.ERROR,
					"WindowsCertificateHook: x509 parsing failed (%s)" % str(e)
				)
			module["windowsCertificate"] = base64.encodestring(module["windowsCertificate"])

	def hook_ldap_modlist(self, module, ml=[]):
		return self.__mapCertificate(module, ml)

	def hook_ldap_addlist(self, module, al=[]):
		return self.__mapCertificate(module, al)
