# Trusted local Vault proxy bootstrap

`scripts/native_vault_proxy.py` is an administrative supervisor for the native
Infisical proxy. It is separate from the AgentBridge HTTP server and its clients.
Normal package installation and desktop startup do not install or select it.

The supervisor loads one owner-only, checksum-pinned profile. Its source binding
is a dedicated Secrets Management project, Development `/proxy`, containing only
`AGENT_VAULT_PROXY_TOKEN` and `AGENT_VAULT_CA_PRIVATE_KEY`. The reviewed protected profile is the explicit source binding. It fetches only
those two bootstrap values in
trusted process memory and then replaces itself with the pinned native CLI.
The token and CA key enter only the proxy's
environment; neither is placed in arguments, files or log output.

The native proxy retrieves service credentials from Agent Vault. Ordinary tools
receive separate short-lived session capabilities and public placeholders. The
trusted supervisor, native CLI, Infisical login and proxy remain privileged; this
does not isolate full-access same-user processes or a compromised host.

The supervisor selects CLI 0.45.6, the existing public certificate and local port. It uses
`--data-dir=/dev/null`, so the proxy keeps its private CA and settings in memory.
After a restart it needs Infisical access; it has no local credential-cache
fallback. Missing source authentication, unexpected source values, changed
metadata or changed executables stop startup. Source-token rotation requires a
trusted profile update and a verified proxy identity and public CA fingerprint.

The registered profile contains metadata only: the source reference, proxy ID,
port, public CA fingerprint, and source/runtime/token
digests. It is installed under `~/.config/infisical/native-proxy/` with directory
mode 0700 and file mode 0600. Install the reviewed supervisor separately in a
protected directory and launch it with trusted Python using `-I -S -B`.

An authorized cutover must verify native behavior with fake credentials first,
preserve the reviewed Agent Vault project, traffic policy, port and public CA, prepare
source metadata and the protected profile, and verify the new runtime before
removing legacy private cache files. Restarting a running proxy or AgentBridge
server and renewing shared sessions require their operation authorization.
Existing app models, normal launch commands and hosted delivery stay unchanged.
Using a new proxy registration with the existing custom CA permits migration
without rotating client trust pins. Retain encrypted recovery in Infisical and
only the public certificate locally; never restore plaintext private caches as
an ordinary fallback.

Offline tests require only Python's standard library:

```sh
python3 -I -S -B scripts/test_native_vault_proxy.py
```

The tests check exact source selection, token-free arguments and errors, clean
process environments, cache-disabled native startup, strict metadata, and changed
source/runtime rejection. They do not provision accounts, rotate credentials,
register services, restart processes or call a live provider.
