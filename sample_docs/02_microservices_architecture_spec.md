# Enterprise Microservices Architecture Specification

## Document Information
- **Owner**: Cloud Architecture & Infrastructure Engineering
- **Document ID**: SPEC-ARCH-2026-04
- **Classification**: Internal Engineering Standard
- **Status**: Approved / In Production

---

## 1. Authentication and Authorization Protocol
All inbound external traffic must authenticate through Amazon Cognito User Pools before reaching backend microservices.

### Token Specifications
- **Format**: JSON Web Token (JWT) RS256 signed.
- **Header**: Standard `Authorization: Bearer <id_or_access_token>`.
- **Token Expiry**: Access tokens expire in 60 minutes; refresh tokens expire in 30 days.
- **Claims Verification**: Microservices must validate token issuer (`iss`), client ID (`aud`), and user groups claim (`cognito:groups`).
- **Group Hierarchy**:
  - `Admins`: Full administrative rights, schema migrations, and index deletion.
  - `Engineers`: Read-write access to application endpoints and runbook execution.
  - `Auditors`: Read-only access to log streams and compliance audit reports.

---

## 2. API Gateway and Rate Limiting
Public requests enter through Amazon API Gateway configured with regional endpoints:

- **Throttling Policy**: Default rate of 2,000 requests per second (RPS) with a burst limit of 5,000 RPS per tenant.
- **Circuit Breaker**: Outbound calls to third-party providers must use Envoy circuit breaker rules tripping at 25% consecutive 5xx errors within 10 seconds.
- **CORS Policy**: Restrict cross-origin headers to verified internal domains (`*.internal.corp`).

---

## 3. Inter-Service Communication
Internal communications between services utilize mutual TLS (mTLS) with AWS App Mesh and gRPC protocols:
- **Default Timeout**: 3,000 ms for synchronous queries.
- **Retry Policy**: Exponential backoff with jitter up to 3 retry attempts for idempotent GET operations. Non-idempotent POST requests must not automatically retry without an idempotency key header (`X-Idempotency-Key`).
- **Distributed Tracing**: All requests must propagate AWS X-Ray trace headers (`X-Amzn-Trace-Id`).

---

## 4. Disaster Recovery Objectives
- **Recovery Point Objective (RPO)**: < 5 minutes for stateful transactional data.
- **Recovery Time Objective (RTO)**: < 15 minutes for complete regional failover.
- **Backup Retention**: Automated daily backups retained for 90 days in Amazon S3 Glacier Flexible Retrieval with Object Lock compliance mode.
