# TravelRoute Production Roadmap

> Current delivery scope: the user selected a portfolio/demo release rather than a commercial booking product. The application now uses best-effort Google Flights comparison fares through `fast-flights`, visibly marks fallback estimates, and creates demo references only. The production roadmap below is retained as optional future work.

## 1. Objective

Convert the existing two-part TravelRoute suite into a deployable product with:

- live, traceable flight prices;
- compliant web-scraped travel intelligence;
- faster search and agent responses;
- a clearer responsive interface;
- production security, persistence, testing, observability, and deployment automation.

The deployed product will retain two user-facing modules in one application:

1. **Route Intelligence** — demand, weather, market signals, price observations, and travel-date recommendations.
2. **Corporate Booking** — live flight search, policy compliance, Hybrid RAG explanations, approval, repricing, and booking.

## 2. Current-State Findings

- `travel/flight_search.py` now returns best-effort live Google Flights comparison fares with a visibly marked demo fallback; a contracted production fare provider remains future work.
- `travel/pnr_builder.py` creates an explicitly labeled demo reference rather than a provider order.
- `booking_agent.py` keeps live observed fares unchanged and presents demand forecasts as separate advisory analytics.
- Flight search currently waits for the RAG/LLM agent even though live offer retrieval does not require an LLM.
- The frontend now renders returned agent steps immediately; the synchronous RAG and weather workflow remains the primary latency source.
- ChromaDB, scheduled jobs, and the API run in the same process, which prevents safe horizontal scaling.
- There are no automated tests, containers, CI/CD workflows, database migrations, or production deployment manifests.
- Public arbitrary-Cypher execution and development CORS settings require production restrictions.

## 3. Default Architecture Decisions

These defaults allow implementation to begin while keeping external providers replaceable.

| Area | Default | Reason |
| --- | --- | --- |
| Canonical application | `travelsolsv2` unified API and UI | It already contains forecasting, GraphRAG, policy, and booking features. |
| Fare provider | Duffel test mode, then live mode | Supports offer search, repricing, expiry, and order creation. |
| Comparison-only alternative | Skyscanner Live Prices | Suitable if the product only displays offers and redirects users. |
| Development fallback | Explicit mock provider | Useful for local tests; prohibited as a silent production fallback. |
| Transaction store | PostgreSQL | Stores users, searches, approvals, bookings, and audit events. |
| Cache and queue | Redis | Stores short-lived offers, rate limits, idempotency keys, and job state. |
| Knowledge graph | Neo4j | Preserves policy, route, passenger, waiver, and document relationships. |
| Vector retrieval | Adapter with ChromaDB locally | Allows a managed vector service to replace local Chroma in production. |
| Background processing | Dedicated worker and scheduled jobs | Keeps scraping, ingestion, and forecasting out of API processes. |
| Deployment | Docker-based, provider-neutral | Supports local Compose and managed container platforms. |

Official references:

- Duffel flight offers and booking: <https://duffel.com/docs/guides/getting-started-with-flights>
- Skyscanner Live Prices: <https://developers.skyscanner.net/docs/flights-live-prices/quick-start>
- Robots Exclusion Protocol guidance: <https://developers.google.com/search/docs/crawling-indexing/robots/intro>

## 4. Target Architecture

```text
Browser
  |
  v
React application
  |-- Route Intelligence module
  |-- Live Flight Search module
  |-- Policy/RAG explanation panel
  |
  v
FastAPI API
  |-- Search service --------> FlightProvider adapter ------> Duffel/alternative
  |                              |-- search
  |                              |-- reprice
  |                              `-- create order
  |-- Policy service --------> Neo4j
  |-- Retrieval service -----> BM25 + vector search + graph traversal + reranker
  |-- Weather service -------> Open-Meteo
  |-- Booking service -------> PostgreSQL + provider order
  `-- Cache/rate limits -----> Redis

Background worker
  |-- approved-source scrapers
  |-- normalization and deduplication
  |-- document chunking and embedding
  |-- graph/vector ingestion
  `-- forecasting and scheduled refreshes
