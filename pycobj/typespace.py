from enum import Enum, auto
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
    resolve_typedefs,
)


TypeName = str


class TypeCategory(Enum):
    INTEGER = auto()
    STRUCT = auto()
    UNION = auto()
    POINTER = auto()
    ARRAY = auto()


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
            t = Type(self, ctype, name)
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


class Type:
    """Pycobj wrapper for a type"""

    typespace: TypeSpace
    ctype: CType
    name: Optional[str]
    struct: Struct
    fields: dict[str, Tuple[int, StructField]]

    def __init__(self, typespace: TypeSpace, ctype: CType, name: Optional[str]):
        self.typespace = typespace
        self.ctype = ctype
        self.name = name

        # TODO: handle this better (subclass by category?)
        if is_struct_type(self.ctype, self.typespace.typemap):
            self.struct = parse_struct(self.ctype.type, self.typespace.typemap)
            self.fields = {}
            for offset, fields in self.struct.fields.items():
                for field in fields:
                    self.fields[field.name] = (offset, field)

    def __str__(self):
        return f"Type({self.name})"

    def get_category(self) -> TypeCategory:
        if isinstance(self.ctype.type, ca.Struct):
            return TypeCategory.STRUCT
        elif isinstance(self.ctype.type, ca.IdentifierType):
            return TypeCategory.INTEGER
        else:
            raise NotImplementedError(self.ctype)
