# Private Premium Evaluation Links

## Operator flow

Open `/admin/demo-access` using the existing super-admin login. Enter the customer
or company name and create a link. The default duration is 14 days; 7 and 30 days
are also available. Copy the generated link into the customer's email.

Opening the link signs the visitor into a dedicated Premium workspace and sends
them directly to `/dashboard`. There is no registration form, password or email
code. Reopening an active link returns to the same workspace and its test data.

The link is a bearer credential: anyone receiving a forwarded copy can access that
test workspace. Use a separate link per customer and avoid production/personal
data. The system does not claim to verify the visitor's personal email or obtain
registration consent. No existing customer or administrator account can be chosen
as a link target.

## Scope

- Real Premium entitlements, a primary assistant and clearly labelled starter knowledge.
- Assistant simulation and training, customer records, notes and internal appointments.
- No forced onboarding wizard; configuration is not falsely marked complete.
- External connectors, calls, billing, credential creation and identity changes
  require a normal live account. Demo appointments do not email recipients,
  including from the reminder worker. Public widget access is disabled.
- AI simulation/training has a persistent, atomic budget of 200 requests per
  workspace. Provider failures still consume a reservation; rate limits also apply.
- No automatic billing or automatic deletion when access expires.

## Link lifecycle

Expiry is measured from creation and enforced by the API, not only by the page.
The raw secret is returned only on creation/rotation and held in the UI's memory.
The list endpoint never returns it. After a page reload, use link rotation to
obtain a new link. Rotation closes prior sessions and invalidates the old link.
Revocation closes sessions but preserves the workspace and its data.

Secrets are cryptographically random (256 bits), stored as SHA-256 hashes, and
placed in the URL fragment rather than its query/path. The entry page removes the
fragment before making its exchange request. Access tokens remain in memory;
refresh credentials use the existing same-origin HttpOnly cookie flow. The entry
page is `noindex` and uses `no-referrer`. Creation/entry/rotation/revocation are
audited without raw link secrets.

## Deployment

Deploy the API and frontend changes together. Apply Alembic migration `056`
(parent `055`) before serving the new API. An active `premium` plan must already
exist. `FRONTEND_URL` must be the canonical customer-facing HTTPS origin.

After deployment, create a test link in the admin panel and verify direct entry,
Premium entitlements, same-workspace re-entry, isolation and revocation. Automated
browser tests use mocked provider/API responses; they do not prove production
provider availability or complete a live acceptance test.

## Automated checks

- `backend/tests/test_demo_access.py`: permissions, isolation, expiry, revocation,
  refresh, token rotation, AI budget and outbound-email suppression.
- `frontend/e2e/demo-access.spec.ts`: direct entry, refresh, invalid links and admin
  management on desktop and mobile.
