from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Generic, Optional, Tuple, TypeVar

from pycparser import c_ast as ca
from m2c.c_types import (
    CType,
    Struct,
    StructField,
    TypeMap,
    build_typemap,
    is_struct_type,
    parse_constant_int,
    parse_struct,
    primitive_size,
    resolve_typedefs,
)

from .memory.memoryaccessor import Addr, MemoryAccessor


TypeName = str
TypeType = TypeVar("TypeType", bound="Type")
CTypeType = TypeVar("CTypeType", bound=CType)


class TypeException(Exception):
    """Error finding a type or its property"""

    pass


class TypeSpace:
    """A collection of types for a program"""

    # M2C parsing of types in context
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

            self._add(ctype, name)

        return self.name_pool[name]

    def get_from_ctype(self, ctype: CType) -> "Type":
        """Gets the Type for a ctype"""

        ctype = resolve_typedefs(ctype, self.typemap)
        if ctype not in self.ctype_pool:
            self._add(ctype)

        return self.ctype_pool[ctype]

    def get_from_var(self, name: str) -> "Type":
        """Gets the type from a global variable"""

        ctype = self.typemap.var_types.get(name)
        if ctype is None:
            raise TypeException(f"Variable {name} not found")
        ctype = resolve_typedefs(ctype, self.typemap)
        if ctype not in self.ctype_pool:
            self._add(ctype)
        
        return self.ctype_pool[ctype]


class Type(ABC, Generic[CTypeType]):
    """Pycobj wrapper for a type"""

    typespace: TypeSpace
    ctype: CTypeType
    name: Optional[str]
    size: int

    def __str__(self):
        return f"{self.__class__.__name__}({self.name})"

    def __init__(
        self, typespace: TypeSpace, ctype: CTypeType, name: Optional[str], size: int
    ):
        self.typespace = typespace
        self.ctype = ctype
        self.name = name
        self.size = size

    @classmethod
    def new(
        cls, typespace: TypeSpace, ctype: CTypeType, name: Optional[str]
    ) -> "Type[CTypeType]":
        if isinstance(ctype, ca.TypeDecl):
            if isinstance(ctype.type, (ca.Struct, ca.Union)):
                ret_cls = StructUnionType
            elif isinstance(ctype.type, ca.IdentifierType):
                ret_cls = IntegerType
            else:
                raise NotImplementedError(type(ctype.type))
        elif isinstance(ctype, ca.ArrayDecl):
            ret_cls = ArrayType
        elif isinstance(ctype, ca.PtrDecl):
            ret_cls = PointerType
        elif isinstance(ctype, ca.FuncDecl):
            ret_cls = FunctionType
        else:
            raise NotImplementedError(ctype)

        return ret_cls(typespace, ctype, name) # type: ignore

    @abstractmethod
    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "Object":
        raise NotImplementedError


class IntegerType(Type[ca.TypeDecl]):
    signed: bool

    def __init__(self, typespace: TypeSpace, ctype: ca.TypeDecl, name: Optional[str]):
        size = primitive_size(ctype.type)
        super().__init__(typespace, ctype, name, size)

        self.signed = "signed" in self.ctype.type.names

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "IntegerObject":
        return IntegerObject(self, memory, addr)


class StructUnionType(Type[ca.TypeDecl]):
    fields: dict[str, Tuple[int, StructField]]

    def __init__(self, typespace: TypeSpace, ctype: ca.TypeDecl, name: Optional[str]):
        parsed = parse_struct(ctype.type, typespace.typemap)
        super().__init__(typespace, ctype, name, parsed.size)

        assert is_struct_type(self.ctype, self.typespace.typemap)

        self.fields = {}
        for offset, fields in parsed.fields.items():
            for field in fields:
                self.fields[field.name] = (offset, field)

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "StructUnionObject":
        return StructUnionObject(self, memory, addr)


class ArrayType(Type[ca.ArrayDecl]):
    item_type: Type
    length: int

    def __init__(self, typespace: TypeSpace, ctype: ca.ArrayDecl, name: Optional[str]):
        self.length = parse_constant_int(ctype.dim, typespace.typemap)
        self.item_type = typespace.get_from_ctype(ctype.type)
        super().__init__(typespace, ctype, name, self.length * self.item_type.size)

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "ArrayObject":
        return ArrayObject(self, memory, addr)


class PointerType(Type[ca.PtrDecl]):
    item_type: Type

    def __init__(self, typespace: TypeSpace, ctype: ca.PtrDecl, name: Optional[str]):
        # TODO: unhardcode size
        super().__init__(typespace, ctype, name, 4)
        self.item_type = typespace.get_from_ctype(ctype.type)

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "PointerObject":
        return PointerObject(self, memory, addr)


class FunctionType(Type[ca.FuncDecl]):
    def __init__(self, typespace: TypeSpace, ctype: ca.FuncDecl, name: Optional[str]):
        # TODO: unhardcode size
        super().__init__(typespace, ctype, name, 4)

    def make_object(self, memory: MemoryAccessor, addr: Addr) -> "FunctionObject":
        return FunctionObject(self, memory, addr)


class Object(ABC, Generic[TypeType]):
    """Instance of a type in a system"""

    _t: TypeType
    _memory: MemoryAccessor
    _addr: Addr

    def __init__(self, t: TypeType, memory: MemoryAccessor, addr: Addr):
        self._memory = memory
        self._t = t
        self._addr = addr

    def _extra_repr(self) -> str:
        return ""

    def __repr__(self):
        return f"{self.__class__.__name__}({self._t}@0x{self._addr:x}{self._extra_repr()})"

class IntegerObject(Object[IntegerType]):
    """Access an object as an integer"""

    # TODO: don't assume endian

    @property
    def value(self) -> int:
        data = self._memory.read(self._addr, self._t.size)
        return int.from_bytes(data, "big", signed=self._t.signed)

    @value.setter
    def value(self, value: int):
        data = int.to_bytes(value, self._t.size, "big", signed=self._t.signed)
        self._memory.write(self._addr, data)
    
    def _extra_repr(self) -> Optional[str]:
        return f" = {self.value}"


class StructUnionObject(Object[StructUnionType]):
    """Access an object as a struct or union"""

    def __getattr__(self, name: str) -> Object:
        if name not in self._t.fields:
            raise TypeException(f"{self} has no field {name}")
        offset, field = self._t.fields[name]
        t = self._t.typespace.get_from_ctype(field.type)
        return t.make_object(self._memory, self._addr + offset)


class ArrayObject(Object[ArrayType]):
    def __getitem__(self, idx: int) -> Object:
        offset = idx * self._t.item_type.size
        return self._t.item_type.make_object(self._memory, self._addr + offset)


class PointerObject(Object[PointerType]):
    @property
    def value(self) -> int:
        data = self._memory.read(self._addr, self._t.size)
        return int.from_bytes(data, "big")

    @value.setter
    def value(self, value: int):
        data = int.to_bytes(value, self._t.size, "big")
        self._memory.write(self._addr, data)

    def deref(self) -> Object:
        return self._t.item_type.make_object(self._memory, self.value)

    def __getitem__(self, idx: int) -> Object:
        addr = self.value + idx * self._t.item_type.size
        return self._t.item_type.make_object(self._memory, addr)

    def _extra_repr(self) -> Optional[str]:
        return f" = 0x{self.value:x}"


class FunctionObject(Object[FunctionType]):
    pass
