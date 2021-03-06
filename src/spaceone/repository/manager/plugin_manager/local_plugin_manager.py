import logging

from spaceone.core import config
from spaceone.core.error import *
from spaceone.repository.model import *
from spaceone.repository.manager.plugin_manager import PluginManager

__all__ = ['LocalPluginManager']

_LOGGER = logging.getLogger(__name__)


class LocalPluginManager(PluginManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_model: Plugin = self.locator.get_model("Plugin")

    def register_plugin(self, params):
        def _rollback(plugin_vo):
            plugin_vo.delete()

        params['registry_url'] = self._get_registry_url()
        plugin_vo = self.plugin_model.create(params)
        self.transaction.add_rollback(_rollback, plugin_vo)

        return plugin_vo

    def update_plugin(self, params):
        plugin_vo = self.get_plugin(params['plugin_id'], params['domain_id'])
        return self.update_plugin_by_vo(params, plugin_vo)

    def enable_plugin(self, plugin_id, domain_id):
        plugin_vo = self.get_plugin(plugin_id, domain_id)
        return self.update_plugin_by_vo({'state': 'ENABLED'}, plugin_vo)

    def disable_plugin(self, plugin_id, domain_id):
        plugin_vo = self.get_plugin(plugin_id, domain_id)
        return self.update_plugin_by_vo({'state': 'DISABLED'}, plugin_vo)

    def update_plugin_by_vo(self, params, plugin_vo):
        def _rollback(old_data):
            _LOGGER.info(f'[ROLLBACK] Revert Plugin Data : {old_data["name"]} ({old_data["plugin_id"]})')
            plugin_vo.update(old_data)

        self.transaction.add_rollback(_rollback, plugin_vo.to_dict())
        return plugin_vo.update(params)

    def delete_plugin(self, plugin_id, domain_id):
        plugin_vo = self.plugin_model.get(domain_id=domain_id, plugin_id=plugin_id)
        plugin_vo.delete()

    def get_plugin(self, plugin_id, domain_id, only=None):
        #plugin_vo = self.plugin_model.get(domain_id=domain_id, plugin_id=plugin_id, only=only)
        plugin_vo = self.plugin_model.get(plugin_id=plugin_id, only=only)
        return plugin_vo

    def list_plugins(self, query, domain_id):
        # remove domain_id (for other domains)
        new_query = self._remove_domain_id_from_query(query)
        return self.plugin_model.query(**new_query)

    def stat_plugins(self, query, domain_id):
        return self.plugin_model.stat(**query)

    def get_plugin_versions(self, plugin_id, domain_id):
        """ Get version of image

        version: tag list of docker image
        create RegistryConnector
        call get_tags()

        Returns:
            A list of docker tag
        """
        plugin_vo = self.get_plugin(plugin_id, domain_id)

        connector = self.locator.get_connector("RegistryConnector")
        tags = connector.get_tags(plugin_vo.image)
        return tags

    def _remove_domain_id_from_query(self, query):
        """
        query = {'page': {'start': 1.0, 'limit': 2.0}}

        Remove domain_id at filter
        Update page to int value (may be float)
        """

        new_query = query.copy()

        # Warning: wrong transfer of query
        # page
        page = new_query.get('page', {})
        page_dic = {}
        for k, v in page.items():
            page_dic[k] = int(v)
        if page_dic != {}:
            new_query['page'] = page_dic

        v = new_query['filter']
        for index in range(len(v)):
            item = v[index]
            if 'k' in item and item['k'] == 'domain_id':
                del new_query['filter'][index]
                break
            elif 'key' in item and item['key'] == 'domain_id':
                del new_query['filter'][index]
                break
        return new_query

    @staticmethod
    def _get_registry_url():
        """
        Get a registry_url from RegistryConnector Config
        """

        try:
            connector_conf = config.get_global("CONNECTORS")
            # ex) 'https://registry.hub.docker.com'
            reg_con = connector_conf['RegistryConnector']['host']
            item = reg_con.split('://')
            return item[1]
        except Exception as e:
            raise ERROR_CONFIGURATION(key='CONNECTORS.RegistryConnector')
            _LOGGER.error('No RegistryConnector.host:%s' % config.get_global())
