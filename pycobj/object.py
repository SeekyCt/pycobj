from abc import ABC
from m2c.c_types import primitive_size

from .memory.memoryaccessor import Addr
from .system import System
from .typespace import Type, TypeCategory, TypeException


class Object(ABC):
    """Instance of a type in a system"""

    _system: System
    _t: Type
    _addr: Addr

    def __init__(self, system: System, t: Type, addr: Addr):
        self._system = system
        self._t = t
        self._addr = addr

    @classmethod
    def new(cls, system: System, t: Type, addr: Addr):
        cat = t.get_category()
        if cat in (TypeCategory.STRUCT, TypeCategory.UNION):
            ret_cls = StructUnionObject
        elif cat == TypeCategory.INTEGER:
            ret_cls = IntegerObject
        else:
            assert 0

        return ret_cls(system, t, addr)


class IntegerObject(Object):
    """Access an object as an integer"""

    _size: int
    _signed: bool

    # TODO: don't assume endian

    def __init__(self, system: System, t: Type, addr: Addr):
        super().__init__(system, t, addr)
        self._size = primitive_size(self._t.ctype.type)
        self._signed = "signed" in self._t.ctype.type.names

    def __repr__(self) -> str:
        return f"IntegerObject({' '.join(self._t.ctype.type.names)}, 0x{self._addr:x}, {self.value})"

    @property
    def value(self) -> int:
        data = self._system.memory.read(self._addr, self._size)
        return int.from_bytes(data, "big", signed=self._signed)

    @value.setter
    def value(self, value: int):
        data = int.to_bytes(value, self._size, "big", signed=self._signed)
        self._system.memory.write(self._addr, data)


class StructUnionObject(Object):
    """Access an object as a struct or union"""

    def __repr__(self) -> str:
        return f"StructUnionObject({self._t.name}, 0x{self._addr:x})"

    def __getattr__(self, name: str) -> Object:
        if name not in self._t.fields:
            raise TypeException(f"{self} has no field {name}")
        offset, field = self._t.fields[name]
        t = self._system.typespace.get_from_ctype(field.type)
        return Object.new(self._system, t, self._addr + offset)
