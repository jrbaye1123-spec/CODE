"""Obfuscated loader — bytecode in sibling .pyc file."""
import runpy as _rp, sys as _sys
_sys.argv[0] = __file__
_rp.run_path(__file__ + "c", run_name="__main__")
