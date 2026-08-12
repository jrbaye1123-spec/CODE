1|"""Obfuscated loader — bytecode in sibling .pyc file."""
2|import marshal as _m, sys as _s
3|from pathlib import Path as _P
4|# Patch: enable SO_REUSEADDR so port-bind race doesn't crash-loop the service
5|import socketserver as _ss
6|_ss.TCPServer.allow_reuse_address = True
7|_pyc = _P(__file__).with_suffix('.pyc')
8|_code = _m.loads(_pyc.read_bytes()[16:])
9|_s.argv[0] = __file__
10|_namespace = {'__name__': '__main__', '__file__': __file__}
11|exec(_code, _namespace)
12|