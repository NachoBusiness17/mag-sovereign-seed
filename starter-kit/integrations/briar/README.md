# Briar integration (the dead drop)

The kit's transport plug for moving envelopes between kit instances with
no server, no account, and no live internet requirement: phone-to-desktop,
kit-to-kit, kit-to-a-spare-in-a-drawer. Briar is the first wire. The law
below is the durable part - it outlives any wire, including this one.

## What Briar is (state checked 2026-10-04)

- Censorship-resistant peer-to-peer messaging: end-to-end encrypted, no
  central server, messages stored only on your own devices. It syncs over
  Tor when online, over Bluetooth or Wi-Fi when the internet is down, via
  memory cards in a total outage, and through a self-hosted Briar Mailbox
  when contacts are never online at the same time.
- Android app at 1.5.21 (September 30, 2026). The project announced
  MAINTENANCE MODE on July 9, 2026: active, but "only making essential
  security updates and bugfixes". Releases do still land - 1.5.21 shipped
  two months into maintenance mode.
- Their own named, unsolved problems: high battery use and unreliable
  background operation on Android; no account backup; no file
  attachments; difficult contact-adding UX. Plan around all four.
- Desktop is a separate beta app (briar-desktop, 0.6.6-beta, Aug 2026,
  Linux and Windows). Its builds EXPIRE - validity currently extended to
  February 2027, extended roughly every six months. A desktop dead-drop
  node must update the app twice a year or the wire goes dark.
- The scriptable surface is briar-headless: a jar running the peer with
  a REST API at 127.0.0.1:7000, bearer token in ~/.briar/auth_token.
  List contacts, add contacts by exchanged links, send and receive
  message text, post blog entries, and stream events over a websocket.
  Needs a JRE (Java 8+). That jar is the only moving part the kit talks
  to; the kit itself stays stdlib-only.

## Honest verdict

RIGHT WIRE when the threat model includes censorship or metadata
surveillance, or when the network is down but peers are nearby. In those
worlds Briar is the only wire on this page that works at all - Bluetooth
and LAN sync need zero infrastructure.

WRONG WIRE for bulk profile sync. No attachments means every payload
rides message text; Android delivery is only as reliable as the app's
background life; the desktop beta expires every six months; and
maintenance mode freezes the feature surface forever. Use the
alternatives below for the memory tree; use Briar for small envelopes -
receipt digests, wake-ups, queue flushes, one-lane payloads.

The maintenance-mode risk, priced honestly: the project nearly shut down
before reversing into maintenance mode; releases continue but features
do not. So the dead-drop law below assumes ANY wire can die mid-queue.
Briar is a wire, never infrastructure.

## THE DEAD-DROP LAW

The inbox law (SUBSYSTEMS.md organ 2, PROTOCOLS.md append-only) extended
across a gap in time and space. Four clauses:

1. OFFLINE QUEUE. Every outbound item is appended to a local outbox
   file BEFORE any transport is touched. A send is complete when it is
   queued, not when it is delivered. No session ever blocks, waits, or
   fails on transport absence - the queue is the buffer and its depth is
   free information (run stats read it like a fuel gauge).

2. APPEND-ONLY, ALLOW FAILURES. The outbox and the far-side inbox are
   append-only logs. A failed send attempt does not abort anything: the
   failure is appended as the next entry (timestamp, wire name, error)
   and the item stays pending. A failed apply on the receiving side is
   recorded the same way. Failures are data; the log replays exactly
   what happened, including every dropped wire.

3. EVENTUAL SYNC. Delivery is assumed slow, duplicated, reordered, and
   arbitrarily delayed - possibly forever. Therefore: every envelope
   carries a monotonic per-sender sequence id and a content hash;
   receivers apply idempotently (an id already present is skipped, not
   re-applied); a gap in the sequence is a census finding, not an error;
   and reconciliation is pull-based on reconnect (the receiver asks for
   everything after its high-water mark). Nothing is ever deleted to
   "fix" a mismatch - a corrective envelope is appended.

4. THE WIRE IS REPLACEABLE. The envelope is a transport-agnostic JSON
   object; the wire is a function from (envelope) to (delivered). Briar
   message text today, a git commit tomorrow, a USB tarball the day
   after. If a wire dies mid-queue (Briar maintenance mode, an expired
   desktop beta, a broken tailnet), the outbox drains onto the next
   wire without changing one byte of envelope. A wire you cannot swap
   is not a wire, it is a hostage.

Envelope shape (v1):

    {"v": 1, "id": "<node>-<seq>", "ts": "<iso8601>", "lane": "<name>",
     "sha256": "<hex of body>", "body": <json or base64 text>}

Bodies stay small (single-digit KB); anything bigger is chunked into
numbered parts sharing the id root, and a gap in part numbers is a
census finding.

NEVER-LAW: secrets never ride a dead drop. .env contents, API keys,
tokens - never in an envelope, on any wire, under any pressure. The
dead drop carries kit data (receipts, memory rows, wake-ups) only.
Keys are installed on each node by hand, the same way they were on the
machine that first earned them.

## Wiring it (briar-headless)

    # desktop side: build or fetch the jar, then
    java -jar briar-headless.jar          # first run: pick nickname+password
    cat ~/.briar/auth_token               # the bearer token

    # pair two nodes (once per pair, links exchanged over any channel):
    curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:7000/v1/contacts/add/link
    curl -X POST -H "Authorization: Bearer $TOKEN" \
         -d '{"link":"<their link>","alias":"phone"}' \
         http://127.0.0.1:7000/v1/contacts/add/pending

    # the kit's whole wire is one stdlib call:
    #   urllib POST /v1/messages/<contactId> with the envelope as "text"
    # and one poll (or the /v1/ws websocket) reading inbound envelopes
    # into the local inbox. No pip, no SDK, no wrapper process.

On Android, the Briar app itself is the peer; the Termux seat and the
Briar app cannot read each other's private storage, so the phone-side
bridge is a manual paste of the envelope text (or a share-intent into
Termux) - acceptable because envelopes are small and few. The heavy
phone wire is Syncthing or git, below.

## Alternatives (ranked for the actual job: profile sync)

1. git-over-tailnet (or git over LAN ssh). The kit is already a git
   repo and its own law says inheritance is commits. A bare repo on any
   node (or a private tailnet host) gives whole-tree sync, content
   addressing, merge, and history in one tool the kit already requires.
   This is the default spine; Briar is the auxiliary lane.
2. Syncthing. Continuous bidirectional file sync, no central server,
   TLS with device-ID pairing, mature and foundation-backed. Syncs the
   whole memory/ tree unattended. Android only via the community fork
   (Syncthing-Fork; the official Android app was discontinued December
   2024) - fine for a personal mesh, know it before you lean on it.
3. Manual bundle. Tar the memory dir plus the inbox, move it by USB,
   SD card, or whatever physically connects the machines. Zero
   dependencies, zero attack surface, works when everything else is
   down. Briar's own memory-card sync is this same law wearing a nicer
   coat. The floor you can always reach.
4. Briar. Best when the network is hostile or absent-but-proximate.
   Envelopes only, never the bulk tree.

The recommended shape: git as the spine, Syncthing where unattended
file sync beats manual pulls, manual bundle as the guaranteed floor,
Briar where the threat model demands it. All four carry the same
envelopes under the same law.
