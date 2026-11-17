#!/usr/bin/env python3
"""Detroit: Become Human (Steam, Windows build) - crash guard for the "park" crash under CrossOver/MoltenVK.

Symptom: in Kara's park scene (after the opening credits) the picture freezes, audio keeps playing, then the
game crashes. Every minidump we got (3/3) faults at DetroitBecomeHuman.exe+0xc732a0, inside a function
(0x140c73100) that fills a width x height float grid from two float rectangles. Under Wine/MoltenVK it
receives non-finite/garbage rectangle coordinates; cvttss2si turns them into INT_MIN-style row/column
indices and the loop reads far outside the grid. The "freeze" is the crash reporter writing the dump.

This patch adds two bounds checks in a code cave (in the .text section's file slack):
  * skip the call when the start row is negative;
  * skip a row when its index range is negative or beyond width*height.
Where the bad coordinates come from is still unknown (likely upstream of this function); this only stops
the crash. With it applied we played through the park scene that crashed 3/3 before.

Usage: python3 rect_guard.py "/path/to/Detroit Become Human/DetroitBecomeHuman.exe"
Refuses to patch if the expected bytes differ. A backup is written next to the exe first.
"""
import struct,sys,shutil,os
p=sys.argv[1]; d=bytearray(open(p,'rb').read())
pe=struct.unpack_from('<I',d,0x3c)[0]; nsec=struct.unpack_from('<H',d,pe+6)[0]; optsz=struct.unpack_from('<H',d,pe+20)[0]
base=struct.unpack_from('<Q',d,pe+24+24)[0]; so=pe+24+optsz
for i in range(nsec):
    o=so+40*i
    if d[o:o+5]==b'.text': hdr=o; vs,va,rs,ro=struct.unpack_from('<IIII',d,o+8)
def off(v): return v-base-va+ro
def rel(frm_end,to): return struct.pack('<i',to-frm_end)
HA=0x140c731a4; HB=0x140c73225
assert bytes(d[off(HA):off(HA)+9])==bytes.fromhex('443bd80f8df2010000'), d[off(HA):off(HA)+9].hex()
assert bytes(d[off(HB):off(HB)+9])==bytes.fromhex('493bc80f8f53010000'), d[off(HB):off(HB)+9].hex()
CA=base+va+0x18b3870; CB=CA+0x40
assert CB+0x40 < base+va+rs and not any(d[off(CA):off(CA)+0x80]), 'cave not free'
def asm(start,parts):
    out=b''
    for pt in parts:
        if isinstance(pt,tuple):
            op,tgt=pt; cur=start+len(out)+len(op)+4; out+=op+rel(cur,tgt)
        else: out+=pt
    return out
BADA=CA+0x28
caveA=asm(CA,[bytes.fromhex('443bd8'),(bytes.fromhex('0f8d'),0x140c7339f),bytes.fromhex('4585db'),(bytes.fromhex('0f88'),BADA),(b'\xe9',0x140c731ad)])
assert len(caveA)<=0x28
caveA=caveA.ljust(0x28,b'\xcc')+asm(BADA,[bytes.fromhex('0f283c24'),(b'\xe9',0x140c73562)])
SKIP=0x140c73381
caveB=asm(CB,[bytes.fromhex('493bc8'),(bytes.fromhex('0f8f'),SKIP),bytes.fromhex('4885c9'),(bytes.fromhex('0f88'),SKIP),
              bytes.fromhex('418b4208'),bytes.fromhex('410faf420c'),bytes.fromhex('4898'),bytes.fromhex('4c3bc0'),(bytes.fromhex('0f8d'),SKIP),(b'\xe9',0x140c7322e)])
assert len(caveA)<=0x40 and len(caveB)<=0x40
bk=p+'.backup-before-rect-guard'
if not os.path.exists(bk): shutil.copy2(p,bk)
d[off(CA):off(CA)+len(caveA)]=caveA; d[off(CB):off(CB)+len(caveB)]=caveB
d[off(HA):off(HA)+9]=asm(HA,[(b'\xe9',CA)])+b'\x90'*4
d[off(HB):off(HB)+9]=asm(HB,[(b'\xe9',CB)])+b'\x90'*4
struct.pack_into('<I',d,hdr+8,rs)   # VirtualSize covers the cave
open(p,'wb').write(d); print('patched; caveA',hex(CA),'caveB',hex(CB))
