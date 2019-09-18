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

"""Internal components of the verified alias service.

There are three major components:

    config_parser: Components for parsing the textual representation of a
                   configuration and querying a configuration.
    controller:    Receiving and dispatching requests and responses, and
                   orchestrating use of resources to generate responses for
                   requests.
    name_cracker:  Machinery for resolving a supplied name based on the
                   configuration.
"""

