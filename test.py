from pycobj.memory.filememory import FileMemoryAccessor
from pycobj.object import Object
from pycobj.system import System
from pycobj.typespace import TypeSpace


ts = TypeSpace("../spm-decomp/ctx.h")
ram = FileMemoryAccessor(("../evt-disassembler/ram.raw", 0x8000_0000))
system = System(ram, ts)

wpad_work_t = ts.get("WpadWork")
wpad_work = Object.new(system, wpad_work_t, 0x8052_8f48)
print(wpad_work)
print(wpad_work.flags)

map_work_t = ts.get("MapWork")
map_work = Object.new(system, map_work_t, 0x8050_bc20)
print(map_work.paperAmbColor.g.value)
map_work.paperAmbColor.g.value += 1

ram.save()
