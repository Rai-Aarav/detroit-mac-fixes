#!/usr/bin/env python3
"""Detroit: Become Human (Steam, Windows build) - make the two startup GPU warning dialogs
("Your graphics card is not officially supported..." and the driver-version warning) behave as if OK
was clicked, without showing them.

Under CrossOver/MoltenVK these dialogs appear on every launch. In our testing, relaunching with an
existing ShaderCache closed the game silently ~30 s after the dialog; with the dialogs auto-answered,
relaunches start normally from the saved caches.

Usage: python3 popup_auto_ok.py "/path/to/Detroit Become Human/DetroitBecomeHuman.exe"
A backup is written next to the exe first. The script refuses to patch if the expected bytes differ.
"""
import shutil, struct, sys, os

def text_section(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    nsec = struct.unpack_from('<H', d, pe + 6)[0]
    optsz = struct.unpack_from('<H', d, pe + 20)[0]
    base = struct.unpack_from('<Q', d, pe + 24 + 24)[0]
    so = pe + 24 + optsz
    for i in range(nsec):
        o = so + 40 * i
        if d[o:o + 5] == b'.text':
            vs, va, rs, ro = struct.unpack_from('<IIII', d, o + 8)
            return base, va, ro
    raise SystemExit('no .text section')

def main(p):
    d = bytearray(open(p, 'rb').read())
    base, va, ro = text_section(d)
    off = lambda v: v - base - va + ro
    # call qword ptr [MessageBoxW] at these two sites -> mov eax, 1 (IDOK) ; nop
    sites = [0x140662804, 0x140662857]
    for v in sites:
        cur = bytes(d[off(v):off(v) + 6])
        if cur == bytes.fromhex('b80100000090'):
            print(hex(v), 'already patched'); continue
        if cur[:2] != b'\xff\x15':
            raise SystemExit(f'unexpected bytes at {hex(v)}: {cur.hex()} (different game version?)')
    bk = p + '.backup-before-popup-patch'
    if not os.path.exists(bk):
        shutil.copy2(p, bk)
    for v in sites:
        d[off(v):off(v) + 6] = bytes.fromhex('b80100000090')
    open(p, 'wb').write(d)
    print('patched; backup at', bk)

if __name__ == '__main__':
    main(sys.argv[1])
