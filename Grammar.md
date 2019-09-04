# Alias Specification Grammar

The configuration file contains configuration parameters and alias specifications.

```
<statement> := <alias-spec> | <config-statement>
```

### Configuration statements

Configuration statements fit on a single line and are terminated by a newline. The following configuration items are available:

* `CASE SENSITIVE` (boolean) Whether stuff should be converted to lowercase before computation or not.
* `HOST` (IP address) The address in turn determines the network interface which will be bound.
* `PORT` (TCP port) The port the service should listen on.
* `LOGGING` (enum) One of `debug`, `info`, `warning`, `error`, `critical` in order of increasing severity.

```
<config-statement> := <conf-item> : <conf-value> <newline>
<conf-item> := CASE SENSITIVE | HOST | PORT | LOGGING
<conf-value> := <boolean> | <address> | <integer> | <log-level>
```

### Alias specifications

Alias statements declare accounts, optional alias mappings, and then a way of calculating a checksum for the alias.

```
<alias-spec> := ACCOUNT <account>[,...]
                { USING <identifier-type> }
                { ALIASED *|<alias>[,...] }
                MATCHES <match-expr>
                WITH <calc-expr>;
```

`account` must exist for local delivery. (Wildcarded accounts: supporting wildcarded accounts was deemed infeasible
because there was no portable way to determine accounts or in other words to call `proxy:unix:passwd.byname` from the service.)
Multiple accounts MAY be declared; if multiple accounts are specified then `ALIASED` MUST be omitted or wildcarded. A
given account may occur in only one statement.

The account is available for matching within the match expression as `%account%`.

The `USING` clause is optional and forces use of a particular identifier pattern (see below). By default
`ident` is used.

The `ALIASED` clause is optional; `ALIASED *` is equivalent to omitting the clause. When wildcarded, the alias
is identical to the account. If a single account is declared, multiple aliases MAY be specified. If multiple
accounts are declared, then the `ALIASED` clause MUST be omitted or wildcarded. A given alias may occur in only one
statement.

The alias is available for matching within the match expression as `%alias%`.

##### match-expr

Match expressions are enclosed in double quotes and consist of literals interspersed with match values.

```
<match-expr> := "[<match-val>|<literal>][...]"
```

`literal` is simply a literal character. `match-val` is inside "%" characters and there are three kinds: account/alias,
identifier, and code.

```
<match-val> := %[<acct-alias>|<identifier>|code]%
```

`acct-alias` is either `account` or `alias`, is declared in either the `ACCOUNT` or `ALIASES` clauses, and
matches a locally deliverable email destination.

`code` is the literal string "code", and matchs the result of the calculation expression.

`identifier` is one of the identifier matching classes:

* `alnum`: matches letters and numerals
* `alpha`: matches letters only
* `number`: matches numerals only
* `fqdn`: matches a domain name, or in other words runs of letters, numerals and dashes separated by dots.
* `ident`: matches the common identifier pattern, which is to say letters, numerals, "-" and "_".

##### calc-expr

A calc expression is a comma separated list of function calls and literals (not white space). The function results
and literals are concatenated in sequence to form the value available inside the match expression as `%code%`.

The following functions are available:

* `DIGITS({n})` Count of digits.
* `ALPHAS({n})` Count of alphabetic characters.
* `LABELS({n})` Count of labels in an domain name.
* `CHARS({n})` Count of characters.
* `VOWELS({n})` Count of vowels.
* `CHAR({n},{label},index,default)` The character at a certain position in an identifier.

**Multiple identifiers:** It is possible to perform more than one identifier match in a match expression. For instance
the following two expressions are (almost) identical:

```
"%account%-%fqdn%-%code%"
"%account%-%ident%.%ident%-%code%"
```

(The difference is that the second one allows "_" in the labels.) For the purposes of the rest of this discussion,
assume that the address being tested is `joe-macys.com-mc2`. In the case where multiple identifier matches were performed,
the first optional parameter =n= specifies the particular match. In the case of an `%fqdn%` match, the second parameter
to `CHAR()` specifies the particular label to match.

| fqdn | ident |
| ---- | ----- |
| `CHARS()` | Can't be done, as in the fqdn case it returns the length of the entire FQDN ("9"). |
| Can't be done, as in the ident case it returns the length of the second label ("3"). | `CHARS(2)` |
| `LABELS()` | Can't be done, only applies to `%fqdn%`. |
| `CHAR(2,1,-)` | `CHAR(2,1,-)` |

That last example is a little tricky, but it does the right thing. In the `%fqdn%` case there is only one identifier,
so the first parameter isn't needed but the label needs to be specified. In the `%ident%` case there are two identifiers,
so the first parameter is required but there aren't labels so the second parameter isn't needed.

Theoretically if you had multiple `%fqdn%` identifiers then you'd need all four parameters.

### Some examples

##### An account with a checksummed identifier

Matches `foo-google-g6`, `foo-macys-m5`.

This is the most basic example. Accounts cannot contain "-".

```
ACCOUNT foo
MATCHES "%account%-%ident%-%code%"
WITH CHAR(1,-), CHARS();
```

Note that this is semantically identical to 

```
ACCOUNT foo
ALIASED *
MATCHES "%account%-%ident%-%code%"
WITH CHAR(1,-), CHARS();
```

##### Several account with the same policy

Matches `foo-google-g6` and `baz-google-g6`, delivering to local accounts `foo` and `baz` respectively.

```
ACCOUNT foo, bar, baz
MATCHES "%account%-%ident%-%code%"
WITH CHAR(1,-), CHARS();
```

##### An account with a couple of aliases and a checksummed identifier

Matches `joe-google-g6` and `paul-macys-m5` and delivers them to the local account `joe`.

```
ACCOUNT foo
ALIASED joe, paul
MATCHES "%alias%-%ident%-%code%"
WITH CHAR(1,-), CHARS();
```

##### An account with a checksummed domain name

Matches `foo-google.com-gm10` and `foo-register.co.uk-ro14`.

```
ACCOUNT foo
MATCHES "%account%-%fqdn%-%code%"
WITH CHAR(1,1,-), CHAR(2,-1,-), CHARS();
```

##### An account with a checksummed domain name and a different calculation

Matches `foo-google.com-gm6` and `foo-register.co-ro8`.

This does NOT match `foo-register.co.uk-ro8` (too many labels,
we explicitly specified two identifiers separated by one dot).

```
ACCOUNT foo
MATCHES "%account%-%ident%.%ident%-%code%"
WITH CHAR(1,1,-), CHAR(2,-1,-), CHARS(1);
```

##### An account with a year along with the account name

Matches `foo-experian-19-e82` and `foo-nytimes-2019-n74`, although it doesn't perform much actual
validation of the year.

```
ACCOUNT foo
MATCHES "%account%-%alnum%-%number%-%code%"
WITH CHAR(1,1,-), CHARS(1), CHARS(2);
```

This also matches, although it's overly clever and relies on the coincidence that there were no digits
in the company names.

```
ACCOUNT foo
MATCHES "%account%-%ident%-%code%"
WITH CHAR(1,-), ALPHAS(), DIGITS();
```

If you truly want to validate years (treat them as an enumeration) you can declare them as aliases. Matches
`foo-experian-19-e8` and `foo-nytimes-2019-n7`.

```
ACCOUNT foo
ALIASED 18, 2018, 19, 2019
MATCHES "%account%-%ident%-%alias%-%code%"
WITH CHAR(1,-), CHARS();
```


