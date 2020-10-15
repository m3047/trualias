# Installation

_Copyright (c) 2019-2020 Fred Morris, Tacoma WA. Apache 2.0 license._

If you're running as a milter, go to the [MILTER_README](https://github.com/m3047/trualias/blob/master/install/MILTER_README.md).

### Assumptions

* Linux
* Python >= 3.6
* Fairly recent Postfix
* Using systemd for service management

Although you can run `postmap -q` to query the service just fine, recent versions of _Postfix_ won't use a TCP map
to resolve local aliases so you should use `tcp_virtual_server` with `virtual_alias_maps`. TCP maps are not encrypted; I wouldn't recommend using them over the internet. On the other hand,
if someone on your mail server has access to `/etc/passwd` and `/etc/aliases` I'm not sure there's much additional
risk. For further analysis of the security implications, see [table_security_analysis.md](https://github.com/m3047/trualias/blob/master/install/table_security_analysis.md)

### Download and setup with systemd

1) Clone this repository into `/usr/local/share/`.

2) Review the service file `systemd/tcp_virtual.service` and make any needed changes (i.e. a user account instead of root).

2) Copy it to `/usr/lib/systemd/system/trualias.service` or wherever is appropriate for your system.

4) Copy `python/tcp_virtual_server.conf.sample` to `python/trualias.conf`, review and make changes. In particular, you should update `ALIAS DOMAINS` replacing `example.com` with your domain (it accepts a space-separated list of domains).

5) You should be able to start the service with `systemctl start trualias.service`.

By default it listens on `127.0.0.1:3047`. You don't have to restart the service to change the resolution rules; the
configuration file is watched and reloaded automatically. You will have to restart the service if you change configuration
parameters (host, port, logging level, debug account).

### Configuring `virtual_alias_maps`

Edit `/etc/postfix/main.cf` and append `tcp:127.0.0.1:3047` to `virtual_alias_maps`:

```
virtual_alias_maps = hash:/etc/aliases tcp:127.0.0.1:3047
```

# Example `procmailrc`

The supplied procmailrc file demonstrates how to extract the address which the mail message was delivered for,
query the table service with postmap, and use that to create an `X-Alias:` header which is added to the mail message.

The example is intended to work with `tcp_table_server.py`, which expects just the alias (or "left-hand side"). To make it work when `tcp_virtual_server.py` is running, you should pass the entire address to `postmap`, and extract it from the `X-Original-To:` header rather than `Delivered-To:`.
