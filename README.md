# trualias

_Copyright (c) 2019-2024 Fred Morris, Tacoma WA. Apache 2.0 license._

Trualias is a postfix tcp table that lets you hand out your email address to anyone and everyone but add a bit of math to
protect yourself while doing so.

These days every vendor, grocery store, and app wants to register you with an email address so they can offer better service
(and track you). Most people either use their primary address which eventually gets flooded or create a second email account
which they use for "commercial" purposes. Trualias is a more sophisticated way to create aliases as an alternative to
[wildcarding an entire domain](https://blog.lewman.com/why-i-have-over-one-thousand-personal-email-addresses.html) which also lets you conveniently track the trackers!

Creating aliases or accounts every time you need to register for something or give out your email is a lot of work and annoying.
This is why Trualias lets you make up a "new" email address (alias) on the fly. Wildcarding a domain means you receive every single email sent to the domain and there's no easy way to determine whether or not you handed out a particular alias or not. We need a bit more error correction to make that determination. What's the error checking? An easy,
mentally-calculable checksum to add at the end of the alias.

### Postfix tcp tables

This utility is implemented as a [TCP table service](http://www.postfix.org/tcp_table.5.html) for both local aliases (`tcp_table_server`) and [virtual aliases](http://www.postfix.org/virtual.5.html) (`tcp_virtual_server`). Except for some rudimentary configuration settings (for network interface/address, port and logging level) and service startup there is nothing else to set up beside the specifics of your particular encoding scheme (in a file `trualias.conf` in the same directory as the script).

Inside of `main.cf` the only thing you need to do in a vanilla installation is add the service to `virtual_alias_maps` (assuming that the service is configured to listen on loopback port 3047):

```
virtual_alias_maps = hash:/etc/postfix/virtual tcp:127.0.0.1:3047
```

The domains with aliases being mapped do not need to be listed in `virtual_alias_domains`. Look in the `install/` and `python/` directories for further information about installation and setup.

You will want to use `tcp_virtual_server` rather than `tcp_table_server` because current
policy of the _Postfix_ team decrees TCP tables to be a security risk when looking up aliases for local accounts.

### Some examples

See [Grammar.md](https://github.com/m3047/trualias/blob/master/Grammar.md) for the syntax specification.

Let's start with an account named `foo`, and define an alias pattern for `foo-macys-m5`:

* append the company name
* compute a checksum (more correctly a verification code) which concatenates the first letter of the company name with the number of letters in it.

```
ACCOUNT foo
MATCHES "%account%-%alnum%-%code%
WITH CHAR(1,1,-), CHARS()
```

Maybe we don't want to reflect our actual account `foo`, and want to set up a traditionally-purposed alias `joe`, so that `joe-macys-m5` gets delivered to `foo`:

```
ACCOUNT foo
ALIASED joe
MATCHES "%alias%-%alnum%-%code%
WITH CHAR(1,1,-), CHARS()
```
You will quickly discover that you're not allowed to put certain things right next to each other, because they
will be rejected as semantically ambiguous, for instance `%alpha%%alpha%` is not allowed. But you can use literals to
separate them, for instance `%alpha%is%alpha%` as in the following rule, which will match `samissexy.34`:

```
ACCOUNT baz
MATCHES %alpha%is%alpha%.%code%
WITH CHARS(1), CHARS(2);
```

This also demonstrates resolution to an account for which neither an account or alias is specified.

Let's be honest, this is broken crypto for a broken internet. Nobody is doing SHA or MD5 in their head. But this is policy, not security: in other words we don't need to verifiably block every single bogus email forever, we just need to make the miscreant's jobs difficult enough that they move on to softer targets. Different people have different levels of mental facility with number and word games; some people have none at all (sorry, this may not be the tool for you). Part of the strength of this scheme is that everyone gets to choose a somewhat different format.

We make it easy to tailor the format of the alias and to compute a checkum which works for you:

**Identifiers** are used to select text to compute values on:

* `alnum` Alphanumeric characters. (Used in our examples above.)
* `alpha` Alphabetic characters.
* `number` Numerals.
* `fqdn` A domain name (alphanumeric, "-", ".").
* `ident` An "identifier" (alphanumeric, "-","_").

**Functions** are used to calculate parts of the checksum from identifiers:

* `DIGITS()` Count of digits.
* `ALPHAS()` Count of alphabetic characters.
* `LABELS()` Count of labels in an domain name.
* `CHARS()` Count of characters.
* `VOWELS()` Count of vowels.
* `ANY()` Any character in an identifier.
* `NONE()` Any character not in an identifier.
* `CHAR()` The character at a certain position in an identifier.
