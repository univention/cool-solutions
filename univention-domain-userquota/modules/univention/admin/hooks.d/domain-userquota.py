import univention.debug as ud
from univention.admin.hook import simpleHook


class DomainUserQuotaHook(simpleHook):
	type = 'DomainUserQuotaHook'

	ud.debug(ud.ADMIN, ud.INFO, 'domain_userquota:')

	def __merge_quota_settings(self, module, ml):
		if module.hasChanged('domainquota'):
			newml = []
			for i in ml:
				if i[0] != 'domainquota':
					newml.append(i)

			quotas = []
			if module.get('domainquota'):
				for quota in module.get('domainquota'):
					quotas.append('$$'.join(quota))

			newml.append((
				'domainquota',
				module.oldattr.get('domainquota'),
				quotas))

			ml = newml

		ud.debug(ud.ADMIN, ud.INFO, 'set module:%s' % str(ml))
		return ml

	def hook_open(self, module):
		if module.get('domainquota'):
			quotasettings = module.get('domainquota')
			module['domainquota'] = []
			for quotasetting in quotasettings:
				if not isinstance(quotasetting, (list, tuple)):
					module['domainquota'].append(quotasetting.split('$$'))
		ud.debug(ud.ADMIN, ud.INFO, 'open: module:%s' % str(module))

	def hook_ldap_modlist(self, module, ml=[]):
		return self.__merge_quota_settings(module, ml)

	def hook_ldap_addlist(self, module, ml=[]):
		return self.__merge_quota_settings(module, ml)
