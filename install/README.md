# Installation

_Copyright (c) 2019 Fred Morris, Tacoma WA. Apache 2.0 license._

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
comes with your _Linux_ distribution.

**1) Clone the source**

Clone the repository https://github.com/vdukhovni/postfix

**2) Edit the files**

Edit the following two files, commenting out the indicated lines.

```
src/util/dict_tcp.c:
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

src/local/alias.c:
205c205
<           if (dict->owner.status == DICT_OWNER_TRUSTED) {
---
> //        if (dict->owner.status == DICT_OWNER_TRUSTED) {
208,230c208,230
<           } else {
<               if (dict->owner.status == DICT_OWNER_UNKNOWN) {
<                   msg_warn("%s: no owner UID for alias database %s",
<                            myname, *cpp);
<                   dsb_simple(state.msg_attr.why, "4.3.0",
<                              "mail system configuration error");
<                   *statusp = defer_append(BOUNCE_FLAGS(state.request),
<                                           BOUNCE_ATTR(state.msg_attr));
<                   return (YES);
<               }
<               if ((errno = mypwuid_err(dict->owner.uid, &alias_pwd)) != 0
<                   || alias_pwd == 0) {
<                   msg_warn(errno ?
<                            "cannot find alias database owner for %s: %m" :
<                          "cannot find alias database owner for %s", *cpp);
<                   dsb_simple(state.msg_attr.why, "4.3.0",
<                              "cannot find alias database owner");
<                   *statusp = defer_append(BOUNCE_FLAGS(state.request),
<                                           BOUNCE_ATTR(state.msg_attr));
<                   return (YES);
<               }
<               SET_USER_ATTR(usr_attr, alias_pwd, state.level);
<           }
---
> //        } else {
> //            if (dict->owner.status == DICT_OWNER_UNKNOWN) {
> //                msg_warn("%s: no owner UID for alias database %s",
> //                         myname, *cpp);
> //                dsb_simple(state.msg_attr.why, "4.3.0",
> //                           "mail system configuration error");
> //                *statusp = defer_append(BOUNCE_FLAGS(state.request),
> //                                        BOUNCE_ATTR(state.msg_attr));
> //                return (YES);
> //            }
> //            if ((errno = mypwuid_err(dict->owner.uid, &alias_pwd)) != 0
> //                || alias_pwd == 0) {
> //                msg_warn(errno ?
> //                         "cannot find alias database owner for %s: %m" :
> //                       "cannot find alias database owner for %s", *cpp);
> //                dsb_simple(state.msg_attr.why, "4.3.0",
> //                           "cannot find alias database owner");
> //                *statusp = defer_append(BOUNCE_FLAGS(state.request),
> //                                        BOUNCE_ATTR(state.msg_attr));
> //                return (YES);
> //            }
> //            SET_USER_ATTR(usr_attr, alias_pwd, state.level);
> //        }
```

**3) Compile**

The following worked for me. In particular, note that `-DNO_NIS` was required.

```
cd postfix_source/postfix
make -f Makefile.init makefiles
make makefiles CCARGS="-DNO_NIS"
make 
```

**4) Replace `local` with the new version**

First you have to find it. It will be a file named `local`. HINT: Easiest way to do this is probably to query the
package manager to find out where it is, for instance:

```
 rpm -q -l postfix-3.3.1-lp150.12.1.x86_64 | grep local
/usr/lib/postfix/bin/local
/usr/share/man/man8/local.8.gz
```

shows us that the program is in `/usr/lib/postfix/bin/`. Overwrite that one with the one you just built:

```
cp postfix_source/postfix/libexec/local /usr/lib/postfix/bin/
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
