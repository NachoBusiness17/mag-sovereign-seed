# Android integration (the phone as a body)

The kit runs on Android two ways; both start with Termux (the terminal
emulator - install from F-Droid, the Play Store build is stale).

## The light way (Termux + a small local model)

```bash
# in Termux:
pkg update && pkg install git python
git clone <this repo> starter-kit && cd starter-kit
bash setup/install.sh
python tools/kit_doctor.py
python tools/profile_boot.py --memory ~/storage/shared/starter-kit-memory
```

Notes for the phone:
- Point --memory at shared storage (termux-setup-storage first) so the
  profile survives Termux reinstalls and syncs to your desktop copy.
- Local models: Termux runs CPU-tier models (2-4B) via ollama's Termux
  build if you want offline lanes; otherwise lanes ride your free-tier
  keys from .env. The phone is a fine JANITOR seat - mining, receipts,
  light lanes - while the heavy seats live elsewhere.
- Battery law: lanes on a phone run on charge + wifi only (cron in
  Termux: pkg install cronie termux-services).

## The full way (a GUI emulator seat)

If you develop on a desktop, the kit's Android surface is also testable
in an emulator: create an AVD, install Termux or your agent app, and
repeat the light way. Useful when you want the agent reachable as a
PHONE - notifications, the party line (murmur client from F-Droid),
photos in, voice out.

## What the phone body is FOR

Presence: the murmur room from your pocket, the day's receipts read to
you, the profile growing from wherever you are. The heavy math stays on
the boxes; the phone is the spore that travels.
