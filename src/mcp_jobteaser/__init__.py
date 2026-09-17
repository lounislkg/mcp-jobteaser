def main() -> None:
    # Imported lazily so that `python -m mcp_jobteaser.server` doesn't end up
    # importing the server module twice (once as `mcp_jobteaser.server` via
    # this eager import, once as `__main__`), which Python warns about.
    from mcp_jobteaser.server import main as _main

    _main()

