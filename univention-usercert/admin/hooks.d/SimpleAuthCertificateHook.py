from univention.admin.hook import simpleHook
import univention.debug as ud

import M2Crypto
import base64


class SimpleAuthCertificateHook(simpleHook):

	type = 'SimpleAuthCertificateHook'

	def __mapCertificate(self, module, ml):
		if module.hasChanged("simpleAuthCertificate"):
			newml = [mod for mod in ml if mod[0] != "userCertificate;binary"]
			newml.append((
				"userCertificate;binary",
				module.oldattr.get("userCertificate;binary", [b""])[0],
				base64.b64decode(module["simpleAuthCertificate"].encode('UTF-8'))))
			ml = newml
		return ml

	def hook_open(self, module):
		if module.get("simpleAuthCertificate"):
			try:
				x509 = M2Crypto.X509.load_cert_der_string(module["simpleAuthCertificate"])
				subject = x509.get_subject()
				issuer = x509.get_issuer()
				notAfter = x509.get_not_after()
				notBefore = x509.get_not_before()
				module.info["certificateSubjectCommonNameSimpleAuth"] = subject.CN
				module.info["certificateIssuerCommonNameSimpleAuth"] = issuer.CN
				module.info["certificateDateNotBeforeSimpleAuth"] = str(notBefore)
				module.info["certificateDateNotAfterSimpleAuth"] = str(notAfter)
			except Exception as exc:
				ud.debug(ud.ADMIN, ud.ERROR, "SimpleAuthCertificateHook: x509 parsing failed (%s)" % (exc,))
			module["simpleAuthCertificate"] = base64.b64encode(module["simpleAuthCertificate"].encode('UTF-8')).decode('ASCII')

	def hook_ldap_modlist(self, module, ml=[]):
		return self.__mapCertificate(module, ml)

	def hook_ldap_addlist(self, module, al=[]):
		return self.__mapCertificate(module, al)
