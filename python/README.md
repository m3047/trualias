Copy `trualias.conf.sample` to `trualias.conf` and you should be able to run `tcp_table_server.py`.

It will listen on `127.0.0.1:3047` by default, and you should be able to query it with `postmap`:

```
# postmap -q "samissexy.34" tcp:127.0.0.1:3047
baz
```

It watches the configuration file and will reload it if it changes.

To actually call it from `main.cf` you will have to recompile `local(8)`. See the instructions in `../install/`.
