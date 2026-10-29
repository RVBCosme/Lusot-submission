"""Guards every MS2 data tool runs before it touches a path (C202, C206, C222).

Claude's tools refuse every path with a part named sealed. Rene's own commands (C202)
take their sealed paths only inside a folder named sealed, start only from his own
console, and ask him to confirm before anything is written. A failure prints its class
only, so no traceback names a photo.

Task 5 copies is_sealed_name, refuse_sealed, require_sealed, console_ok,
require_console, confirm and quiet verbatim into backend/analysis/probes/set_b_masks.py,
because backend/analysis can't import eval/. A parity test compares the copies, so
those seven call nothing else defined in this module.
"""

import getpass
import os
import sys
from collections.abc import Callable


def is_sealed_name(name: str) -> bool:
    """True when one path part names sealed as Windows reads it: in any case, by its
    name before any ":" (so the NTFS stream sealed::$INDEX_ALLOCATION counts), and
    without trailing dots and spaces (so "sealed." and "sealed " count)."""
    return name.split(":", 1)[0].rstrip(". ").casefold() == "sealed"


def refuse_sealed(*paths: str | os.PathLike) -> None:
    """Exit 2 when any part of a path, as given or made absolute and normalised, names
    sealed (C222). It reads the strings only, never the disk."""
    for path in paths:
        given = os.fspath(path)
        for form in (given, os.path.normpath(os.path.abspath(given))):
            if any(is_sealed_name(part) for part in form.replace("\\", "/").split("/")):
                print("refused: path inside a folder named sealed", file=sys.stderr)
                sys.exit(2)


def require_sealed(path: str | os.PathLike, *, flag: str) -> None:
    """Exit 2 unless a part of the path, made absolute and normalised, names sealed
    (C202). It reads the string only, never the disk."""
    normal = os.path.normpath(os.path.abspath(os.fspath(path)))
    if not any(is_sealed_name(part) for part in normal.replace("\\", "/").split("/")):
        print(f"refused: {flag} must be inside a folder named sealed", file=sys.stderr)
        sys.exit(2)


def console_ok(*, is_console: Callable[[int], bool] | None = None) -> bool:
    """True when stdin and stdout are both consoles (C202).

    On Windows the default check is GetConsoleMode, which fails on NUL and on a pipe;
    os.isatty there calls NUL a terminal. Elsewhere it is os.isatty.
    """
    if is_console is None and sys.platform == "win32":
        import msvcrt
        from ctypes import byref, windll, wintypes

        def get_console_mode(fd: int) -> bool:
            mode = wintypes.DWORD()
            try:
                handle = wintypes.HANDLE(msvcrt.get_osfhandle(fd))
            except OSError:  # the descriptor isn't open
                return False
            return windll.kernel32.GetConsoleMode(handle, byref(mode)) != 0

        is_console = get_console_mode
    elif is_console is None:
        is_console = os.isatty
    return is_console(0) and is_console(1)


def require_console() -> None:
    """Exit 2 unless stdin and stdout are both a console, as in Rene's window (C202)."""
    if not console_ok():
        print(
            "refused: run this yourself, in a Windows PowerShell window",
            file=sys.stderr,
        )
        sys.exit(2)


def ask_password(*, ask: Callable[[str], str] | None = None) -> str:
    """Read the archive password, typed twice (C206). An empty one is refused, and so is
    one UTF-16-LE can't encode, as with the lone surrogates Windows getpass gives for an
    emoji, since 7z derives its key from that encoding.

    ask defaults to getpass.getpass, looked up at each call so tests can replace it.
    """
    if ask is None:
        ask = getpass.getpass
    password = ask("Archive password: ")
    if not password:
        print("refused: empty password", file=sys.stderr)
        sys.exit(2)
    if not _encodes(password):
        print("refused: the password can't be encoded", file=sys.stderr)
        sys.exit(2)
    if ask("Type it again: ") != password:
        print("refused: the two entries differ; nothing was written", file=sys.stderr)
        sys.exit(2)
    return password


def _encodes(password: str) -> bool:
    """True when UTF-16-LE can encode the password. The encoding error holds the
    password, so it ends here, and the refusal is raised outside its handler."""
    try:
        password.encode("utf-16-le")
    except UnicodeEncodeError:
        return False
    return True


def confirm(summary: str, *, ask: Callable[[str], str] | None = None) -> None:
    """Print the summary, then exit 2 unless Rene types yes (C202).

    ask defaults to input, looked up at each call so tests can replace it.
    """
    if ask is None:
        ask = input
    print(summary)
    if ask("Type yes to continue: ").strip() != "yes":
        print("stopped: nothing was done", file=sys.stderr)
        sys.exit(2)


def quiet(run: Callable[[], int]) -> int:
    """Return run(). Any exception, and Ctrl+C, prints only its class and returns 1, so
    no traceback names a photo. SystemExit passes through."""
    try:
        return run()
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001
        print(f"stopped: {type(error).__name__}", file=sys.stderr)
        return 1
