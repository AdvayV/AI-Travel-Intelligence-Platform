# TravelRoute Production Implementation Backlog

> Deferred scope: this backlog describes a future commercial-grade release. The active portfolio/demo scope uses best-effort Google Flights comparison fares, transparent fallback estimates, and non-ticketing demo references.

This backlog converts `PRODUCTION_ROADMAP.md` into executable engineering work. It assumes one unified `travelsolsv2` product with Route Intelligence and Corporate Booking modules.

## Priority and Sizing

- **P0** — required for safe live-price deployment.
- **P1** — required for the production-ready release.
- **P2** — valuable after the first controlled release.
- **S** — up to one engineering day.
- **M** — approximately two to three engineering days.
- **L** — approximately four to five engineering days.

Estimates include implementation and focused tests but exclude external provider approval delays.

## Epic A — Foundation

### TRV-A01 — Capture a reproducible baseline

- **Priority/size:** P0 / S
- **Depends on:** none
- Record supported Python and Node versions.
- Pin Python dependencies and keep the existing npm lockfile authoritative.
- Add commands for backend import checks and frontend production builds.
- Capture current API responses for forecasting, graph retrieval, agent execution, and booking demo fixtures.
- **Acceptance:** a clean environment can install dependencies and reproduce the documented baseline.

### TRV-A02 — Introduce validated application settings

- **Priority/size:** P0 / M
- **Depends on:** TRV-A01
- Add environment-specific settings for development, test, staging, and production.
- Validate secrets, database URLs, allowed origins, provider mode, mock mode, and feature flags at startup.
- Reject placeholder credentials and mock fare mode in production.
- **Acceptance:** invalid production configuration fails before the API begins serving traffic.

### TRV-A03 — Define domain models and error contracts

- **Priority/size:** P0 / M
- **Depends on:** TRV-A02
- Define immutable search request, flight offer, segment, money, fare condition, passenger, quote, and booking models.
- Use decimal monetary amounts with explicit ISO currency codes.
- Define stable error codes for validation, provider timeout, no offers, expired offer, price change, policy rejection, approval required, and booking failure.
- **Acceptance:** mock and live providers must return the same normalized models and errors.

### TRV-A04 — Create provider interfaces

- **Priority/size:** P0 / M
- **Depends on:** TRV-A03
- Add `FlightProvider.search`, `FlightProvider.reprice`, and `FlightProvider.create_order` interfaces.
- Keep provider SDK/HTTP payloads out of API routes and agent tools.
- Wrap the existing generated flights in an explicit development-only provider.
- **Acceptance:** provider selection is configuration-driven and does not change API or UI contracts.

### TRV-A05 — Version the public API

- **Priority/size:** P0 / S
- **Depends on:** TRV-A03
- Add `/api/v1` routing, consistent response envelopes, request IDs, and structured exception handlers.
- Keep temporary compatibility wrappers for existing frontend calls.
- **Acceptance:** new routes are versioned without breaking the current demo during migration.

## Epic B — Real Prices and Booking Integrity

### TRV-B01 — Implement provider authentication and HTTP client

- **Priority/size:** P0 / M
- **Depends on:** TRV-A02, TRV-A04
- Implement pooled asynchronous HTTP, bounded timeouts, retries only for safe operations, provider request IDs, and redacted logs.
- Default implementation target: Duffel test mode.
- **Acceptance:** credentials never reach logs or frontend responses, and timeout behavior is deterministic.

### TRV-B02 — Implement live offer search

- **Priority/size:** P0 / L
- **Depends on:** TRV-B01
- Translate one-way and return search requests into provider requests.
- Normalize slices, segments, carriers, cabin, baggage, conditions, totals, currency, source, retrieval time, and expiry.
- Preserve the provider offer ID only on the server or in an opaque signed internal reference.
- **Acceptance:** provider fixtures and test-mode requests produce identical normalized schemas.

### TRV-B03 — Add short-lived offer storage

- **Priority/size:** P0 / M
- **Depends on:** TRV-B02
- Cache normalized offers in Redis using a TTL no longer than provider expiry.
- Store search ownership and prevent users from accessing another user's opaque offer reference.
- Avoid claiming a cache hit is newly retrieved live data.
- **Acceptance:** expired offers cannot be quoted or booked and are never displayed as current.

