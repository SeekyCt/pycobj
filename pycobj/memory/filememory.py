from dataclasses import dataclass
from typing import List, Tuple

from .memoryaccessor import Addr, AddrException, MemoryAccessor


# Path, base address
MemoryFileDef = Tuple[str, int]


@dataclass
class MemoryFile:
    """Internal handling of an addressed file"""

    path: str
    base_addr: int
    data: bytearray

    def __contains__(self, addr: Addr):
        return self.base_addr <= addr < self.base_addr + len(self.data)

    def read(self, addr: Addr, length: int) -> bytes:
        offs = addr - self.base_addr
        return bytes(self.data[offs : offs + length])

    def write(self, addr: Addr, data: bytes):
        offs = addr - self.base_addr
        self.data[offs : offs + len(data)] = data


class FileMemoryAccessor(MemoryAccessor):
    """MemoryAccessor implementation for a RAM dump / regular binary file"""

    files: List[MemoryFile]

    def __init__(self, *files: MemoryFileDef):
        self.files = []
        for path, base_addr in files:
            with open(path, "rb") as f:
                dat = f.read()
            self.files.append(MemoryFile(path, base_addr, bytearray(dat)))
        # TODO: check overlap

    def read(self, addr: Addr, length: int) -> bytes:
        for file in self.files:
            if addr in file:
                return file.read(addr, length)
        raise AddrException(f"Read from unknown address 0x{addr:x}")

    def write(self, addr: Addr, data: bytes):
        for file in self.files:
            if addr in file:
                return file.write(addr, data)
        raise AddrException(f"Wrote to unknown address 0x{addr:x}")

    def save(self):
        for file in self.files:
            with open(file.path, 'wb') as f:
                f.write(file.data)
