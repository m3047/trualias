# What is `base_server.py`?

(This document (c) 2026 Fred Morris Consulting, TACOMA WA USA and distributed with the Trualias package.)

`base_server` is a sample TCP table implementation which you can utilize for testing / exploration or as a base for your own
TCP table service.

### Exploration

This is most useful for answering the question: _exactly what is getting passed to the service_? To run it in this mode, simply

1. Copy `base_server.ini.sample` to `base_server.ini`
2. `./base_server.py`

It isn't always crystal clear what is or may be passed to the table server depending on context: an address, an FQDN... which FQDN?
Something looked up from the client address? The envelope sender domain? You get the idea. The doc
(for example https://www.postfix.org/postconf.5.html#smtpd_sender_restrictions) gives a fair idea what a given
`check_` action does in the circumstances, but always good to verify.

I wrote a doc capturing some things which were important to me: http://athena.m3047.net/pub/postfix/postfix-restrictions-actions.html

### Expansion

So, maybe you want to do something with it? Good! (Spoiler alert, I wrote one which installs under
`smtpd_sender_restrictions` as a `check_sender_access` action. I wanted to do some tests based on `MX` records,
but I wanted to check the envelope sender domain first. Tell me your story and I'll probably share it with you.)

##### some place to start

Probably start with something resembling this:

```
"""Perform SMTPD sender checks.

This table service is intended to be called from smtpd_sender_restrictions as a
check_sender_access action:

    smtpd_sender_restrictions =
        hash:/etc/postfix/access check_sender_access tcp:127.0.0.1:3048
"""

from configparser import ConfigParser
from base_server import Configuration, Request, CoroutineContext, main

class MyConfiguration( Configuration ):

    # Sample stuff to give you ideas. Look at base_server.Configuration for how it works.
    @Configuration.property
    @Configuration.cached
    def mx_white_list(self):
        self.mx_white_list_parser = WhiteListParser()
        return self.mx_white_list_parser.parse( self.parsed.get( 'MX', 'white_list' ) ).result

class MyRequest( Request ):
    
    COMMANDS = dict(get=2, stats=1, jstats=1)
    STATISTICS_TYPES = ('success','not_found', 'bad', 'error', 'stats')
```
You'll want to adjust those `STATISTICS_TYPES` to the ones you're actually returning with `stop_timer()` below.
```
    LOGGING_CATEGORIES = set()
    #LOGGING_CATEGORIES = { 'raw_message' }

    # Errors should return an error status code.
    ERROR_STATUS_CODE = '400'
    # Errors should lie and return not found.
    #ERROR_STATUS_CODE = '500'
    
    VALID_DOMAIN_CHARS = re.compile(r'^[A-Z0-9._-]+$', flags=re.I)
    
    def __init__(self, message, statistics, request_stats, config):
        Request.__init__(self, message, statistics, request_stats, config, self.LOGGING_CATEGORIES)
        return
    
    #def validate_request(self, request):
        #return Request.validate_request(self, request)
    
    #def dispatch_request(self, request):
        #Request.dispatch_request(self, request)
        #return
    
    def get(self, request):
        """Expects the argument to be user@domain.name

        This is where you go to work! This is just some sample code to give you a feel.
        """
        try:
            sender_domain = request[1].split('@')[1].strip('.').lower()
        except Exception as e:
            logging.error('Did not receive an argument in username@host format. Check your configuration.')
            logging.warn('sender_domain extraction exception: {}'.format(e))
            sender_domain = None
        if sender_domain is None:
            self.response = '{} bad argument\n'.format( self.ERROR_STATUS_CODE )
            self.stop_timer('error')
            return

        # Make sure it's sane.
        if not self.VALID_DOMAIN_CHARS.fullmatch( sender_domain ):
            logging.warn('Domain "{}" contains invalid characters.'.format( sender_domain ) )
            self.response = '{} invalid characters\n'.format( self.ERROR_STATUS_CODE )
            self.stop_timer('error')
            return

        self.deferred = self.get_deferred( request, sender_domain)
        return
```
OK, so what's going on here? Our caller (`base_server.CoroutineContext.handle_requests()`) runs in coroutine
context. If we set `self.deferred` to an awaitable, then the caller will await it before continuing.

Logically the previous and following routines are part of the same function. Look at the definitions:

* `def get(self, request)`
* `async def get_deferred(self, request, sender_domain)`

If you're not doing any I/O, you could do all of the processing synchronously inside of `get()`.
```
    async def get_deferred(self, request, sender_domain):
        
        # Perform MX lookup.
        try:
            effective_mx = await mx_lookup( sender_domain, self.loop )
            if effective_mx is None:
                effective_mx = { sender_domain }
        except Exception as e:
            logging.warn('MX lookup failed: {}: {}'.format(e.__class__.__name__, e))
            self.response = '{} internal error\n'.format( self.ERROR_STATUS_CODE )
            self.stop_timer('error')
            return

        # Check the blocking list.
        for fqdn in effective_mx:
            if fqdn in self.config.mx_list:
                if PRINT_BLOCKLIST_HIT:
                    PRINT_BLOCKLIST_HIT('{} hit blocklist with {}'.format(request[1], fqdn))
                self.response = '200 {}\n'.format( self.config.mx_list[ fqdn ] )
                self.stop_timer('success')
                return
```
Returning `200...` for something found in the blocking list is a little ironic? I think so! So what you actually return in
`self.response` is going to be something like `200 REJECT Your email smells like something died.`
```
        self.response = '500 not found\n'
        self.stop_timer('not_found')
        return
```
The fall-through is the case where no match was found, or in other words "good" / not blocked.

So that is the leadup so you can do this (you can probably copy this verbatim at least to get started):

```
##################################################################################
# CONTEXT AND CONTROL

def allocate_context(config_loader, config, config_file, statistics):
    """Create your own adventure!
    
    A typical reason to contemplate subclassing CoroutineContext would be to handle a
    different type of request or handle requests differently. But you don't need to do
    that, instead subclass Request and then specify your subclass when instantiating
    CoroutineContext.
    """
    return CoroutineContext(config_loader, config, config_file, statistics, request_class=MyRequest)

def config_loader(f):
    """Create your own adventure!
    
    This server does not use the Trualias configuration parser, it uses the builtin Python
    ConfigParser
    """
    parser = ConfigParser()
    parser.read_file(f)
    config = MyConfiguration( parser )
    return config

if __name__ == "__main__":
    main(allocate_context=allocate_context, config_loader=config_loader)
```

##### now what?

I would suggest:

1. Get your configuration working first. You can test it by importing your `config_loader()` from an interactive python shell: `config_loader( open('my_config.ini'))`
2. Get `MyRequest.get()` working. Think about logging. That's why there's statistics collectors.

##### final thoughts

Less is more? I've tried to keep this to what you need to get up and running. A lot just depends. I'll offer one
final thought. Although the server uses `asyncio`, threading will probably work fine to parallelize DNS lookups:

```
from dns.resolver import Resolver, NXDOMAIN, NoAnswer, Answer
import dns.rcode as rcode
import dns.rdatatype as rdtype

import concurrent.futures

def lookup_task_( fqdn ):
    """Actual MX lookup thread."""
    resolver = Resolver()
    try:
        result = resolver.query( fqdn, rdtype.MX )
    except (NXDOMAIN, NoAnswer):
        result = None
    return result

def mx_lookup( fqdn ):
    """Performs MX lookup for a domain / fqdn.
    
    It is possible for any FQDN to have an MX record associated with it.
    """
    with concurrent.futures.ThreadPoolExecutor() as executor:
        thread = executor.submit( lookup_task_, fqdn )
        result = thread.result()
    if result is None:
        return None
    resp = result.response
    if resp.rcode():
        logging.info('Got rcode {} for {}'.format( rcode.to_text(resp.rcode()), fqdn ))
        return None

    mx_list = set()
    for rset in resp.answer:
        if rset.rdtype != rdtype.MX:
            continue
        for rr in rset:
            mx_list.add( rr.to_text().split()[1].strip('.').lower() )

    return mx_list
```

# Does it not work for you?

I welcome pull requests, and I'd be happy just to have a conversation with you as well.
