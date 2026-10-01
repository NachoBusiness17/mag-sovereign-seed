# OpenClaw through Cloudflare One

This is the second, identity-aware phone path for the containerized OpenClaw
Gateway. Tailscale remains the private operator path and break-glass route.

```text
phone browser
    -> Cloudflare Access (identity / MFA / policy)
    -> Cloudflare Tunnel (outbound-only)
    -> cloudflared-openclaw container
    -> shared namespace: 127.0.0.1:18789
    -> mag-openclaw
```

The Gateway has no host port. Cloudflare does not replace OpenClaw's Gateway
token; it adds an outer identity boundary.

## Dashboard setup

1. In Cloudflare Zero Trust, create a **remotely managed** tunnel under
   **Networking > Tunnels**.
2. Add a **Published application** route for a hostname you control, such as
   `openclaw.example.com`, with service:
   `http://127.0.0.1:18789`.
   The connector shares the Tailscale/OpenClaw network namespace, so loopback
   is intentional here.
3. Create a **Self-hosted** Access application for that hostname. Add an
   explicit **Allow** policy for the operator identity (and MFA through the
   selected identity provider). Do not use `Everyone`, `Bypass`, or an
   unauthenticated route.
4. Copy the remotely managed tunnel token into the local, uncommitted `.env`
   file as:

   ```dotenv
   CLOUDFLARE_TUNNEL_TOKEN=<paste-token-locally>
   ```

   Never put the token in Git, a chat message, a Dockerfile, or a committed
   compose file. Anyone holding it can run a connector for that tunnel.

## Start and verify

From the repository root:

```powershell
docker compose --profile cloudflare up -d cloudflared-openclaw
docker compose ps
docker compose logs --since=5m cloudflared-openclaw
```

Verify in the Cloudflare dashboard that the tunnel is **Healthy**, then open
the Access hostname from the phone. Complete the Access login, then provide
the existing OpenClaw Gateway token if the Control UI asks for it.

## Security boundaries

- Keep the Tailscale Serve route tailnet-only; it is the recovery path if
  Cloudflare policy or DNS is misconfigured.
- Do not enable Cloudflare Funnel or publish a second origin route.
- Do not enable broad TLS inspection or DLP as part of the first cut. The
  control panel should first be proven through Access, then policies can be
  piloted with a narrow operator group.
- Access is deny-by-default, but the application still needs an explicit
  Allow policy for the operator.
- A healthy tunnel only proves the connector reaches Cloudflare. Validate the
  full chain: Access login, origin response, OpenClaw WebSocket/control UI,
  and Gateway token authentication.

## Rollback

```powershell
docker compose --profile cloudflare stop cloudflared-openclaw
```

The Tailscale URL and the local Docker services remain unchanged.
