# Copy `trualias.conf` and it should run.

Copy `trualias.conf.sample` to `trualias.conf` and you should be able to run `tcp_table_server.py`.

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