### TRV-B04 — Remove synthetic modification of live fares

- **Priority/size:** P0 / S
- **Depends on:** TRV-B02
- Remove custom surge multiplication from all live provider offers.
- Retain opportunity score and demand forecast as separate analytics fields.
- Update labels to distinguish observed live fare, cached observation, and predicted market signal.
- **Acceptance:** the displayed provider total exactly matches the normalized provider response.

### TRV-B05 — Implement repricing

- **Priority/size:** P0 / M
- **Depends on:** TRV-B03
- Retrieve the latest selected offer before confirmation.
- Compare previous and current totals, conditions, baggage, segments, and availability.
- Return an explicit user-confirmation requirement when anything material changes.
- **Acceptance:** no booking request can proceed using an offer that has not passed current repricing validation.

### TRV-B06 — Build deterministic policy quotes

- **Priority/size:** P0 / M
- **Depends on:** TRV-B04, TRV-B05
- Evaluate cabin, fare class/brand, maximum amount, preferred carrier, advance purchase, route, and approval thresholds in domain code.
- Store each rule result and source policy version.
- Use the LLM only to explain the result.
- **Acceptance:** identical quote inputs always produce identical compliance decisions without an LLM call.

### TRV-B07 — Add approval and booking state machine

- **Priority/size:** P1 / L
- **Depends on:** TRV-B05, TRV-B06, TRV-G01
- Define `DRAFT`, `QUOTED`, `APPROVAL_REQUIRED`, `APPROVED`, `REPRICED`, `BOOKING`, `CONFIRMED`, `FAILED`, and `CANCELLED` transitions.
- Enforce authorization and legal transitions server-side.
- **Acceptance:** API clients cannot skip policy, approval, repricing, or confirmation states.

### TRV-B08 — Implement provider order creation

- **Priority/size:** P1 / L
- **Depends on:** TRV-B07, TRV-G02
- Collect required passenger details through a secure confirmation flow.
- Require idempotency keys and persist provider request/result references.
- Keep live order creation behind a disabled production feature flag until provider onboarding and operational runbooks are approved.
- **Acceptance:** repeated client requests cannot create duplicate orders, and test-mode orders are fully auditable.

## Epic C — Fast Search and Responsive Enrichment

### TRV-C01 — Add direct flight-search endpoint

- **Priority/size:** P0 / M
- **Depends on:** TRV-B02, TRV-A05
- Implement `POST /api/v1/flights/search` without RAG or LLM calls.
- Return search metadata and offers as soon as the provider responds.
- **Acceptance:** live flight search remains available when the LLM or vector store is unavailable.

### TRV-C02 — Parallelize offer enrichment

- **Priority/size:** P1 / M
- **Depends on:** TRV-C01, TRV-B06
- Run weather, policy facts, Neo4j traversal, keyword retrieval, and vector retrieval concurrently where independent.
- Apply per-dependency timeouts and return partial enrichment statuses.
- **Acceptance:** one failed enrichment dependency does not discard valid live offers.

### TRV-C03 — Stream enrichment events

- **Priority/size:** P1 / M
- **Depends on:** TRV-C02
- Add Server-Sent Events for policy, weather, Hybrid RAG, and explanation progress.
- Include event IDs, terminal states, reconnect behavior, and cancellation.
- **Acceptance:** the UI can render each completed stage without waiting for all stages.

### TRV-C04 — Remove frontend artificial latency

- **Priority/size:** P0 / S
- **Depends on:** TRV-C01
- Remove the 450 ms per-step timers.
- Cancel stale requests and prevent outdated responses from replacing the latest search.
- **Acceptance:** results render immediately when received from the server.

### TRV-C05 — Add performance instrumentation

- **Priority/size:** P1 / M
- **Depends on:** TRV-C01, TRV-C02
- Measure search provider time, normalization time, cache time, policy time, retrieval time, LLM time, and frontend time-to-first-offer.
- Report p50, p95, errors, and timeouts per dependency.
- **Acceptance:** staging dashboards can identify which dependency owns observed latency.

## Epic D — Compliant Web Scraping

### TRV-D01 — Create source governance registry

