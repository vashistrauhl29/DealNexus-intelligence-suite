# SOC2 Security Specifications

## Overview

This document defines the mandatory security framework for all Glean implementations, with particular emphasis on Custom Build engagements involving client-controlled data sources. All agents must reference these specifications when assessing deals that involve sensitive data, legacy systems, or custom integrations.

**Compliance Standard:** SOC 2 Type II
**Framework Version:** 1.0
**Last Updated:** 2026-01-16
**Owner:** Legal Counsel Agent + Technical PM Agent

---

## Four-Point Security Framework

All Custom Build implementations MUST adhere to the following four security principles:

---

### 1. Least Privilege Access

**Principle:** Grant only the minimum permissions necessary to perform required functions.

**Requirements:**

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| Role-Based Access Control (RBAC) | Define granular roles matching job functions | Security review |
| Service Account Isolation | Dedicated service accounts per integration | Credential audit |
| No Shared Credentials | Each system component uses unique credentials | Vault inspection |
| Time-Bound Access | Temporary credentials with automatic expiration | Token policy |

**For Custom Connectors:**
- Glean service account MUST have read-only access to data sources
- Service account MUST be isolated from production user accounts
- Service account credentials MUST be rotated every 90 days
- Access scope MUST be limited to specific tables/views required for indexing

**Implementation Pattern:**
```
[Glean Connector] --> [Isolated Service Account] --> [Filtered SQL View]
                              |
                              +-- Read-only permissions
                              +-- No access to PII tables
                              +-- Audit logging enabled
```

---

### 2. Data Minimization

**Principle:** Collect and process only the data strictly necessary for the stated purpose.

**Requirements:**

| Requirement | Implementation | Verification |
|-------------|----------------|--------------|
| Purpose Limitation | Document specific use case for each data element | Data mapping |
| Collection Boundaries | Define explicit inclusion/exclusion lists | Schema review |
| Retention Limits | Establish data lifecycle policies | Retention audit |
| PII Exclusion | Exclude personal data unless explicitly required | Privacy review |

**For Custom Connectors:**

- **Filtered SQL Views:** Client MUST create database views that exclude:
  - Employee personal information (SSN, DOB, home address)
  - Payroll and compensation data
  - Health and medical records
  - Financial account numbers
  - Authentication credentials

- **Schema Documentation:** Client MUST provide:
  - Complete list of tables/columns to be indexed
  - Explicit exclusion list for sensitive fields
  - Data classification for each included field

**Filtered SQL View Pattern:**
```sql
-- REQUIRED: Client creates filtered view
CREATE VIEW glean_safe_shipping_data AS
SELECT
    shipment_id,
    tracking_number,
    origin_port,
    destination_port,
    customs_status,
    resolution_notes,
    created_at,
    updated_at
FROM shipping_records
-- EXCLUDE: employee_id, handler_ssn, salary_grade, personal_notes
WHERE data_classification != 'RESTRICTED';
```

---

### 3. Encryption Standards

**Principle:** Protect data confidentiality through encryption at rest and in transit.

**Requirements:**

| Requirement | Standard | Implementation |
|-------------|----------|----------------|
| Data in Transit | TLS 1.3 minimum | All API/SQL connections |
| Data at Rest | AES-256 | Glean index storage |
| Key Management | HSM-backed | Cloud KMS integration |
| Certificate Management | Auto-renewal | 90-day rotation |

**Network Security Requirements:**

| Component | Requirement | Specification |
|-----------|-------------|---------------|
| **VPN/PrivateLink** | MANDATORY for Custom Builds | AWS PrivateLink, Azure Private Link, or GCP Private Service Connect |
| IP Allowlisting | Required | Client firewall must allowlist Glean egress IPs |
| mTLS | Recommended | Mutual TLS for high-sensitivity integrations |
| Network Segmentation | Required | Custom connector in isolated network segment |

**Connection Architecture:**
```
[Glean Cloud] <--TLS 1.3--> [VPN/PrivateLink] <--TLS 1.3--> [Client Network]
                                   |
                                   +-- No public internet exposure
                                   +-- Encrypted tunnel
                                   +-- IP-restricted access
```

**VPN/PrivateLink Requirements for Custom Builds:**
- All custom connector traffic MUST traverse private network connection
- Public internet exposure of client databases is PROHIBITED
- Client MUST provision PrivateLink endpoint or VPN tunnel
- Glean MUST connect exclusively via private endpoint

---

### 4. Auditability

**Principle:** Maintain comprehensive logs enabling security monitoring, incident response, and compliance verification.

**Requirements:**

| Requirement | Retention | Format |
|-------------|-----------|--------|
| Access Logs | 1 year minimum | Structured JSON |
| Query Logs | 1 year minimum | Structured JSON |
| Authentication Events | 2 years | SIEM-compatible |
| Configuration Changes | 2 years | Immutable log |

