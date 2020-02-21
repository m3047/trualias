# Installation

_Copyright (c) 2019-2020 Fred Morris, Tacoma WA. Apache 2.0 license._

If you're running as a milter, go to the [MILTER_README](https://github.com/m3047/trualias/blob/master/install/MILTER_README.md).

### Assumptions

* Linux
* Python >= 3.6
* Fairly recent Postfix
* Using systemd for service management

### `local(8)` thinks this a horrible security vulnerability

Although you can run `postmap -q` to query the service just fine, recent versions of _Postfix_ won't use a TCP map
to resolve aliases. TCP maps are not encrypted; I wouldn't recommend using them over the internet. On the other hand,
if someone on your mail server has access to `/etc/passwd` and `/etc/aliases` I'm not sure there's much additional
risk. THE SECURITY RISKS ASSOCIATED WITH DISABLING THESE SECURITY CHECKS DEPENDS ON YOUR SECURITY AND DEPLOYMENT
POSTURE; USE AT YOUR OWN RISK.

Until distributions pick this up, you need to compile a custom version of `local` and replace the one which
comes with your _Linux_ distribution. For further analysis of the security implications, see [table_security_analysis.md](https://github.com/m3047/trualias/blob/master/install/table_security_analysis.md)

**1) Clone the source**

Clone the repository https://github.com/vdukhovni/postfix

**2) Edit the files**

Edit `src/util/dict_tcp.c`, commenting out the indicated lines and adding the line at the end:

```
292,295c292,295
<     if (dict_flags & DICT_FLAG_NO_UNAUTH)
<       return (dict_surrogate(DICT_TYPE_TCP, map, open_flags, dict_flags,
<                    "%s:%s map is not allowed for security sensitive data",
<                              DICT_TYPE_TCP, map));
---
> //     if (dict_flags & DICT_FLAG_NO_UNAUTH)
> //    return (dict_surrogate(DICT_TYPE_TCP, map, open_flags, dict_flags,
> //                 "%s:%s map is not allowed for security sensitive data",
> //                           DICT_TYPE_TCP, map));
312a313,314
>     // Mark it "trusted".
>     dict_tcp->dict.owner.status = DICT_OWNER_TRUSTED;
```

**3) Compile**

The following worked for me. In particular, note that `-DNO_NIS` was required.

```
# cd postfix_source/postfix
# make -f Makefile.init makefiles
# make makefiles CCARGS="-DNO_NIS"
# make 
```

**4) Replace `local` with the new version**

First you have to find it. It will be a file named `local`. HINT: Easiest way to do this is probably to query the
package manager to find out where it is, for instance:

```
# rpm -q -l postfix-3.3.1-lp150.12.1.x86_64 | grep local
/usr/lib/postfix/bin/local
/usr/share/man/man8/local.8.gz
```

shows us that the program is in `/usr/lib/postfix/bin/`. Overwrite that one with the one you just built:

```
# cp postfix_source/postfix/libexec/local /usr/lib/postfix/bin/
```

### Download and setup with systemd

1) Clone this repository into `/usr/local/share/`.

2) Review the service file `systemd/trualias.service` and make any needed changes (i.e. a user account instead of root).

2) Copy it to `/usr/lib/systemd/system/` or wherever is appropriate for your system.

4) Copy `python/trualias.conf.sample` to `python/trualias.conf`, review and make changes.

5) You should be able to start the service with `systemctl start trualias.service`.

By default it listens on `127.0.0.1:3047`. You don't have to restart the service to change the resolution rules; the
configuration file is watched and reloaded automatically. You will have to restart the service if you change configuration
parameters (host, port, logging level, debug account).

### Configuring `alias_maps`

Edit `/etc/postfix/main.cf` and append `tcp:127.0.0.1:3047` to `alias_maps`:

```
alias_maps = hash:/etc/aliases tcp:127.0.0.1:3047
```

# Example `procmailrc`

The supplied procmailrc file demonstrates how to extract the address which the mail message was delivered for,
query the table service with postmap, and use that to create an `X-Alias:` header which is added to the mail message.