- **Priority/size:** P0 / M
- **Depends on:** TRV-A02
- Store source owner, purpose, allowed paths, Terms review, robots result, schedule, rate limit, parser version, retention, and enable state.
- Default every source to disabled until reviewed.
- **Acceptance:** the worker cannot fetch an unregistered or disabled domain.

### TRV-D02 — Build reusable fetch framework

- **Priority/size:** P1 / M
- **Depends on:** TRV-D01
- Add identifiable user agent, bounded concurrency, rate limits, timeouts, exponential backoff, conditional requests, response-size limits, and content-type validation.
- Use static HTTP by default and an isolated Playwright worker only when approved and necessary.
- **Acceptance:** fetch policy is enforced centrally rather than reimplemented by each source.

### TRV-D03 — Define normalized travel signals

- **Priority/size:** P1 / S
- **Depends on:** TRV-A03
- Define source, URL, title, content, type, severity, affected entities, effective dates, fetch time, hash, parser version, and staleness fields.
- **Acceptance:** all scraper adapters emit the same validated signal model.

### TRV-D04 — Implement first two approved adapters

- **Priority/size:** P1 / L per source
- **Depends on:** TRV-D02, TRV-D03, user-approved domains
- Implement parser fixtures before live scheduling.
- Preserve raw snapshots for debugging and provenance.
- **Acceptance:** layout changes fail safely and never replace the last valid normalized signal.

### TRV-D05 — Deduplicate and ingest signals

- **Priority/size:** P1 / M
- **Depends on:** TRV-D04, TRV-G01
- Deduplicate by canonical URL and content hash.
- Store normalized signals transactionally, then enqueue graph/vector ingestion.
- Avoid re-embedding unchanged content.
- **Acceptance:** repeated fetches of unchanged pages create no duplicate graph nodes or embeddings.

### TRV-D06 — Monitor scraper quality

- **Priority/size:** P1 / M
- **Depends on:** TRV-D05, TRV-G04
- Alert on parser failure, empty extraction, unexpected volume, robots/Terms status change, stale source, and repeated network failure.
- **Acceptance:** stale or broken sources are visible and removable from RAG retrieval.

## Epic E — Hybrid RAG and Safe Graph Access

### TRV-E01 — Separate structured and unstructured retrieval

- **Priority/size:** P1 / M
- **Depends on:** TRV-A03
- Return Neo4j graph facts, keyword results, and vector results as typed candidates with provenance.
- Apply entity filters before semantic retrieval where possible.
- **Acceptance:** each candidate records retrieval method, score, source, and timestamp/version.

### TRV-E02 — Add keyword retrieval and rank fusion

- **Priority/size:** P1 / M
- **Depends on:** TRV-E01
- Add BM25/full-text retrieval and fuse it with vector and graph candidates.
- Keep fusion strategy configurable and observable.
- **Acceptance:** exact policy identifiers and semantic paraphrases are both retrieved reliably.

### TRV-E03 — Add reranking and context budgets

- **Priority/size:** P1 / M
- **Depends on:** TRV-E02
- Rerank fused candidates, remove near-duplicates, and construct token-bounded context.
- **Acceptance:** context contains the strongest non-duplicated evidence rather than a fixed number from every collection.

### TRV-E04 — Add answer citations

- **Priority/size:** P0 / M
- **Depends on:** TRV-E03, TRV-D05
- Return document, page/section or source URL, fetch time, and matching excerpt metadata.
- Add an insufficient-evidence response when citations do not support an answer.
- **Acceptance:** every policy/advisory claim in a generated answer maps to retrievable evidence.

### TRV-E05 — Restrict Cypher execution

- **Priority/size:** P0 / M
- **Depends on:** TRV-A02
- Remove public arbitrary write-capable Cypher.
- Validate generated queries as read-only, parameterize user values, apply query/result limits, and use a Neo4j read role.
- **Acceptance:** write, procedure abuse, unrestricted traversal, and oversized results are rejected before execution.

### TRV-E06 — Build RAG evaluation suite

- **Priority/size:** P1 / L
- **Depends on:** TRV-E04
- Create versioned questions and expected sources for policies, fare rules, routes, waivers, advisories, and insufficient-context cases.
- Track retrieval recall, citation correctness, groundedness, policy explanation agreement, and latency.
- **Acceptance:** quality regressions fail CI or block release according to agreed thresholds.

