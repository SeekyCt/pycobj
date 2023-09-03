from time import sleep

import dolphin_memory_engine as dme

from .memoryaccessor import Addr, AddrException, MemoryAccessor


class DolphinMemoryAccessor(MemoryAccessor):
    """MemoryAccessor implementation for a GC/Wii game in Dolphin Emulator"""

    def __init__(self):
        dme.hook()
        if not dme.is_hooked():
            print("DME not ready yet, sleeping")
            while not dme.is_hooked():
                sleep(0.01) # 10ms
                dme.hook()        

    def _validate_addr(self, addr: Addr):
        return (
            0x8000_0000 <= addr <= 0x817f_ffff or
            0x9000_0000 <= addr <= 0x93FFFFFF
        )

    def read(self, addr: Addr, length: int) -> bytes:
        if not self._validate_addr(addr):
            raise AddrException(f"Read from unknown address 0x{addr:x}")
        return dme.read_bytes(addr, length)

    def write(self, addr: Addr, data: bytes):
        if not self._validate_addr(addr):
            raise AddrException(f"Wrote to unknown address 0x{addr:x}")
        dme.write_bytes(addr, data)
