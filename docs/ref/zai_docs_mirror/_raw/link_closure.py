import os, re, io

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
have = set()
targets = set()
link_re = re.compile(r'\(([^)\s]+)\)')
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d != '_raw']
    for fn in filenames:
        if not fn.endswith('.md'):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, root).replace(os.sep, '/')
        have.add(rel[:-3])
        with io.open(full, encoding='utf-8', errors='replace') as f:
            text = f.read()
        for m in link_re.finditer(text):
            t = m.group(1)
            if t.startswith(('http://', 'https://', 'mailto:', '#')):
                if t.startswith('https://docs.z.ai/'):
                    t = t[len('https://docs.z.ai/'):]
                else:
                    continue
            t = t.split('#')[0].split('?')[0]
            if not t:
                continue
            if t.endswith('.md'):
                t = t[:-3]
            elif t.endswith(('.json', '.png', '.jpg', '.gif', '.svg', '.webp', '.ico', '.zip', '.mp4')):
                continue
            if t.startswith('/'):
                t = t[1:]
            else:
                base = os.path.dirname(rel)
                t = os.path.normpath(os.path.join(base, t)).replace(os.sep, '/')
            if t and not t.endswith(('.txt', '.xml')):
                targets.add(t)

unfetched = sorted(t for t in targets if t not in have)
out = os.path.join(root, '_raw', 'link_closure.txt')
with io.open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(unfetched) if unfetched else '(no unfetched internal targets)')
print('pages:', len(have), 'unique internal targets:', len(targets), 'unfetched:', len(unfetched))
for u in unfetched:
    print('MISSING:', u)