## Epic F — User Interface

### TRV-F01 — Consolidate navigation and design system

- **Priority/size:** P1 / M
- **Depends on:** none
- Present Forecasting and Booking as first-class modules in one responsive shell.
- Define tokens and reusable controls for spacing, typography, color, focus, loading, errors, and statuses.
- **Acceptance:** both modules share consistent navigation and responsive behavior.

### TRV-F02 — Build structured search form

- **Priority/size:** P0 / M
- **Depends on:** TRV-C01
- Add origin/destination autocomplete, trip type, dates, passengers, and cabin fields with client/server validation.
- Let conversational input populate the form instead of directly booking.
- **Acceptance:** users can inspect and correct every search parameter before submitting.

### TRV-F03 — Build transparent offer cards

- **Priority/size:** P0 / L
- **Depends on:** TRV-F02, TRV-B02
- Display total/currency, taxes, segments, duration, stops, baggage, fare conditions, source, update time, and expiry.
- Visibly distinguish live, test, mock, cached, and expired data.
- **Acceptance:** no offer can be mistaken for a live current price when it is not one.

### TRV-F04 — Add sorting, filtering, and comparison

- **Priority/size:** P1 / M
- **Depends on:** TRV-F03
- Add filters for stops, carriers, times, duration, baggage, compliance, and approval.
- Add side-by-side comparison of selected offers.
- **Acceptance:** filtering never changes the server-authoritative offer values.

### TRV-F05 — Add progressive compliance and citations

- **Priority/size:** P1 / L
- **Depends on:** TRV-C03, TRV-E04
- Render deterministic rule outcomes first, then optional natural-language explanation.
- Link policy rules and scraped advisories to their evidence.
- **Acceptance:** users can distinguish a rule decision from an LLM explanation.

### TRV-F06 — Add reprice and approval confirmation

- **Priority/size:** P0 / M
- **Depends on:** TRV-B05, TRV-B07
- Display all material changes since selection and require explicit reconfirmation.
- Route approval-required offers to the approval flow.
- **Acceptance:** booking UI cannot submit an expired, changed-but-unconfirmed, or unapproved offer.

### TRV-F07 — Accessibility and responsive verification

- **Priority/size:** P1 / M
- **Depends on:** TRV-F01 through TRV-F06
- Verify keyboard flow, focus, labels, contrast, live-region announcements, reduced motion, and mobile layouts.
- **Acceptance:** automated accessibility checks pass and critical flows are keyboard-complete.

## Epic G — Persistence, Security, Observability, and Deployment

### TRV-G01 — Add PostgreSQL and migrations

- **Priority/size:** P0 / L
- **Depends on:** TRV-A02, TRV-A03
- Store users, searches, approvals, booking states, provider references, scraper sources/signals, and audit events.
- Add migration and rollback commands.
- **Acceptance:** a fresh and upgraded database produce the same expected schema.

### TRV-G02 — Add authentication and role authorization

- **Priority/size:** P0 / L
- **Depends on:** TRV-G01
- Add OIDC/JWT boundary and employee, manager, travel-agent, and administrator roles.
- Enforce tenant/user ownership of searches and bookings.
- **Acceptance:** protected operations fail closed and are covered by role matrix tests.

### TRV-G03 — Apply API security controls

- **Priority/size:** P0 / M
- **Depends on:** TRV-A02, TRV-G02
- Configure strict CORS/hosts, HTTPS awareness, rate limits, payload limits, secret redaction, security headers, idempotency, and PII retention.
- **Acceptance:** production security configuration is tested during startup and CI.

### TRV-G04 — Add observability

- **Priority/size:** P1 / L
- **Depends on:** TRV-A05
- Add structured logs, correlation IDs, traces, dependency metrics, error reporting, dashboards, and alerts.
- Separate liveness from dependency-aware readiness.
- **Acceptance:** a failed provider request is traceable from browser request through provider response/error.

### TRV-G05 — Add backend and frontend test foundations

- **Priority/size:** P0 / L
- **Depends on:** TRV-A01
- Add unit, integration, contract, and Playwright E2E suites with isolated configuration and fixtures.
- **Acceptance:** all suites run locally and in CI without live production credentials.

