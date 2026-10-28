"""The write-once encrypted archive (C205).

Each sealing step writes its archive once, in one pass, from memory and from files
named in its inputs. AES-256 encrypts the contents and the header, so even the member
names need the password. No tool opens, lists or adds to an archive after that, since
adding would mean decrypting its index. Rene tests each archive in 7-Zip, and the hash
in the committed record lets the sealed run prove the archive is the one written here.

Set D's sealer depends on py7zr alone, so this module imports neither numpy nor OpenCV.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import py7zr
import table


@dataclass(frozen=True)
class ArchiveFacts:
    """The archive file's name without its folder, its size in bytes and its SHA-256,
    for the committed record."""

    file: str
    size: int
    sha256: str


def write_sealed_archive(
    path: Path, password: str, members: Sequence[tuple[str, bytes | Path]]
) -> ArchiveFacts:
    """Create the archive at path in one pass, encrypted with the password, and return
    the facts of the written file.

    Each member is an arcname with its bytes, or with the Path of a file to copy in.
    The members are read once, so a generator works too. The archive is written once,
    in a folder only Rene may touch, so every failure that can be foreseen is raised
    before the file exists (S-R12). ValueError is raised when:
    - the path isn't absolute, or its name doesn't end in .7z or holds ":", as an NTFS
      stream's name does (S-R8, S-R2)
    - the password is empty (C206), or UTF-16-LE, the encoding 7z derives its key from,
      can't encode it, as with the lone surrogates Windows getpass gives for an emoji
    - an arcname is empty, absolute or not printable, repeats another in any case (NTFS
      would extract both to one file), holds a backslash or ":" (C:x and C:/x name a
      drive), or has an empty, "." or ".." part. py7zr would store some of these under
      another name, or fail on them only once the file exists, so an arcname that
      passes is stored exactly as given.
    - a source is neither bytes nor a Path to a file that isn't a link. py7zr would
      store a folder or a link as such, read a str as a path, and fail partway on a
      missing file or a bytearray.
    Each message is fixed text that names a member by its place in members, never by
    its name, and no exception chained to one holds the password.

    An existing file raises FileExistsError and keeps its bytes. Only an I/O error or
    an interrupt during the write leaves a partial archive, holding the members written
    so far, which Rene deletes before a rerun (§5.5).
    """
    if not path.is_absolute():
        raise ValueError("the archive path isn't absolute")
    if not path.name.endswith(".7z") or ":" in path.name:
        raise ValueError("the archive name must end in .7z and hold no ':'")
    if not password:
        raise ValueError("the password is empty")
    if not _encodes(password):
        raise ValueError("the password can't be encoded")
    members = list(members)
    seen: set[str] = set()
    for index, (arcname, source) in enumerate(members):
        if (
            not arcname.isprintable()
            or arcname.casefold() in seen
            or "\\" in arcname
            or ":" in arcname
            or any(part in ("", ".", "..") for part in arcname.split("/"))
        ):
            raise ValueError(f"members[{index}] has a bad arcname")
        if not isinstance(source, bytes) and not (
            isinstance(source, Path) and source.is_file() and not source.is_symlink()
        ):
            raise ValueError(f"members[{index}] is neither bytes nor a file")
        seen.add(arcname.casefold())
    with py7zr.SevenZipFile(
        path, "x", header_encryption=True, password=password
    ) as sealed:
        for arcname, source in members:
            if isinstance(source, bytes):
                sealed.writestr(source, arcname)
            else:
                sealed.write(source, arcname)
    return ArchiveFacts(path.name, path.stat().st_size, table.sha256_file(path))


def _encodes(password: str) -> bool:
    """True when UTF-16-LE can encode the password. The encoding error holds the
    password, so it ends here: a ValueError raised inside its handler, even with
    from None, would still keep it as __context__."""
    try:
        password.encode("utf-16-le")
    except UnicodeEncodeError:
        return False
    return True
