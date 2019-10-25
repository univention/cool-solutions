from univention.admin.hook import simpleHook
import univention.debug as ud

import M2Crypto
import base64


class WindowsCertificateHook(simpleHook):

	type = 'WindowsCertificateHook'

	def __mapCertificate(self, module, ml):
		if module.hasChanged("windowsCertificate"):
			newml = [mod for mod in ml if mod[0] != "userCertificate;binary"]
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
				subject = x509.get_subject()
				issuer = x509.get_issuer()
				notAfter = x509.get_not_after()
				notBefore = x509.get_not_before()
				module.info["certificateSubjectCommonNameWindows"] = subject.CN
				module.info["certificateIssuerCommonNameWindows"] = issuer.CN
				module.info["certificateDateNotBeforeWindows"] = str(notBefore)
				module.info["certificateDateNotAfterWindows"] = str(notAfter)
			except Exception as e:
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