### TRV-G06 — Add container artifacts

- **Priority/size:** P0 / M
- **Depends on:** TRV-A01, TRV-A02
- Add multi-stage API/frontend images, a separate worker command, non-root runtime users, health checks, and a local Compose stack.
- **Acceptance:** the complete staging-equivalent stack starts from documented commands.

### TRV-G07 — Add CI pipeline

- **Priority/size:** P0 / M
- **Depends on:** TRV-G05, TRV-G06
- Run formatting/linting, tests, RAG evaluation gates, dependency/secret scans, frontend build, and container build.
- **Acceptance:** protected deployment artifacts originate only from a passing immutable revision.

### TRV-G08 — Add staging and production CD

- **Priority/size:** P1 / L
- **Depends on:** TRV-G07, hosting decision
- Deploy migrations, API, worker, and frontend; then run smoke tests.
- Add manual production approval, progressive rollout, rollback, and environment-scoped secrets.
- **Acceptance:** staging deployment and rollback are demonstrated before first production release.

### TRV-G09 — Add operational runbooks

- **Priority/size:** P1 / M
- **Depends on:** TRV-G04, TRV-G08
- Document provider outage, price mismatch, duplicate booking, scraper breakage, database recovery, credential rotation, rollback, and PII requests.
- **Acceptance:** each production alert links to an actionable runbook and owner.

## Proposed Sprint Sequence

### Sprint 0 — Baseline and architecture

- TRV-A01, A02, A03, A04, A05
- TRV-G05 test skeleton
- TRV-G06 initial containers
- **Demo:** reproducible unified app with versioned contracts and provider-neutral mock search.

### Sprint 1 — Live search

- TRV-B01, B02, B03, B04
- TRV-C01, C04
- TRV-F02, F03
- **Demo:** Duffel test-mode offers rendered immediately with source, currency, timestamp, and expiry.

### Sprint 2 — Quote, reprice, and persistence

- TRV-B05, B06, B07
- TRV-G01, G02, G03
- TRV-F06
- **Demo:** deterministic policy quote, approval boundary, repricing, and auditable booking state.

### Sprint 3 — Scraping and Hybrid RAG

- TRV-D01 through D05
- TRV-E01 through E05
- **Demo:** two approved sources ingested with provenance and cited alongside policy graph facts.

### Sprint 4 — Experience and speed

- TRV-C02, C03, C05
- TRV-F01, F04, F05, F07
- TRV-E06
- **Demo:** progressive enrichment, measurable performance, accessible comparison and cited explanations.

### Sprint 5 — Production release

- TRV-B08
- TRV-D06
- TRV-G04, G07, G08, G09
- Security, resilience, load, backup/restore, and rollback verification
- **Demo:** staging order flow and controlled production release readiness review.

## Critical Path

```text
A01 -> A02 -> A03 -> A04 -> B01 -> B02 -> B03 -> B05 -> B06
                                                   |       |
                                                   v       v
                                                  G01 -> B07 -> B08

A01 -> G05 -> G06 -> G07 -> G08
```

Scraping, Hybrid RAG, and most UI work can proceed in parallel once the normalized contracts are stable.

## First Implementation Slice

The first code-change batch should remain provider-neutral and include:

1. validated settings and environment modes;
2. normalized money, segment, offer, and search models;
3. provider interface plus explicit mock adapter;
4. versioned direct flight-search endpoint;
5. focused unit/API tests;
6. no UI redesign and no live credentials yet.

This slice proves the architecture before adding Duffel-specific code.

## Decision Gates

| Gate | Needed before | Default if approved |
| --- | --- | --- |
| Fare provider | TRV-B01 | Duffel test mode |
| Search-only vs booking | TRV-B07/B08 | Booking behind disabled feature flag |
| Hosting budget/region | TRV-G08 | Low-cost managed container deployment |
| Authentication source | TRV-G02 | Project OIDC provider for staging |
| Approved scraper domains | TRV-D04 | No scraper enabled until explicitly approved |

Provider-neutral Sprint 0 can begin before these choices. Live-provider, scraper-source, authentication, and cloud-specific tickets must wait at their respective decision gates.
