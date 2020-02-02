# Configuring Milter support

This milter edits envelope recipients, this _could_ be supported by milters during SMTP `RCPT` if
the executor supports _fast forwarding_ but most (if not all) of them don't.

In _Postfix_ this means that `local_delivery_maps` cannot be utilized as a screen for invalid accounts.
First off, _Postfix_ runs the `local_delivery_maps` checks before running milters and since the (unresolved)
aliases aren't accounts mail would be rejected; and since milters do not _fast forward_, `local_delivery_maps`
can't be applied after milters are run. (If you want to use `local_delivery_maps`, consider recompiling
`local(8)` and using the TCP table, it's what I do.)

If run with a _fast forwarding_ executor, this milter could be chained to a separate milter providing
identity verification and that milter could in turn reject invalid recipients during SMTP `RCPT`, but 
we're not running a _fast forwarding_ executor.

From all of this, it is unavoidable that the milter needs to invoke some source of identity and make the
rejection decision itself.

### Running a second instance of _Postfix_ smtpd with `VRFY` enabled

The source of identity truth implemented in the milter is SMTP `VRFY` (and declared local domains). If you
have some other source of identity truth that you're plugging _Postfix_ into, you're strongly encouraged to
call that source of truth directly from the milter and not rely on `VRFY`.

We will run two copies of smtpd for these reasons:

* Allowing the use of `VRFY` locally.
* Running `local_recipient_maps` checks in the copy running `VRFY` but not in the copy running the milter (and processing actual mail.

The following defaults are established in `main.cf`:

* `smtpd_milters =` (blank)
* `local_recipient_maps = proxy:unix:passwd.byname $alias_maps` (or as appropriate)
* `disable_vrfy_command = yes`

This provides maximum configuration safety, as by default (if `master.cf` is used without
alteration) `local_recipient_maps` is defined and the `VRFY` command is disabled.

For the specific `smtpd` instances in `master.cf`:

* Default instance of `smtpd` (port 25)
  * `-o smtpd_milters = inet:192.168.123.1:5000` (or as appropriate)
  * `-o local_recipient_maps =` (blank)

* Validating instance of `smtpd` (port 5025)
  * `-o disable_vrfy_command = no`

So, in `master.cf` it might look like this:

```
# ==========================================================================
# service type  private unpriv  chroot  wakeup  maxproc command + args
#               (yes)   (yes)   (no)    (never) (100)
# ==========================================================================
smtp      inet  n       -       n       -       -       smtpd
    -o smtpd_milters=inet:192.168.123.1:5000
    -o local_recipient_maps=
5025      inet  n       -       n       -       -       smtpd
    -o disable_vrfy_command=no
```

Presumably you can firewall port `5025` or restrict it to the loopback or local interface.

In the milter server's config file, set `SMTP HOST` and `SMTP PORT` accordingly. You must **also**
set `LOCAL HOST` and `LOCAL DOMAINS` appropriately. `LOCAL HOST` is sent during `EHLO` and may
affect how `VRFY` interprets addresses. `LOCAL DOMAINS` represents the domains for which trualias
resolution and identity verification is even attempted and **must** accurately reflect your
environment. Anything not in `LOCAL DOMAINS` is accepted unmolested (why? because local users
need to be able to submit mail for relaying for remote delivery, so make sure you've got relaying
permissions set correctly).

```
SMTP HOST: 192.168.123.2
SMTP PORT: 5025
LOCAL HOST: mail1.na.example.com
LOCAL DOMAINS: example.com na.example.com asia.example.com
```
