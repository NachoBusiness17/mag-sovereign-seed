# OpenClaw from the phone, Docker-only

This is the supported remote path for the containerized OpenClaw Gateway:

    phone with Tailscale
        -> tailnet-only HTTPS
        -> tailscale-openclaw sidecar
        -> shared network namespace
        -> mag-openclaw:18789

The Gateway remains private inside Docker. There is no public Funnel and no
host port mapping for OpenClaw.

## One-time setup

1. Install and sign in to Tailscale on the phone.
2. Put a Tailscale auth key in the uncommitted project .env as TS_AUTHKEY=.
   The key is a secret; do not paste it into chat or commit it. If you prefer
   interactive login, leave it blank.
3. Enable HTTPS certificates for the tailnet in the Tailscale admin console
   under DNS. Serve is intentionally HTTPS-only; without this, the sidecar
   will authenticate but cannot issue the certificate needed by the phone UI.
4. From the project directory, start only the containerized path:

       docker compose up -d --build tailscale-openclaw openclaw

5. If no auth key was supplied, complete the login URL shown by:

       docker compose logs -f tailscale-openclaw

6. Inspect the generated tailnet hostname and Serve state:

       docker compose exec tailscale-openclaw tailscale status
       docker compose exec tailscale-openclaw tailscale serve status

7. On the phone, open the HTTPS URL for the Tailscale node shown by status.
   The Control UI will still request the OpenClaw Gateway token. Use the
   existing OPENCLAW_GATEWAY_TOKEN value from the local .env; never put it
   in this document or in a public URL.

## Operational rules

- Do not run a second host OpenClaw Gateway. The Docker service is authoritative.
- Do not publish 18789 on the host. Tailscale is the ingress boundary.
- Keep AllowFunnel false. Phone access is tailnet-only.
- Keep the Tailscale state volume persistent or the node identity will churn.
- Use docker compose logs --tail=200 tailscale-openclaw openclaw for diagnosis.
- The host openclaw gateway status command describes the old host service
  registration; use the Docker commands above for the live instance.

## Smoke test

The path is healthy only when all three checks pass:

    docker compose ps
    docker compose exec tailscale-openclaw tailscale status
    docker compose exec tailscale-openclaw tailscale serve status

Then load the HTTPS tailnet URL from the phone and confirm that the Control UI
can establish its WebSocket connection. A page that loads but cannot connect
usually means the Gateway token or Control UI origin policy, not Tailscale
routing.
