# API Authentication and RBAC

## Scope

Authentication and role-based access control protect
BlockSikka API write operations.

Read-only API routes remain accessible for the current
learning/demo architecture.

The middleware currently applies authorization policy
to POST, PUT, PATCH, and DELETE requests under the API
prefix. GET requests do not currently require an
authenticated VIEWER principal.

## Authentication

The development backend uses opaque Bearer credentials
configured through environment variables, typically
from the Git-ignored backend/.env file.

The tracked backend/.env.example documents placeholder
configuration names only and must never contain real
credentials.

Configured credentials map to named application roles.
Duplicate configured token values are rejected, and
credential comparison uses constant-time comparison.

Tokens are not returned by API responses and must not
be written to application logs.

For the real browser payment E2E workflow, the
PAYMENT_OPERATOR credential is loaded by the test from
the ignored backend environment and inserted into
browser localStorage under `blocksikka.auth.token`.

The React API client reads that value only for
`/payments/prepare` and `/payments/relay`. It does not
attach the payment credential globally to read-only API
requests.

The token is deliberately not exposed through a
`VITE_*` environment variable because Vite client
environment values are bundled into browser JavaScript.

## Roles

### VIEWER

Identity role reserved for authenticated read-oriented
workflows.

The role exists in the current authentication model,
but read-only GET routes are presently public and do
not require VIEWER authorization.

### PAYMENT_OPERATOR

May prepare/relay payments and create settlements.

### BANK_OPERATOR

May operate the mock external-bank ledger and perform
bank-administration write operations.

### TREASURY_OPERATOR

May ingest settled bank credits and process bank
reversal events.

### TREASURY_ADMIN

May perform all privileged operations, including:

- minting;
- redemption;
- reconciliation recording;
- recovery execution;
- bank reversal resolution;
- token administrative actions;
- other otherwise-unclassified API writes.

## Fail-closed policy

Any future POST, PUT, PATCH, or DELETE route under the
API prefix that is not explicitly assigned a narrower
role automatically requires TREASURY_ADMIN.

This prevents newly introduced write endpoints from
silently becoming unauthenticated.

## HTTP behavior

Missing credentials:

    401 Unauthorized

Invalid credentials:

    401 Unauthorized

Authenticated principal without the required role:

    403 Forbidden

## Security logging

Protected write requests produce security log entries
containing:

- HTTP method;
- API path;
- authenticated subject;
- role;
- response status.

Bearer credentials themselves are never logged.

## Current limitation

This is a development/engineering identity layer using
environment-backed static credentials.

The real browser payment test additionally places the
development PAYMENT_OPERATOR credential in browser
localStorage. JavaScript executing in the same origin
can access localStorage, so an XSS compromise could
expose that credential.

The model provides no native token expiry, interactive
login, centralized identity lifecycle, device binding,
or institutional credential issuance.

It is therefore not a production identity or browser
session architecture.

A production deployment would normally replace this
credential verifier and browser token handling with an
enterprise identity architecture using mechanisms such
as OIDC/OAuth2, short-lived authenticated sessions,
managed service identities, certificate authentication,
or another institutionally governed identity system.

That future system would also require credential
lifecycle management, revocation, rotation, MFA where
appropriate, access reviews, durable security audit
retention, managed secrets, and explicit controls for
browser-session compromise.
