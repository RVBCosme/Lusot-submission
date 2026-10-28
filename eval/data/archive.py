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

    Each member is an arcname with its bytes, or with the path of a file to copy in.
    ValueError is raised, before anything is created, when:
    - the path isn't absolute, or its name doesn't end in .7z or holds ":", as an NTFS
      stream's name does (S-R8, S-R2)
    - the password is empty (C206)
    - an arcname is empty, absolute or repeated, holds a backslash or ":" (C:x and C:/x
      name a drive), or has an empty, "." or ".." part. py7zr would store some of these
      under another name, or refuse them only once the file exists, so an arcname that
      passes is stored exactly as given. The message gives the member's place in
      members, never its name.

    An existing file raises FileExistsError and keeps its bytes. An error while writing
    still closes the file, with the members written so far. That is a partial output,
    which Rene deletes before a rerun (§5.5).
    """
    if not path.is_absolute():
        raise ValueError("the archive path isn't absolute")
    if not path.name.endswith(".7z") or ":" in path.name:
        raise ValueError("the archive name must end in .7z and hold no ':'")
    if not password:
        raise ValueError("the password is empty")
    seen: set[str] = set()
    for index, (arcname, _) in enumerate(members):
        if (
            arcname in seen
            or "\\" in arcname
            or ":" in arcname
            or any(part in ("", ".", "..") for part in arcname.split("/"))
        ):
            raise ValueError(f"members[{index}] has a bad arcname")
        seen.add(arcname)
    with py7zr.SevenZipFile(
        path, "x", header_encryption=True, password=password
    ) as sealed:
        for arcname, source in members:
            if isinstance(source, bytes):
                sealed.writestr(source, arcname)
            else:
                sealed.write(source, arcname)
    return ArchiveFacts(path.name, path.stat().st_size, table.sha256_file(path))
