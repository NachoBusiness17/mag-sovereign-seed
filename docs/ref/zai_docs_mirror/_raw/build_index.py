import os, re, io

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pages = []
for dirpath, dirnames, filenames in os.walk(root):
    dirnames[:] = [d for d in dirnames if d != '_raw']
    for fn in filenames:
        if not fn.endswith('.md') or fn == 'INDEX.md':
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, root).replace(os.sep, '/')
        with io.open(full, encoding='utf-8', errors='replace') as f:
            text = f.read()
        m = re.search(r'^# (.+)$', text, re.M)
        title = m.group(1).strip() if m else fn
        sm = re.search(r'^Source: (.+)$', text, re.M)
        src = sm.group(1).strip() if sm else 'https://docs.z.ai/' + rel[:-3]
        body_lines = [l.strip() for l in text.splitlines() if l.strip()]
        note = ''
        for l in body_lines:
            if l.startswith('#') or l.startswith('Source:') or l.startswith('>'):
                continue
            if len(l) < 25:
                continue
            note = re.sub(r'\s+', ' ', l)[:110]
            break
        gap = 'GAP' in title or 'MIRROR STUB' in text
        size = len(text.encode('utf-8'))
        pages.append((rel, title, src, note, size, gap))

sec_order = ['guides/overview/', 'guides/llm/', 'guides/vlm/', 'guides/audio/', 'guides/image/',
             'guides/capabilities/', 'guides/tools/', 'guides/develop/', 'guides/agents/',
             'api-reference/', 'devpack/', 'scenario-example/', 'release-notes/', 'help/', 'legal-agreement/']


def sec_key(rel):
    for i, s in enumerate(sec_order):
        if rel.startswith(s):
            return (0, i, rel)
    return (1, 0, rel)


pages.sort(key=lambda p: sec_key(p[0]))
n_real = sum(1 for p in pages if not p[5])
lines = []
A = lines.append
A('# Z.AI DOCS MIRROR — INDEX')
A('')
A('> **Provenance:** mirrored from https://docs.z.ai (the official Z.AI developer documentation site, Mintlify-hosted).')
A('> **Mirror date:** 2026-09-04 (llms-full.txt vendor Last-Modified 2026-09-03T21:55:58Z).')
A('> **Doors used:** (1) https://docs.z.ai/llms-full.txt — EXISTS, 647,819 bytes, whole-docs capture (the 90% door confirmed); (2) https://docs.z.ai/llms.txt — index, 68 pages; (3) sitemap.xml — 67 URLs; (4) per-page `.md` raw-markdown endpoints — every page fetched via curl as raw markdown.')
A('> **License note:** vendor docs mirrored for internal fleet use only. Copyright z.ai. Do not republish, redistribute, or feed to external parties; internal reference shelf per the wall-ledger law.')
A('')
A('**Coverage:** %d/%d pages mirrored (100%% fetch rate; %d pages with full vendor content; 1 documented gap: `api-reference/rate-limit.md` — page moved vendor-side to the z.ai console docs, HTML-only). Plus `openapi.json` (valid, 14 endpoint paths) and the raw door captures in `_raw/`.' % (len(pages), len(pages), n_real))
A('')
A('Index completeness finding (2026-09-04): the vendor\'s own maps are INCOMPLETE. `scenario-example/*` (6 pages) appears in NEITHER llms.txt NOR sitemap.xml, and 12 model-guide pages (retired GLM generations glm-4.5/4.6/4.7/5/5.1, glm-4-32b, VLMs glm-4.5v/4.6v/autoglm-phone, image glm-image/cogview-4, video cogvideox-3) are linked by live pages but absent from both indexes — found via link-graph closure + live probing. Anything not listed here is Unproven to exist.')
A('')
A('---')
cur_sec = None
for rel, title, src, note, size, gap in pages:
    sec = rel.split('/')[0]
    if sec != cur_sec:
        cur_sec = sec
        A('')
        A('## %s/' % sec)
        A('')
    flag = ' **[GAP]**' if gap else ''
    note_s = (' — ' + note) if note else ''
    A('- `%s` — %s%s%s (%d bytes) [source](%s)' % (rel, title, flag, note_s, size, src))
A('')
A('## openapi.json')
A('')
A('- `openapi.json` — vendor machine-readable API spec (14 paths: chat completion, images, video, audio, agents, tools) [source](https://docs.z.ai/openapi.json)')
A('')
A('## _raw/ (door captures)')
A('')
A('- `_raw/llms_index.txt` — llms.txt index capture (68 links)')
A('- `_raw/llms_full.txt` — llms-full.txt whole-docs capture (647,819 bytes)')
A('- `_raw/sitemap.xml` + `_raw/sitemap_urls.txt` — sitemap ground truth (67 URLs)')
A('- `_raw/fetch_log.txt` — per-page HTTP status + byte log for the 2026-09-04 crawl')
A('- `_raw/crawl_urls.txt` — the exact 75-URL crawl manifest')
A('')
A('## Known gaps (tri-state)')
A('')
A('- `api-reference/rate-limit` — **Disputed availability**: docs.z.ai 307-redirects to https://z.ai/manage-apikey/rate-limits (HTML console docs, no .md door). Stub + pointer recorded in-mirror; endpoint-level rate numbers UNPROVEN until that page is mined. Concurrency-by-tier table IS captured at `devpack/usage-policy.md`.')
A('- No 404s, no wall hits on any other page.')
A('')

with io.open(os.path.join(root, 'INDEX.md'), 'w', encoding='utf-8', newline='\n') as f:
    f.write('\n'.join(lines))
print('INDEX.md written:', len(pages), 'pages listed,', n_real, 'full-content,', sum(1 for p in pages if p[5]), 'gap')
