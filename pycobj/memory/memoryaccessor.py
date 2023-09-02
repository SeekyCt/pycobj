from abc import ABC, abstractmethod


Addr = int


class AddrException(Exception):
    """Address not found"""

    pass


class MemoryAccessor(ABC):
    """Interface for C data"""

    @abstractmethod
    def read(self, addr: Addr, length: int) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, addr: Addr, data: bytes):
        raise NotImplementedError
