# starter-kit install helper (Windows PowerShell). Each step names what
# and why; everything headless. Run from the starter-kit folder.

$ErrorActionPreference = "Continue"

function Step($m) { Write-Host "`n== $m ==" }

# NOTE: try/catch does NOT catch native (exe) failures in PowerShell -
# the classic trap. Check $LASTEXITCODE explicitly after each native call.
function Check-Native($name) {
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        Write-Host "  $name reported exit $LASTEXITCODE (listed above as MISS context)"
    }
}

Step "git (version control - the memory is the chain)"
git --version; Check-Native "git"

Step "python 3.9+ (stdlib-only kit)"
python --version; Check-Native "python"

Step "docker (every organ its own box - INSTALL.md step 2 explains why)"
docker --version; Check-Native "docker"

Step "ollama (local models - INSTALL.md step 3 picks by your VRAM)"
ollama --version; Check-Native "ollama"

Step "murmur voice room (optional, INSTALL.md step 5)"
Write-Host "docker run -d --name murmur --restart on-failure -p 64738:64738 -p 64738:64738/udp -v murmur-data:/data mumblevoip/mumble-server"

Step "env keys"
if (Test-Path .env) { Write-Host ".env present" } else { Copy-Item .env.example .env; Write-Host "created .env from template - fill in free-tier keys (never commit it)" }

Step "verify"
python tools/kit_doctor.py
Write-Host "next: python tools/profile_boot.py  (first boot), then tutorial\TUTORIAL.md"
