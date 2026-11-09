# Private Serial Service

The public Device Manager EXE contains no GitHub token. It calls this service with
requests signed by a private device key generated automatically on that Windows PC.
Only the GitHub token in the Cloudflare Worker secret `GITHUB_TOKEN` accesses GitHub.
Never commit that secret, a `.dev.vars` file, Wrangler credentials, or private keys.

## Operator Experience

Operators download and open the single EXE. The first launch registers a public
device key and shows a short PC code while awaiting approval. They do not enter
tokens, create cloud accounts, install tools, or configure the network.
Approval persists across EXE updates. Approved PCs work outside the office too.

## Administrator

The bootstrap administrator is configured as a public identity in the Worker
secret `BOOTSTRAP_DEVICE`. Its private key remains encrypted with Windows DPAPI
under the administrator's Windows profile, never in the EXE or Worker.

Use Impostazioni > Computer autorizzati on the administrator PC. Refresh the list,
compare the short ID with the one visible on the intended office PC, then approve.
Do not approve a request merely because its computer name looks familiar.
Only the bootstrap administrator can list, approve, or revoke device identities.
Replacing the administrator identity requires the Cloudflare account owner.

## GitHub Data

The repository and branch are fixed to `coloretevm/GeneradorCSV-LoRa`, `main`.
Writes contain only `serial_registry.json` and `serial_registry_istantaneo.json`.
The GitHub GraphQL commit uses an expected head and updates both files atomically.
The service never accepts arbitrary repository paths, code updates, or token queries.
Manual corrections may lower serial values, preserving the existing workflow.
No-change saves return the existing revision without a commit.

Signed requests bind the HTTPS origin, method, path, body hash, timestamp and nonce.
The server rejects unapproved identities, replayed requests, stale revisions,
invalid fields and unknown routes. A SQLite Durable Object serializes operations.
Retry IDs keep successful saves idempotent for one day.

The authoritative counters remain on GitHub. Cloudflare stores device approvals,
temporary replay protection and short-lived save confirmations, not a replacement
per-PC counter registry. No IP allowlist is required.

## Deployment

```powershell
npm.cmd exec --yes --package=wrangler@4.158.0 -- wrangler deploy --config serial_service/wrangler.jsonc
npm.cmd exec --yes --package=wrangler@4.158.0 -- wrangler secret put GITHUB_TOKEN --config serial_service/wrangler.jsonc
npm.cmd exec --yes --package=wrangler@4.158.0 -- wrangler secret put BOOTSTRAP_DEVICE --config serial_service/wrangler.jsonc
node --test serial_service/test/service.test.mjs
```

Enter secrets privately at the command prompt, never in source or command-line
arguments. Provision the administrator public identity with `ServiceClient.identity`.
Wrangler's login is protected with its Windows keyring option on the admin machine.

The free plan is used; availability and usage limits still apply. Pending device
requests are capped and rate-limited. There are no unauthenticated registry writes.
Credential expiry/revocation still requires administrator maintenance in Cloudflare.
The migration does not automatically revoke credentials used by older clients.

## Windows Identity Helper

`DeviceIdentity.cs` creates an RSA-2048 identity per service origin, encrypts the
private key with DPAPI CurrentUser, and exposes only a public key and signatures.
The helper is compiled and embedded by `Device_Manager_v133.spec`.
It requires no additional install on PCs already running the cached portable app.
