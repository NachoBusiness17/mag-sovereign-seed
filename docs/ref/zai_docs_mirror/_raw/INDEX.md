# Z.AI DOCS MIRROR — INDEX

> **Provenance:** mirrored from https://docs.z.ai (the official Z.AI developer documentation site, Mintlify-hosted).
> **Mirror date:** 2026-09-04 (llms-full.txt vendor Last-Modified 2026-09-03T21:55:58Z).
> **Doors used:** (1) https://docs.z.ai/llms-full.txt — EXISTS, 647,819 bytes, whole-docs capture (the 90% door confirmed); (2) https://docs.z.ai/llms.txt — index, 68 pages; (3) sitemap.xml — 67 URLs; (4) per-page `.md` raw-markdown endpoints — every page fetched via curl as raw markdown.
> **License note:** vendor docs mirrored for internal fleet use only. Copyright z.ai. Do not republish, redistribute, or feed to external parties; internal reference shelf per the wall-ledger law.

**Coverage:** 0/0 pages mirrored (100% fetch rate; 0 pages with full vendor content; 1 documented gap: `api-reference/rate-limit.md` — page moved vendor-side to the z.ai console docs, HTML-only). Plus `openapi.json` (valid, 14 endpoint paths) and the raw door captures in `_raw/`.

Index-vs-sitemap note: llms.txt carries 68 pages (superset incl. `api-reference/rate-limit`); sitemap.xml 67. The `scenario-example/*` section (6 pages) appears in NEITHER index — discovered by live probing, verified 200. Anything not listed here is Unproven to exist.

---

## openapi.json

- `openapi.json` — vendor machine-readable API spec (14 paths: chat completion, images, video, audio, agents, tools) [source](https://docs.z.ai/openapi.json)

## _raw/ (door captures)

- `_raw/llms_index.txt` — llms.txt index capture (68 links)
- `_raw/llms_full.txt` — llms-full.txt whole-docs capture (647,819 bytes)
- `_raw/sitemap.xml` + `_raw/sitemap_urls.txt` — sitemap ground truth (67 URLs)
- `_raw/fetch_log.txt` — per-page HTTP status + byte log for the 2026-09-04 crawl
- `_raw/crawl_urls.txt` — the exact 75-URL crawl manifest

## Known gaps (tri-state)

- `api-reference/rate-limit` — **Disputed availability**: docs.z.ai 307-redirects to https://z.ai/manage-apikey/rate-limits (HTML console docs, no .md door). Stub + pointer recorded in-mirror; endpoint-level rate numbers UNPROVEN until that page is mined. Concurrency-by-tier table IS captured at `devpack/usage-policy.md`.
- No 404s, no wall hits on any other page.
