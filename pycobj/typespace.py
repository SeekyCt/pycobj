from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional, Tuple

from pycparser import c_ast as ca
from m2c.c_types import (
    CType,
    Struct,
    StructField,
    TypeMap,
    build_typemap,
    is_struct_type,
    parse_struct,
    primitive_size,
    resolve_typedefs,
)

from .memory.memoryaccessor import Addr, MemoryAccessor


TypeName = str


class TypeException(Exception):
    """Error finding a type or its property"""

    pass


class TypeSpace:
    """A collection of types for a program"""

    # M2C parsing of C
    typemap: TypeMap

    # Pool of pycobj type objects
    name_pool: Dict[TypeName, "Type"]
    ctype_pool: Dict[CType, "Type"]

    def __init__(self, *contexts: str):
        self.typemap = build_typemap([Path(path) for path in contexts], False)
        self.name_pool = {}
        self.ctype_pool = {}

    def _add(self, ctype: CType, name: Optional[str] = None):
        """Adds a new type to the type pool"""

        # Ensure the type is in the ctype pool
        if ctype in self.ctype_pool:
            t = self.ctype_pool[ctype]
        else:
            t = Type.new(self, ctype, name)
            self.ctype_pool[ctype] = t

        # Add to name pool if possible
        if name is not None:
            self.name_pool[name] = t

    def get(self, name: TypeName) -> "Type":
        """Gets the Type for a name"""

        if name not in self.name_pool:
            # TODO: support non-typedef'd?
            ctype = self.typemap.typedefs.get(name)
            if ctype is None:
                raise TypeException(f"Type {name} not found")
            ctype = resolve_typedefs(ctype, self.typemap)

            self._add(ctype, name)

        return self.name_pool[name]

    def get_from_ctype(self, ctype: CType) -> "Type":
        """Gets the Type for a ctype"""

        ctype = resolve_typedefs(ctype, self.typemap)
        if ctype not in self.ctype_pool:
            self._add(ctype)

        return self.ctype_pool[ctype]


class Type(ABC):
    """Pycobj wrapper for a type"""

    typespace: TypeSpace
    ctype: CType
    name: Optional[str]

    def __str__(self):
        return f"{self.__class__.__name__}({self.name})"

    def __init__(self, typespace: TypeSpace, ctype: CType, name: Optional[str]):
        self.typespace = typespace
        self.ctype = ctype
        self.name = name

    @classmethod
    def new(cls, typespace: TypeSpace, ctype: CType, name: Optional[str]):
        if isinstance(ctype, ca.TypeDecl):
            if isinstance(ctype.type, ca.Struct):
                ret_cls = StructType
            elif isinstance(ctype.type, ca.IdentifierType):
                ret_cls = IntegerType
            else:
                assert 0, ctype
        else:
            assert 0, ctype

        return ret_cls(typespace, ctype, name)

    @abstractmethod
    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "Object":
        raise NotImplementedError


class IntegerType(Type):
    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "IntegerObject":
        return IntegerObject(memory, self, addr)


class StructType(Type):
    struct: Struct
    fields: dict[str, Tuple[int, StructField]]

    def __init__(self, typespace: TypeSpace, ctype: CType, name: Optional[str]):
        super().__init__(typespace, ctype, name)

        assert is_struct_type(self.ctype, self.typespace.typemap)

        self.struct = parse_struct(self.ctype.type, self.typespace.typemap)
        self.fields = {}
        for offset, fields in self.struct.fields.items():
            for field in fields:
                self.fields[field.name] = (offset, field)

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "StructUnionObject":
        return StructUnionObject(memory, self, addr)


class Object(ABC):
    """Instance of a type in a system"""

    _memory: MemoryAccessor
    _t: Type
    _addr: Addr

    def __init__(self, memory: MemoryAccessor, t: Type, addr: Addr):
        self._memory = memory
        self._t = t
        self._addr = addr


class IntegerObject(Object):
    """Access an object as an integer"""

    _size: int
    _signed: bool

    # TODO: don't assume endian

    def __init__(self, memory: MemoryAccessor, t: Type, addr: Addr):
        super().__init__(memory, t, addr)
        self._size = primitive_size(self._t.ctype.type)
        self._signed = "signed" in self._t.ctype.type.names

    def __repr__(self) -> str:
        return f"IntegerObject({' '.join(self._t.ctype.type.names)}, 0x{self._addr:x}, {self.value})"

    @property
    def value(self) -> int:
        data = self._memory.read(self._addr, self._size)
        return int.from_bytes(data, "big", signed=self._signed)

    @value.setter
    def value(self, value: int):
        data = int.to_bytes(value, self._size, "big", signed=self._signed)
        self._memory.write(self._addr, data)


class StructUnionObject(Object):
    """Access an object as a struct or union"""

    # TODO: generic object?
    _t: StructType

    def __repr__(self) -> str:
        return f"StructUnionObject({self._t.name}, 0x{self._addr:x})"

    def __getattr__(self, name: str) -> Object:
        if name not in self._t.fields:
            raise TypeException(f"{self} has no field {name}")
        offset, field = self._t.fields[name]
        t = self._t.typespace.get_from_ctype(field.type)
        return t.make_object(self._memory, self._addr + offset)
