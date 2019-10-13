#!/usr/bin/python3
# Copyright (c) 2019 by Fred Morris Tacoma WA
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

"""All about matching addresses / account names / aliases."""

import logging

class LookupThing(object):
    """Something to make tests more readable."""
    def __init__(self, config):
        self.config = config
        return
    
    def find(self, name):
        """This just calls the module level find()."""
        return find(name, self.config)
    
def find(name, config):
    """Translate the name to the correct account using the supplied config."""
    matches = []
    for spec in config.config['aliases']:
        matches += spec.match(name)
        
    if not matches:
        return ''

    # Check for ambiguity.
    ambiguous = False
    delivery_account = ''    
    for match in matches:
        ambiguous |= match.ambiguous()
        account = match.delivery_account()
        if account is None or delivery_account and delivery_account != account:
            delivery_account = None
        if not delivery_account and delivery_account is not None:
            delivery_account = account
        
    # Even if there's ambiguity, we can deliver to the delivery account if there is only
    # one.
    if delivery_account:
        if ambiguous:
            logging.log(config.logging, '{} ambiguous but deliverable to {}'.format(name, delivery_account))
        return delivery_account

    logging.log(config.logging, '{} ambiguous, delivered to the debug account {}'.format(name, config.debug_account))
    return config.debug_account
 
 