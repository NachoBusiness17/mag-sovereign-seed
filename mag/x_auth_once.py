"""One-shot X OAuth login for the @groundingwave surface.
Run (Mag root, venv): python -m mag.x_auth_once
Opens the browser, auto-catches the 8788 callback, exchanges immediately,
writes memory/runs/x_oauth/tokens.json. No paste race.
"""
import time

from . import x_oauth as x


def main() -> None:
    d = x.start()
    if not d.get("ok"):
        print(d)
        return
    print("AUTH URL:", d["authorize_url"])
    print("waiting up to 600s for callback on", d["redirect_uri"])
    t0 = time.time()
    while not x._captured.get("code") and time.time() - t0 < 600:
        time.sleep(1)
    code = x._captured.get("code", "")
    if not code:
        print("no callback captured — rerun and approve faster")
        return
    print(x.complete(code))


if __name__ == "__main__":
    main()
