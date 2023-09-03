from pycobj.memory.filememory import FileMemoryAccessor
from pycobj.typespace import TypeSpace


ts = TypeSpace("../spm-decomp/ctx.h")
ram = FileMemoryAccessor(("../evt-disassembler/ram.raw", 0x8000_0000))

wpad_wp_t = ts.get_from_var("wpadmgr_wp")
wpad_wp = wpad_wp_t.make_object(ram, 0x805a_e198)
wpad_work = wpad_wp[0]
print(wpad_work)
print(wpad_work.flags)
print(wpad_work.unknown_0x4[2])

map_work_t = ts.get("MapWork")
map_work = map_work_t.make_object(ram, 0x8050_bc20)
print(map_work.paperAmbColor.g.value)
map_work.paperAmbColor.g.value += 1

evt_work_t = ts.get("EvtWork")
evt_work = evt_work_t.make_object(ram, 0x8050_c990)
print(evt_work.entries[1].id)

union_t = ts.get("TestUnion")
union = union_t.make_object(ram, 0x8000_0000)
print(hex(union.asInt.value), hex(union.asChar.value))

first_rel_t = ts.get_from_var("firstRel")
first_rel = first_rel_t.make_object(ram, 0x8000_30c8)
print(first_rel)
relf = first_rel[0]
print(relf.prolog[0])

ram.save()
