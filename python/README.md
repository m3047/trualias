# Copy `trualias.conf` and it should run.

Copy `tcp_table_server.conf.sample` to `tcp_table_server.conf` and you should be able to run `tcp_table_server.py`.

It will listen on `127.0.0.1:3047` by default, and you should be able to query it with [`postmap`](http://www.postfix.org/postmap.1.html):

```
# postmap -q "samissexy.34" tcp:127.0.0.1:3047
baz
```

It watches the configuration file and will reload it if it changes.

To actually call it from `main.cf` you will have to recompile `local(8)`, or consider using `tcp_virtual_server` with `virtual_alias_maps` (probably a better option). See the instructions in `../install/`.

### Hacking 101

This is a [plaintext protocol](http://www.postfix.org/tcp_table.5.html). Got `telnet`?

```
# telnet 127.0.0.1 3047
Trying 127.0.0.1...
Connected to 127.0.0.1.
Escape character is '^]'.
get greyisthenewbeige.411
200 baz
^]
telnet> quit
Connection closed.
```

### Statistics!

The TCP Map server supports statistics! These can be logged periodically as well as queried for.

Briefly:

* _e_ elapsed seconds
* _d_ queue depth
* _n_ number per second
* _min_ minimum per second
* _max_ maximum per second
* _1_ most recent one second
* _10_ most recent 10 seconds average
* _60_ most recent 60 seconds average

```
# telnet athena.m3047.net 3047
Trying 209.221.140.128...
Connected to athena.m3047.net.
Escape character is '^]'.
foo
400 unrecognized command
get foo
500 not found
get samissexy.34
200 baz
stats
210 bad: emin=0.0000 emax=0.0000 e1=0.0000 e10=0.0000 e60=0.0000 nmin=0 nmax=1 n1=0.0000 n10=0.0000 n60=0.0167
212 connections: emin=0.0000 emax=0.0627 e1=0.0000 e10=0.0000 e60=0.0010 dmin=0 dmax=1 d1=1.0000 d10=1.0000 d60=0.2167 nmin=0 nmax=1 n1=0.0000 n10=0.0000 n60=0.0333
212 not_found: emin=0.0000 emax=0.0001 e1=0.0000 e10=0.0000 e60=0.0000 nmin=0 nmax=1 n1=0.0000 n10=0.1000 n60=0.0167
212 reads: emin=0.0000 emax=5.4090 e1=0.0000 e10=0.8751 e60=0.1834 dmin=0 dmax=1 d1=1.0000 d10=1.0000 d60=0.2167 nmin=0 nmax=2 n1=0.0000 n10=0.2000 n60=0.1000
212 stats: emin=0.0000 emax=0.0000 e1=0.0000 e10=0.0000 e60=0.0000 nmin=0 nmax=0 n1=0.0000 n10=0.0000 n60=0.0000
212 success: emin=0.0000 emax=0.0007 e1=0.0000 e10=0.0001 e60=0.0000 nmin=0 nmax=1 n1=0.0000 n10=0.1000 n60=0.0333
212 writes: emin=0.0000 emax=0.0001 e1=0.0000 e10=0.0000 e60=0.0000 dmin=0 dmax=0 d1=0.0000 d10=0.0000 d60=0.0000 nmin=0 nmax=1 n1=0.0000 n10=0.2000 n60=0.0667
jstats
212 [{"name": "connections", "elapsed": {"minimum": 0.0, "maximum": 0.06274080276489258, "one": 0.0, "ten": 0.0, "sixty": 0.0010456800460815429}, "depth": {"minimum": 0, "maximum": 1, "one": 1, "ten": 1.0, "sixty": 0.8333333333333334}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.03333333333333333}}, {"name": "reads", "elapsed": {"minimum": 0.0, "maximum": 5.409029722213745, "one": 0.0, "ten": 0.0, "sixty": 0.21678426861763}, "depth": {"minimum": 0, "maximum": 1, "one": 1, "ten": 1.0, "sixty": 0.8333333333333334}, "n_per_sec": {"minimum": 0, "maximum": 2, "one": 0, "ten": 0.0, "sixty": 0.11666666666666667}}, {"name": "writes", "elapsed": {"minimum": 0.0, "maximum": 9.918212890625e-05, "one": 0.0, "ten": 0.0, "sixty": 7.673104604085286e-06}, "depth": {"minimum": 0, "maximum": 0, "one": 0, "ten": 0.0, "sixty": 0.0}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.08333333333333333}}, {"name": "success", "elapsed": {"minimum": 0.0, "maximum": 0.0007426738739013672, "one": 0.0, "ten": 0.0, "sixty": 2.3651123046875e-05}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.03333333333333333}}, {"name": "not_found", "elapsed": {"minimum": 0.0, "maximum": 0.00010251998901367188, "one": 0.0, "ten": 0.0, "sixty": 1.708666483561198e-06}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.016666666666666666}}, {"name": "bad", "elapsed": {"minimum": 0.0, "maximum": 3.910064697265625e-05, "one": 0.0, "ten": 0.0, "sixty": 6.516774495442708e-07}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.016666666666666666}}, {"name": "stats", "elapsed": {"minimum": 0.0, "maximum": 0.0016276836395263672, "one": 0.0, "ten": 0.0, "sixty": 2.7128060658772786e-05}, "n_per_sec": {"minimum": 0, "maximum": 1, "one": 0, "ten": 0.0, "sixty": 0.016666666666666666}}]
```

### Differences between `alias_map` and `virtual_alias_map` in Postfix

There are a couple of differences between these.

|   | `Delivered-To:` header | query string |
| - | -------------------- | ------------ |
| **alias_map** | alias address | account ("left-hand side") |
| **virtual_alias_map** | delivery address | full email address |

As a consequence, `tcp_table_server` expects just the account and returns an account, whereas `tcp_virtual_server` expects the
whole aliased email address and returns a whole email address. The `X-Original-To:` header always contains the alias address.

### Pre and Post Processing

See `preprocessing_sample.py` for further documentation. In a nutshell, you can e.g. make matching case insensitive by lower
casing with the following:

1) Edit `preprocessing_sample.py` and change `preprocess()` as follows:

```
def preprocess( alias, domain=None):
    """Called before Trualias looks up account for the alias."""
    return (alias.lower(), domain)
```

2) Edit your configuration and add the line:

```
PROCESSOR: preprocessing_sample
```
