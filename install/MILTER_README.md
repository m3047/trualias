Assuming that the following (effectively) defaults are established in `main.cf`, the following
will need to be specified with `-o` for the identified smtpd instances in `master.cf`.

* `smtpd_milters =` (blank)
* `local_recipient_maps = proxy:unix:passwd.byname $alias_maps` (or as appropriate)
* `disable_vrfy_command = yes`

This provides maximum configuration safety, as by default (if `master.cf` is used without
alteration) `local_recipient_maps` is defined and the `VRFY` command is disabled.

For the specific `smtpd` instances in `master.cf`:

* Default instance of `smtpd` (port 25)
** `-o smtpd_milters = inet:192.168.123.1:5000` (or as appropriate)
** `-o local_recipient_maps =` (blank)

* Validating instance of `smtpd` (port 5025)
** `-o disable_vrfy_command = no`

