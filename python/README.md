# Copy `trualias.conf` and it should run.

Copy `tcp_table_server.conf.sample` to `tcp_table_server.conf` and you should be able to run `tcp_table_server.py`.

It will listen on `127.0.0.1:3047` by default, and you should be able to query it with [`postmap`](http://www.postfix.org/postmap.1.html):

```
# postmap -q "samissexy.34" tcp:127.0.0.1:3047
baz
```

It watches the configuration file and will reload it if it changes.

To actually call it from `main.cf` you will have to recompile `local(8)`. See the instructions in `../install/`.

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

## Milters on the other hand...

If you're not already running milters this is probably not a good option for you. If you don't have your head
wrapped around local delivery accounts and not being an open relay or source of incorrectly addressed blowback,
it's probably not an option for you: if you rely on _Postfix_ `local_delivery_maps` to keep you out of trouble,
this is not for you, because they won't work with a milter which has as its sole purpose the rewriting of
recipients. The milter is written to use SMTP `VRFY` for local delivery validation, which is not an ideal
solution.

### When are milters a good option?

The milter implementation is a good option if either:

* You are using a _fast forwarding milter executor_ so that recipient edits are visible during the SMTP `RCPT` stage.

-- OR --

* You have a source of deliverable account truth. If you do, you are probably plugging _Postfix_ into it right now. So you'd have to write some code to query that source of truth from the milter. Hopefully not much, we tried to make it easy... `pydoc3 ./milter_server.py` should give you the notes you need to go about it.

See [install/MILTER_README.md](https://github.com/m3047/trualias/blob/master/install/MILTER_README.md) for
suggestions on configuring _Postfix_ in particular.

The following code pointers will take you to what you'd need to change to use some other source of identity:

* [CoroutineContext.verify_account()](https://github.com/m3047/trualias/blob/8c332475cd15cc09a9640462b667dafa95538634/python/milter_server.py#L151)
* [CoroutineContext.say_hello()](https://github.com/m3047/trualias/blob/8c332475cd15cc09a9640462b667dafa95538634/python/milter_server.py#L173)
* [CoroutineContext.handle_requests()](https://github.com/m3047/trualias/blob/8c332475cd15cc09a9640462b667dafa95538634/python/milter_server.py#L181)

No, this not intended to be the final solution; pull requests and feedback welcomed (did I mention I'm looking
for someone to be the milter champion?).




