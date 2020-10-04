#!/usr/bin/python3
# Copyright (c) 2019-2020 by Fred Morris Tacoma WA
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Postfix TCP virtual(5) Service.

REQUIRES PYTHON 3.6 OR BETTER

Provides a Postfix TCP service to resolve virtual aliases.
If the service is running (assuming it's listening on 127.0.0.1:3047), you can
query it with postmap (from the Postfix distribution) like this:

    postmap -q "alias_to_resolve" tcp:127.0.0.1:3047

Difference between This and TCP Table Server
--------------------------------------------

The tcp_table_server expects just the account name, whereas this expects
the entire email address and returns an email address (in the same domain).

For reference see aliases(5) and virtual(5) in the postfix manual pages.

To this end, there is an additional config parameter:

  ALIAS DOMAINS:    A list of domains for which alias resolution should
                    be attempted. Any alias which is matched is substituted
                    within the same domain.
"""

import logging

import tcp_table_server as base_server

import trualias
from trualias.parser import StreamParsingLoader as BaseConfigLoader
from trualias.config import Configuration as BaseConfiguration

CONFIG_FILE = ('tcp_virtual_server.conf','trualias.conf')

def to_fqdn_list(value):
    """Space separated list of FQDNs returned as a set."""
    return set((fqdn.lower() for fqdn in value.split()))

class ConfigLoader(BaseConfigLoader):
    
    def __init__(self, fh):
        BaseConfigLoader.__init__(self, fh)
        self.CONFIG_FIRST_WORDS |= set(('ALIAS',))
        self.CONFIG_SECOND_WORDS.update(ALIAS=['DOMAINS'])
        self.CONFIG_MAP.update((('ALIAS DOMAINS',('alias_domains', to_fqdn_list)),))
        return

class Configuration(BaseConfiguration):
    
    @property
    def alias_domains(self):
        return self.config.get('alias_domains', [])

class VirtualRequest(base_server.Request):

    def get(self, request):
        """A get request.
        
        Unlike tcp_table_server, the passed lookup item is expected to be a fully-specified
        email address (alias@example.com) rather than just an alias. The domain (example.com)
        must be listed in ALIAS DOMAINS.
        
        If matched, the resulting account is returned as a new email address in the same
        domain (account@example.com).
        """
        parts = request[1].split('@')
        print(parts)
        if len(parts) == 2 and parts[1].lower() in self.config.alias_domains:
            delivery_address = trualias.find(parts[0], self.config)
        else:
            self.response = '500 not found\n'
            self.stop_timer('not_found')
            return

        if delivery_address:
            self.response = '200 {}@{}\n'.format(delivery_address, parts[1])
            self.stop_timer('success')
        else:
            self.response = '500 not found\n'
            self.stop_timer('not_found')
        return

def allocate_context(config_loader, config, config_file, statistics):
    return base_server.CoroutineContext(config_loader, config, config_file, statistics, request_class=VirtualRequest)

def config_loader(f):
    config = Configuration().load(ConfigLoader(f), raise_on_error=True)
    if not config.alias_domains:
        logging.warn('Nothing is specified for alias_domains, so no mapping will occur!')
    return config

if __name__ == '__main__':
    base_server.main(allocate_context, base_server.resolve_config_files(CONFIG_FILE), config_loader)

