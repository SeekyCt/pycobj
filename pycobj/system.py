from dataclasses import dataclass

from .typespace import TypeSpace
from .memory.memoryaccessor import MemoryAccessor


@dataclass
class System:
    """Container for a single system's types and memory"""

    memory: MemoryAccessor
    typespace: TypeSpace
