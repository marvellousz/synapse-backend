# Synapse backend application package
#
# Leapcell (and some hosts) may run `python app/__init__.py` as the start command.
# That must start the ASGI server; an empty file exits immediately and shows
# "Runtime exited without providing a reason" / Server SHUTDOWN: failure.

if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    # Running this file sets sys.path[0] to app/; ensure project root is on path so `app.main` imports.
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