```

Live flight search stays deterministic and fast. RAG, policy explanations, scraped signals, and agent reasoning enrich the offers after the initial results arrive.

## 5. Phase 0 — Stabilize the Foundation

### Work

- Treat `travelsolsv2` as the deployable application and preserve `travelsols` as a reference until feature parity is verified.
- Split configuration, routes, provider clients, domain services, repositories, and workers into separate modules.
- Introduce validated environment settings for development, test, staging, and production.
- Define a single currency convention using ISO 4217 codes and decimal values; remove mixed USD/INR labels.
- Add PostgreSQL migrations for users, searches, approvals, bookings, and audit events.
- Add request IDs, structured errors, and a consistent `/api/v1` response format.

### Exit Criteria

- Existing forecasting, graph, policy, and booking-demo flows still work locally.
- The API starts without running scraping or forecasting inside each web worker.
- Production configuration cannot start with placeholder secrets or mock fare mode.

## 6. Phase 1 — Real Flight Offers and Booking Boundary

### Provider Contract

Implement an asynchronous provider interface with three operations:

```text
search(search_request) -> flight offers
reprice(provider_offer_id) -> current offer
create_order(provider_offer_id, passenger, payment_reference) -> booking
```

Every normalized offer must include:

- internal offer ID and provider offer ID;
- provider name and live/test mode;
- origin, destination, segments, carrier, flight numbers, and timings;
- cabin, fare brand, baggage, refund/change conditions, and seat availability when supplied;
- base amount, tax amount, total amount, and currency;
- retrieval time and provider expiry time;
- raw provider reference for support and auditing.

### API Contract

- `POST /api/v1/flights/search` — returns offers without invoking the LLM.
- `POST /api/v1/flights/offers/{offer_id}/reprice` — refreshes availability and total price.
- `POST /api/v1/bookings/quote` — applies policy checks and approval rules without booking.
- `POST /api/v1/bookings` — requires a repriced offer, user confirmation, idempotency key, and authorization.
- `GET /api/v1/bookings/{booking_id}` — returns provider and internal booking state.

### Price-Integrity Rules

- Never apply the project surge multiplier to a provider's live total.
- Display market/demand predictions as separate analytics, not as a modified fare.
- Never label an expired or cached historical observation as a current fare.
- Reprice immediately before confirmation and show the user any price change.
- In production, provider failure returns an unavailable state; it never generates a plausible-looking fallback price.
- Keep mock offers visibly marked and available only in development/test environments.

### Exit Criteria

- Duffel test searches are normalized into the provider-independent schema.
- Test scenarios cover no offers, timeout, expiry, price change, and booking failure.
- The booking audit stores the selected and repriced totals.
- No `MOCK_TRAVEL` response can be emitted under production configuration.

## 7. Phase 2 — Compliant Scraping and Signal Ingestion

### Intended Sources

Scraping enriches travel decisions; it is not the transactional fare source. Candidate content includes:

- official airline and airport disruption notices;
- government travel and visa advisories;
- weather warnings and natural-disaster notices;
- public destination-event calendars;
- airline policy and baggage pages where automated access is permitted.

### Source Registry

Each scraper must be registered with:

- owner, purpose, base URL, and allowed paths;
- Terms-of-Service review status and `robots.txt` result;
- expected update frequency and rate limit;
- parser version and required fields;
- retention policy and whether embedding is allowed;
- disable switch and last successful run.

### Pipeline

```text
Source registry -> HTTP fetch -> raw snapshot -> parse -> validate -> deduplicate
                -> normalized TravelSignal -> PostgreSQL/object storage
                -> chunk/embed -> vector store
                -> extract entities/relationships -> Neo4j
