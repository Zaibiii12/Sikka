# API Authentication and RBAC

## Scope

Phase 25 adds authentication and role-based access
control to BlockSikka API write operations.

Read-only API routes remain accessible for the current
learning/demo architecture.

## Authentication

The development system uses opaque bearer credentials
stored only in backend/.env.

Tokens are never stored in Git or returned by API
responses.

Credential comparison uses constant-time comparison.

## Roles

### VIEWER

Identity-only role reserved for authenticated
read-oriented workflows.

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

It is not a production identity system.

A production deployment would normally replace this
credential verifier with an enterprise identity
provider using mechanisms such as OIDC/OAuth2, managed
service identities, certificate authentication, or
another institutionally governed identity system.

That future system would also require credential
lifecycle management, revocation, rotation, MFA where
appropriate, access reviews, and durable security audit
retention.
