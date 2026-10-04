#!/usr/bin/env bash
# starter-kit install helper (Linux/macOS/Termux). Everything is optional
# except git; each step says what it is and why. Headless by design.
set -euo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

step() { echo; echo "== $* =="; }

step "git (version control - the memory is the chain)"
have git && git --version || { echo "install from https://git-scm.com or: apt install git / brew install git"; echo "then make a free account: https://github.com/signup"; }

step "python 3.9+ (the kit is stdlib-only)"
have python3 && python3 --version || echo "apt install python3 / brew install python"

step "docker (every organ its own box - INSTALL.md step 2 explains why)"
have docker && docker --version || echo "see https://docs.docker.com/get-docker/ (Android/Termux: skip; use proot if you want it)"

step "ollama (local models - INSTALL.md step 3: which model for your VRAM)"
have ollama && ollama --version || echo "curl -fsSL https://ollama.com/install.sh | sh"

step "murmur voice room (optional, INSTALL.md step 5)"
have docker && echo "docker run -d --name murmur --restart on-failure -p 64738:64738 -p 64738:64738/udp -v murmur-data:/data mumblevoip/mumble-server" || true

step "env keys"
# guard: a missing template must not abort the whole install under set -e
if [ -f .env ]; then echo ".env present"
elif [ -f .env.example ]; then cp .env.example .env && echo "created .env from the template - fill in your free-tier keys (never commit it)"
else echo "no .env template found (skipped - create .env by hand)"; fi

step "verify"
python3 tools/kit_doctor.py || true
echo "next: python3 tools/profile_boot.py  (first boot), then tutorial/TUTORIAL.md"
