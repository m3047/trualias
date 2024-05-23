#!/usr/bin/python3
"""Sample Pre- and Post- Processing module for PROCESSOR

The way this would be specified in the configuration file is:

    PROCESSOR: preprocessing_sample

Not intended to be a general catchall framework for processing aliases, although
I can see why that might be tempting. If you have a great idea let's talk, maybe
I can help.

Calls the functions

    preprocess( alias, [ domain | None ] ) -> (alias, [ domain | None ] )

and

    postprocess( account, [ domain | None ] ) -> (account, [ domain | None ] )
   
tcp_virtual_server supplies the domain, tcp_table_server does not.

Both functions should be defined. If the operation is a null op, it should return
the arguments unchanged.

In preprocess / postprocess the alias / account argument represents the lefthand
side of the "@" sign. So in preprocess() it's the hypothetical alias to be translated
and in postprocess() it's the account which is returned from translation.

If an exception is encountered when one of these functions is called the exception
is logged, but the processing result is as though nothing was matched.

There is an additional function:

    reload()

which is called whenever the configuration reloads. This can be used to do whatever
voodoo it is you choose to do with ALIASES / ACCOUNTS. Reloading is not intended
to account for changes to the processing module itself, only to the aliases defined in
the configuration. (In other words the python code cache is not invalidated. It
is possible to load a postprocessing module after the service starts, it is just
not possible to reload a changed postprocessing module.)

If an exception is encountered when reload() is called this is treated as a
ConfigurationError and the configuration fails to load.

ACCOUNTS and ALIASES Global Variables
-------------------------------------

When a configuration is parsed lists of aliases and accounts are compiled as part
of the spec creation process (they're used for semantic validity checks).

The global variables defined here are updated with those lists whenever a
configuration is loaded. The lists may change when the configuration is reloaded.
Do not cache them and assume they remain unchanged, forever.
"""

ACCOUNTS = set()
ALIASES = set()

def reload():
    return

def preprocess( alias, domain=None):
    """Called before Trualias looks up account for the alias."""
    return (alias, domain)

def postprocess( account, domain=None):
    """Called after Trualias has determined the associated account."""
    return (account, domain)
