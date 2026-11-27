# Cloud Security & SOC-2 Type II Compliance Standards

## Document Information
- **Owner**: Information Security & Compliance Office
- **Document ID**: SEC-STD-SOC2-401
- **Applicability**: All Production Environments & AWS Infrastructure

---

## 1. Data Encryption at Rest and in Transit
- **Encryption at Rest**:
  - All Amazon S3 buckets, Amazon EBS volumes, and DynamoDB tables must enforce AES-256 or AWS KMS customer-managed keys (CMK) with automated annual key rotation.
  - S3 bucket policies must include `DenyUnEncryptedObjectUploads` condition.
- **Encryption in Transit**:
  - Minimum TLS 1.3 for external communication; TLS 1.2 allowed for internal legacy endpoints with strong cipher suites (`ECDHE-RSA-AES256-GCM-SHA384`).
  - Cleartext HTTP (port 80) is prohibited and must redirect automatically to HTTPS (port 443).

---

## 2. Least Privilege Access Control & IAM
- **Root Account Usage**: The AWS root account is reserved exclusively for billing and account closure. Root access keys are permanently prohibited.
- **IAM Policies**: Wildcard actions (`"Action": "*"`) are forbidden in all IAM policies.
- **Role Session Duration**: Maximum temporary credential duration for STS AssumeRole is capped at 1 hour (3600 seconds).
- **MFA Enforcement**: Hardware or TOTP Multi-Factor Authentication is mandatory for all console users and CLI assume-role policies.

---

## 3. Audit Logging and Security Monitoring
- **AWS CloudTrail**: Multi-region trail enabled with log file validation and immutable delivery to an isolated security audit S3 bucket with Object Lock compliance.
- **Log Retention**: Audit logs must be retained for a minimum of 365 days (1 year) to comply with SOC-2 Trust Services Criteria CC6.1.
- **Incident Escalation**: Any detection of unauthorized IAM role creation or security group opening port 22/3389 to `0.0.0.0/0` triggers an automated P1 incident ticket sent to the SOC security team within 15 minutes.