**Audit Log Schema:**
```json
{
  "timestamp": "ISO-8601",
  "event_type": "DATA_ACCESS | AUTH | CONFIG_CHANGE | ERROR",
  "actor": {
    "service_account": "glean-connector-prod",
    "source_ip": "10.0.0.x",
    "session_id": "uuid"
  },
  "resource": {
    "type": "SQL_VIEW | TABLE | API_ENDPOINT",
    "name": "glean_safe_shipping_data",
    "database": "logibase_prod"
  },
  "action": "SELECT | CONNECT | DISCONNECT",
  "row_count": 1500,
  "duration_ms": 234,
  "status": "SUCCESS | FAILURE",
  "client_request_id": "uuid"
}
```

**Audit Requirements for Custom Builds:**
- All Glean queries to client systems MUST be logged
- Logs MUST include: timestamp, query, row count, duration, service account
- Client MUST have access to query audit logs
- Anomaly detection MUST alert on unusual access patterns
- Quarterly access reviews MUST be conducted

---

## Custom Build Security Checklist

Before any Custom Build connector can proceed to development, the following MUST be verified:

### Pre-Development Security Review

- [ ] **Least Privilege**
  - [ ] Isolated service account created
  - [ ] Read-only permissions verified
  - [ ] Access scope limited to required views only
  - [ ] Credential rotation policy established (90-day)

- [ ] **Data Minimization**
  - [ ] Filtered SQL View created by client IT
  - [ ] PII/sensitive columns excluded at source
  - [ ] Data classification documented
  - [ ] Inclusion/exclusion list approved by Legal

- [ ] **Encryption**
  - [ ] VPN or PrivateLink provisioned
  - [ ] TLS 1.3 verified on all connections
  - [ ] No public internet database exposure
  - [ ] Certificate management in place

- [ ] **Auditability**
  - [ ] Query logging enabled on client database
  - [ ] Glean audit logs configured
  - [ ] Log retention policy (1 year minimum)
  - [ ] Access review schedule established (quarterly)

---

## Compliance Mapping

| SOC2 Trust Principle | Framework Mapping |
|----------------------|-------------------|
| Security | Least Privilege, Encryption |
| Availability | Service Account Isolation, VPN redundancy |
| Processing Integrity | Data Minimization, Audit Logging |
| Confidentiality | Encryption, Data Minimization |
| Privacy | Data Minimization, Least Privilege |

---

## Reference Integration: Filtered SQL View Strategy

For legacy databases without REST APIs (e.g., LogiBase), the Filtered SQL View strategy provides SOC2-compliant data access:

**Architecture:**
```
┌─────────────────────────────────────────────────────────────────┐
│                     CLIENT NETWORK (Private)                     │
│  ┌──────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  LogiBase    │───▶│ Filtered SQL View │◀───│ Glean Service │  │
│  │  (Full DB)   │    │ (Shipping Only)   │    │   Account     │  │
│  │              │    │                    │    │ (Read-Only)   │  │
│  │ - Shipping   │    │ EXCLUDES:          │    │               │  │
│  │ - Payroll    │    │ - Payroll tables   │    │ Permissions:  │  │
│  │ - Employee   │    │ - PII columns      │    │ - SELECT only │  │
│  │   PII        │    │ - Credentials      │    │ - View access │  │
│  └──────────────┘    └──────────────────┘    └───────────────┘  │
│                              │                        │          │
│                              │                        │          │
│                     ┌────────▼────────────────────────▼───────┐  │
│                     │         VPN / PrivateLink               │  │
│                     │    (Encrypted Private Connection)       │  │
│                     └────────────────────────────────────────┬┘  │
└──────────────────────────────────────────────────────────────┼──┘
                                                               │
                                                    TLS 1.3    │
                                                               │
┌──────────────────────────────────────────────────────────────▼──┐
│                      GLEAN CLOUD                                 │
│  ┌──────────────────┐    ┌──────────────────┐                   │
│  │ Custom Connector │───▶│   Search Index   │                   │
│  │ (SQL Adapter)    │    │ (Encrypted AES)  │                   │
│  └──────────────────┘    └──────────────────┘                   │
└──────────────────────────────────────────────────────────────────┘
```

**Key Security Controls:**
1. **Service Account Isolation:** Dedicated `glean-logibase-readonly` account
2. **VPN/PrivateLink:** No public internet exposure of LogiBase
3. **Filtered View:** Client IT excludes PII at database level
4. **Audit Trail:** All queries logged with full attribution

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-16 | Legal Counsel Agent | Initial framework |

---

*This document is referenced by: GOVERNANCE_RULES.md, orchestrator_manifest.json*
*Required for: All Custom Build assessments*
