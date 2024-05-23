#!/usr/bin/python3
# Copyright (c) 2019,2024 by Fred Morris Tacoma WA
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

"""Internal components of the verified alias service.

There are four major components:

    alias:         Machinery and components for describing an alias specification
                   and resolving aliases to delivery addresses.
    config:        Components for representation of a configuration and
                   querying a configuration.
    parser:        Components for parsing a configuration from text.
    lookup:        Machinery for resolving a supplied name based on the
                   configuration.
                   
There are two methods here which you generally need to "make it go":

    1) load_config(stream, raise_on_error=False) -> config.Configuration

            stream:     use a filehandle ;-)
            Returns:    a configuration you can use

        This is an alias for config.from_text().
    
    2) find(name, config) -> delivery address (string)
    
            name:       this would be an alias to be resolved
            config:     a Configuration object
            
        Call this to attempt to resolve an alias to a delivery address, using the
        specified configuration.
"""

from .config import from_text as load_config
from .lookup import find
from .config_base import HOST, PORT, LOGGING, DEBUG_ACCOUNT

