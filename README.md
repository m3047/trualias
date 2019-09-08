# trualias

_Copyright (c) 2019 Fred Morris, Tacoma WA. Apache 2.0 license._

Mentally computable verification codes for email aliases implemented as a postfix tcp table.

These days everybody wants an email address. If you give everybody your main email account, it will become unusable. A lot of people create a second email account which they use for "commercial" purposes. The more sophisticated create aliases, and some of us go as far as [wildcarding an entire domain](https://lewman.blog/2019/09/02/why-i-have-over-one-thousand-personal-email-addresses/).

The reason people opt for the more sophisticated approaches is that it enables tracking the trackers. But creating aliases or accounts beforehand is problematic (a problem that a wildcarded domain solves); and a wildcarded domain lets you make stuff up on the fly but there's no easy way to determine whether or not you're the one who gave out a particular alias. Wildcarding a domain also commits you to receiving all of the emails, regardless of whether the alias is bogus or not.

### Postfix tcp tables

This utility is implemented as a [TCP table service](http://www.postfix.org/tcp_table.5.html). Except for some rudimentary configuration settings (for network interface/address, port and logging level) and service startup there is nothing else to set up beside the specifics of your particular encoding scheme (in a file `trualias.conf` in the same directory as the script).

Inside of `main.cf` the only thing you need to do in a vanilla installation is add the service to `alias_maps` (assuming that the service is configured to listen on loopback port 3047):

```
alias_maps = hash:/etc/aliases tcp:127.0.0.1:3047
```

Look in the `install/` and `python/` directories for further information about installation and setup.

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
* `CHAR()` The character at a certain position in an identifier.
