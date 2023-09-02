from pycobj.memory.filememory import FileMemoryAccessor
from pycobj.typespace import TypeSpace


ts = TypeSpace("../spm-decomp/ctx.h")
ram = FileMemoryAccessor(("../evt-disassembler/ram.raw", 0x8000_0000))

wpad_work_t = ts.get("WpadWork")
wpad_work = wpad_work_t.make_object(ram, 0x8052_8F48)
print(wpad_work)
print(wpad_work.flags)
print(wpad_work.unknown_0x4[2])

map_work_t = ts.get("MapWork")
map_work = map_work_t.make_object(ram, 0x8050_BC20)
print(map_work.paperAmbColor.g.value)
map_work.paperAmbColor.g.value += 1

evt_work_t = ts.get("EvtWork")
evt_work = evt_work_t.make_object(ram, 0x8050_c990)
print(evt_work.entries[1].id)

ram.save()
