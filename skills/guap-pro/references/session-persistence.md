# Diagnosing GUAP session persistence

In the current client, unchecked checkboxes are preserved as an explicit user
choice; authenticated login saves domain/path-aware cookies in a private jar.
`pro renew` and `renew_background.py` implement the bounded flow described below.
They require a separate renewal permit and do not expand a monitor's read scope.

## Separate the two sessions

- Distinguish the application session at `pro.guap.ru` from the SSO session at
  `sso.guap.ru`. A redirect from the cabinet does not establish that the SSO
  session has also expired.
- Inspect cookie names, domains, paths, expiry metadata and response status only.
  Never print cookie values, complete JWTs, authorization codes, state values,
  callback URLs with queries, passwords, or user/session identifiers.
- Treat a cookie's Max-Age and an identity JWT's encoded exp as cookie/token
  evidence, not proof of the realm's absolute session lifetime. Do not promise
  indefinite access from one successful renewal or a moving exp value.

## Check the existing client before adding keepalive

1. Inspect `scripts/relay.py` form parsing. Preserve an upstream `rememberMe`
   checkbox as a real, explicit user choice; skipping unchecked checkboxes removes
   the choice altogether. Never silently enable it. Its effect on idle/max
   lifetime depends on the realm settings, which public discovery does not expose.
2. Inspect cookie persistence. A flat Cookie header loses original domain, path,
   expiry and host-only metadata. It is not safe input for a multi-origin redirect
   client. A future cookie jar must send each cookie only where it belongs.
3. Inspect cabinet requests. If they neither process/persist Set-Cookie nor allow
   an explicitly controlled SSO flow, they cannot retain renewed session state.
   Do not remove a same-origin redirect guard merely to make login work.
4. Check the actual authentication flow. For a user-approved diagnostic,
   initiate a fresh cabinet OAuth flow in an isolated jar and test SSO with
   `prompt=none` and the existing, correctly scoped SSO cookies. Keep state in
   memory, validate the exact callback origin/path and state, and never follow or
   print the callback during a recognition-only probe. A code response proves SSO
   recognition now; it does not prove a restored cabinet session.
5. Report the distinction between an observed silent SSO response, a completed
   cabinet login, a deployed renewal feature, and demonstrated multi-day survival.

## Requirements for a future renewal feature

- Require a separate explicit persistent-renewal grant. Existing read-only
  background/daily permits do not authorize an OAuth callback, credential relay,
  login attempt, or new scheduled SSO traffic.
- Preserve a domain/path-aware private jar with expiry metadata, mode 0600,
  owner/regular-file checks, atomic replacement and a lock shared by all clients.
  Migrate legacy flat headers through an approved fresh login rather than guessing
  the original scope of every stored cookie.
- Allow only exact HTTPS origins `pro.guap.ru` and `sso.guap.ru`, validate OAuth
  state and the expected callback path, bound the redirect chain and timeouts,
  and never forward the original raw Cookie header across origins.
- Process rotated/deleted Set-Cookie values and persist only after the completed
  callback is followed by a verified authenticated cabinet response.
- Before a read, attempt at most one silent restoration if the cabinet session
  expired and the renewal grant is valid. Add proactive SSO traffic only with an
  explicitly approved cadence/night policy; normal cabinet reads need not touch
  SSO and therefore do not establish an SSO keepalive.
- On `login_required`, an interactive password/2FA/CAPTCHA step, grant revocation,
  invalid state, unexpected origin or failed verification, stop and emit one
  sanitized reauthentication notice. Never auto-submit saved credentials.
- Request `offline_access` or refresh tokens only through a client authorized for
  that use. Realm discovery advertising a grant/scope does not grant the cabinet
  client or this tool access to it; do not obtain another client's secret.

## Verification

Test cookie scoping, rotation/deletion, concurrent writes, invalid redirects/state,
missing/revoked renewal grants, and failure deduplication without live credentials.
Then separately verify an approved live completed restoration. Record multi-day
survival only after observing it across the former daily expiry window.

Primary references: Keycloak Server Administration Guide, sections "Enabling
Remember Me" and "Session and token timeouts"; OpenID Connect Core 1.0, section
3.1.2.1 (`prompt=none`). Recheck live server behavior rather than assuming the
installed Keycloak version or private realm timeout configuration.
