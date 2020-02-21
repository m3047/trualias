# An Analysis of the Postfix Security Model for Tables / Maps

THE CONCLUSIONS STATED HERE ARE FOR ADVISORY AND DISCUSSION PURPOSES. DETERMINATION OF SUITABILITY AND
RISK IN A GIVEN ENVIRONMENT IS UP TO THE READER.

### Background

The _Postfix_ Mail Transport Agent is a well known, understood and respected SMTP mailer implementation.
It is written in _C_, and is intentionally based on carefully crafted primitives to obviate at least some
of the common coding errors in _C_ (e.g. memory management) which lead to security vulnerabilities.

Additional architectural considerations around security occur in the context of normal mailer operations
(who is allowed to send mail, who is allowed to relay, policy on remote mailer configuration, etc.). Not
as clearly articulated are architectural considerations such as "network connections are bad" which seem to
be part of the fabric of the mailer itself.

The "network connections are bad" notion is seen by comparison of various dictionary / mapping implementations
represented by the files `src/util/dict*.c`. A concrete example would be that _TCP maps_, represented by
`dict_tcp.c` cannot be utilized with `alias_maps` because `local(8)` rejects their use.

### The Security Model

For our purposes here code consists of:

* _trusted code_ which performs a mailer-related operation, for instance `local(8)` delivering mail locally; and
* _untrusted code_, which is relied on to perform for example a lookup operation where certain lookup operations might be deemed "unsafe" in a given context.

##### Participation in the security model is Voluntary on the part of the untrusted code.

Continuing with the example of mapper implementations:

* An _untrusted mapper_ commits suicide when informed that its kind is not welcome.
* A _trusted mapper_ sets `dict_x->dict.owner.status = DICT_OWNER_TRUSTED`

An untrusted mapper such as `dict_tcp.c` can be made trusted by:

* Not committing suicide when asked; and
* setting ``dict_x->dict.owner.status = DICT_OWNER_TRUSTED`.

The change is simple and straightforward enough that it can be reproduced here (the following code is part
of _Postfix_, and subject to the _Secure Mailer License_), from `src/util/dict_tcp.c`:

```
/* dict_tcp_open - open TCP map */

DICT   *dict_tcp_open(const char *map, int open_flags, int dict_flags)
{
    DICT_TCP *dict_tcp;

    /*
     * Sanity checks.
     */
//+++
//     if (dict_flags & DICT_FLAG_NO_UNAUTH)
// 	       return (dict_surrogate(DICT_TYPE_TCP, map, open_flags, dict_flags,
// 		         "%s:%s map is not allowed for security sensitive data",
// 			           DICT_TYPE_TCP, map));
///---
    if (open_flags != O_RDONLY)
	      return (dict_surrogate(DICT_TYPE_TCP, map, open_flags, dict_flags,
            "%s:%s map requires O_RDONLY access mode",
                 DICT_TYPE_TCP, map));

    /*
     * Create the dictionary handle. Do not open the connection until the
     * first request is made.
     */
    dict_tcp = (DICT_TCP *) dict_alloc(DICT_TYPE_TCP, map, sizeof(*dict_tcp));
    dict_tcp->fp = 0;
    dict_tcp->raw_buf = dict_tcp->hex_buf = 0;
    dict_tcp->dict.lookup = dict_tcp_lookup;
    dict_tcp->dict.close = dict_tcp_close;
    dict_tcp->dict.flags = dict_flags | DICT_FLAG_PATTERN;
    if (dict_flags & DICT_FLAG_FOLD_MUL)
        dict_tcp->dict.fold_buf = vstring_alloc(10);
    //+++
    // Mark it "trusted".
    dict_tcp->dict.owner.status = DICT_OWNER_TRUSTED;
    //---
    
    return (DICT_DEBUG (&dict_tcp->dict));
}
```

There is no need to modify for instance `src/local/alias.c`, a part of the `local(8)` implementation.

### Security Implications: "Network Connections are Bad"

In the author's opinion the implications are "not so bad, as long as you're reasonable for your environment".
The following are some considerations entering into that assessment.

#### TRUE: The Machine is Trusted

Files and unix sockets are trusted.

##### multitenancy

Multitenancy is not an issue, and is presumed to be dealt with by e.g.
file permissions. It has to be acknowledged that file permissions could be intentionally or unintentionally
set to allow access to map data by other than the mailer software. File permissions on maps are not checked
to verify that only the mailer has permission.

#### FALSE: The Network Stack Cannot Be Trusted

The software speaks _SMTP_ to other hosts on the wide open internet; obviously the network stack is "safe enough".

#### FALSE: Network Peers Cannot Be Trusted

Presumably you're running the lookup service yourself and can trust it.

##### malicious data

Malicious or corrupt data could be ingested by the application with unknown impacts. But this could happen
from a file as well as from a network source.

##### ip / dns hijacking, man-in-the-middle

IP or DNS hijacking on loopback or `localhost` is improbable and we have already determined that we trust
the machine.

In a world of containerization and collapsed switching fabric the argument can be made that the "machine" is
actually the host operating environment. Certainly mechanisms exist in the host operating environment to mitigate
and control network access which do not exist in the fundamental "wired" environment of the internet itself.
For example, some of this information may be provided by the host operating system as "baked in" to the containers
it is running.

This comes down to where the network and service operators want to establish control boundaries, and
implementation of _defense in depth_. A network entirely provisioned with non-routing addresses is not
subject to random attacks from outside that environment, any such access has to be explicitly enabled whether
intentionally or accidentally.

#### IRRELEVANT: Network Services Expose Data

Architectural overreach. Files and sockets can expose data depending on file permissions, and we've already
established that multitenancy is ok and the risk is accepted for architectural purposes. Files could be present
on remote file shares, mounted over the network. Firewalls, routes, choices of interfaces to listen on are all
tools for network and system operators to implement access policies.

#### IRRELEVANT: Adversaries can Attack a Network Service

Architectural overreach. We have already established that we are running the network service; presumably
we've utilized the tools (firewalls, routes, interfaces, etc.) to implement what we feel are appropriate
access controls. The service is _not part of the mailer_: the dictionary implementation within the mailer
is a _client_ which talks to the service. The mailer doesn't even provide a working TCP map service implementation;
obviously we should take appropriate security concerns into consideration when implementing as well as
deploying such a service.






