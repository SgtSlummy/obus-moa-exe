import psutil, os

matches = []
for p in psutil.process_iter(['name','cmdline','exe','cwd']):
    try:
        info = p.info
        name = (info.get('name') or '').lower()
        cmdline = ' '.join(info.get('cmdline') or [])
        if name and ('oz' in name or 'pegasus' in cmdline.lower()):
            matches.append(info)
        elif cmdline and ('oz' in cmdline.lower() or 'pegasus' in cmdline.lower()):
            matches.append(info)
    except Exception as e:
        print(f"  err {p.pid}: {e}")

print(f"OZ/Pegasus candidate processes: {len(matches)}")
for m in matches:
    print("---")
    print("  name:", m.get('name'))
    print("  pid:", m.pid if hasattr(m,'pid') else '?')
    print("  exe:", m.get('exe'))
    print("  cwd:", m.get('cwd'))
    print("  cmdline:", m.get('cmdline'))