```

Use `httpx` and HTML parsing for static pages. Use Playwright only when an approved source requires JavaScript rendering. Scrapers must use bounded concurrency, timeouts, retries with backoff, conditional requests, content hashes, and parser fixture tests.

### Normalized Signal

Each signal records source URL, source type, title, text, affected airports/routes/countries, severity, effective dates, fetched time, content hash, parser version, and expiry/staleness state.

### Exit Criteria

- At least two approved sources run from the worker, not the API process.
- Duplicate content is not repeatedly embedded or inserted into Neo4j.
- Every RAG citation can link back to a source URL and fetch time.
- Parser failures raise alerts and do not overwrite the last valid record.

## 8. Phase 3 — Production Hybrid RAG

### Retrieval Flow

1. Parse entities and structured filters from the question.
2. Retrieve exact passenger, route, policy, waiver, and booking facts from Neo4j.
3. Run keyword/BM25 and vector retrieval over policy and scraped documents.
4. Fuse ranked results and rerank the strongest candidates.
5. Build a token-bounded context containing source, page/section, URL, and timestamp metadata.
6. Generate an answer with citations and an explicit insufficient-evidence response when grounding is weak.

### Safety

- Make natural-language-to-Cypher read-only and validate the generated AST/query before execution.
- Remove public arbitrary-Cypher access or restrict it to authenticated administrators with an allowlist.
- Parameterize values and enforce query timeout, result limit, and database read role.
- Do not expose raw passenger PII to the LLM unless the specific workflow requires it.

### Evaluation

Build a versioned set of policy, route, waiver, and booking questions. Track retrieval recall, citation correctness, answer groundedness, policy-decision accuracy, latency, and fallback frequency.

### Exit Criteria

- Policy answers cite the correct document section or source URL.
- Compliance decisions are deterministic domain logic; the LLM only explains them.
- Destructive Cypher cannot be executed through public endpoints.
- The evaluation suite passes agreed quality thresholds before deployment.

## 9. Phase 4 — Faster Results

### Backend

- Return live offers independently of the agent.
- Run weather, graph, keyword, vector, and policy lookups concurrently when independent.
- Use asynchronous HTTP clients and connection pooling.
- Cache only within provider expiry and data-source freshness limits.
- Preload embedding resources in the worker or use an external embedding service.
- Add database indexes for booking history, policy lookup, source timestamps, and content hashes.
- Stream enrichment and agent events through Server-Sent Events rather than holding the entire response.

### Frontend

- Remove the artificial 450 ms step-render delay.
- Render search results immediately and load compliance/RAG panels progressively.
- Cancel stale searches with `AbortController`.
- Use request caching and deduplication for airports, policies, and recent searches.
- Lazy-load graph visualization and other large bundles.

### Initial Performance Budgets

- Health/readiness response: p95 below 300 ms.
- Cached metadata request: p95 below 500 ms.
- First live offer displayed: target p95 below 5 seconds, measured separately by provider.
- Policy evaluation after offers: target p95 below 2 seconds without LLM explanation.
- UI interaction latency: below 200 ms for local state changes.

Targets must be measured in staging and adjusted only from recorded provider and infrastructure data.

## 10. Phase 5 — UI and User Journey

### Search Experience

- Use a structured search form for airports, dates, trip type, passengers, and cabin.
- Keep natural-language search as an optional convenience that fills the structured form.
- Add skeletons, progressive results, clear empty states, retry actions, and provider-unavailable states.

### Offer Cards

- Display total fare and currency prominently.
- Show taxes, baggage, refund/change conditions, segments, duration, stops, source, last updated time, and expiry.
- Support sorting and filtering by total, duration, departure time, stops, carrier, compliance, and approval requirement.
- Label test and mock data unmistakably.

### Corporate Workflow

- Show deterministic compliance checks beside each offer.
- Explain policy failures with document citations.
- Require explicit user confirmation after repricing.
- Route approval-required offers to a manager workflow instead of generating a booking.
- Provide booking status, audit timeline, and provider reference after confirmation.

### Quality

- Responsive behavior at mobile, tablet, and desktop sizes.
- Keyboard navigation, visible focus, semantic labels, sufficient contrast, and screen-reader status announcements.
- Error messages that distinguish validation, provider, policy, authentication, and network failures.

## 11. Phase 6 — Security and Operations

- Add OIDC/JWT authentication and employee, manager, travel-agent, and administrator roles.
- Keep provider tokens and database credentials in platform secret storage.
- Restrict CORS to deployed origins and apply trusted-host and HTTPS settings.
- Add request validation, rate limiting, payload limits, idempotency, and CSRF protection where cookies are used.
- Encrypt sensitive data in transit and at rest; define PII retention and deletion procedures.
- Record immutable audit events for policy decisions, approvals, repricing, and booking attempts.
- Add structured JSON logs, traces, metrics, error reporting, dashboards, and alerts.
- Expose separate liveness and dependency-aware readiness endpoints.
- Create backup, restore, migration, rollback, and incident runbooks.

## 12. Phase 7 — Testing and Release Gates

| Layer | Required coverage |
| --- | --- |
| Unit | Fare normalization, currency precision, policy rules, scoring, parsers, entity extraction |
| Contract | Provider request/response fixtures, timeouts, malformed payloads, expiry and repricing |
| Integration | FastAPI + PostgreSQL + Redis + Neo4j/vector adapters |
| RAG | Retrieval recall, citation accuracy, groundedness, insufficient-context behavior |
| End-to-end | Search, filter, select, compliance, approval, reprice, confirm, booking history |
| Security | Authentication, role checks, Cypher restrictions, secret scanning, dependency scanning |
| Performance | Concurrent searches, cache behavior, provider slowdown, worker backlog |
| Resilience | Provider outage, scraper layout change, Neo4j outage, Redis outage, duplicate requests |

Release is blocked if any of these are true:

- a production response can silently contain a generated fare;
- a booking can bypass repricing or user confirmation;
- policy rules are decided only by an LLM;
- uncited scraped content influences a decision;
- destructive Cypher is publicly executable;
- migrations, backup restoration, health checks, or rollback are unverified.

## 13. Phase 8 — Deployment

### Artifacts

- Multi-stage backend Dockerfile.
- Multi-stage frontend build served through a production web server or static host.
- Separate worker image/command using the same backend package.
- Docker Compose environment for local integration testing.
- Database migrations executed as a release job.
- CI workflow for linting, tests, builds, security scans, and image publication.
- CD workflow with staging deployment, smoke tests, approval, production deployment, and rollback.

### Recommended Managed Topology

- Static frontend/CDN.
- Containerized FastAPI API with at least two workers when load requires it.
- Separate background worker and scheduler.
- Managed PostgreSQL and Redis.
- Neo4j Aura or another managed Neo4j deployment.
- Managed vector service for production, behind the vector adapter.
- Object storage for policy PDFs and raw approved-source snapshots.
- One public domain with `/api` reverse-proxied to the backend where possible.

The provider-neutral Docker setup is implemented first; the final cloud vendor depends on budget and region requirements.

## 14. Delivery Sequence

| Milestone | Demonstrable result |
| --- | --- |
| M0 — Foundation | Unified app, settings, PostgreSQL/Redis, migrations, containers |
| M1 — Live Search | Duffel test offers, normalization, caching, direct search UI |
| M2 — Safe Booking | Repricing, policy quote, approval boundary, test order flow |
| M3 — Intelligence | Approved scrapers, Hybrid RAG fusion, citations, evaluation |
| M4 — Experience | Progressive UI, streaming trace, accessibility, performance budgets |
| M5 — Production | Auth, observability, CI/CD, staging, security/load tests, runbooks |
| M6 — Live Release | Live provider approval, controlled rollout, monitoring, rollback proof |

A realistic solo implementation is approximately five to eight weeks, depending mainly on provider onboarding, real-booking scope, scraper approvals, and hosting requirements.

## 15. Definition of Done

The project is production-ready only when:

- live prices come from the configured provider and include provenance and freshness metadata;
- selected offers are repriced before confirmation;
- production never substitutes mock fares or PNRs;
- approved scrapers run independently with traceable, deduplicated output;
- Hybrid RAG answers include citations and pass the evaluation suite;
- initial flight results do not wait for LLM reasoning;
- the UI is responsive, accessible, and explicit about price state;
- authentication, authorization, rate limits, audit logging, and Cypher restrictions are active;
- automated tests and performance/security gates pass;
- staging and production deploy from reproducible containers with migrations, monitoring, backups, and rollback.

## 16. Decisions Required Before Phase 1

1. **Commercial scope:** live search and redirect, or in-application order creation?
2. **Provider:** Duffel, Skyscanner, Amadeus, or an existing corporate/GDS account?
3. **Hosting budget and region:** free/portfolio deployment, low-cost production, or enterprise deployment?
4. **Identity:** project-local accounts or an existing corporate OIDC provider?
5. **Scraping sources:** exact domains approved for automated ingestion?

Recommended starting answers are Duffel test-mode search, order creation behind a disabled feature flag, low-cost managed hosting, project-local authentication for staging, and two official advisory sources approved before scraper implementation.
