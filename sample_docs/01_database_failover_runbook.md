# Aurora PostgreSQL Multi-AZ Database Failover Runbook

## Document Information
- **Owner**: Site Reliability Engineering (SRE) / Data Platform Team
- **Document ID**: RUNBOOK-DB-001
- **Classification**: Internal Confidential
- **Last Verified**: 2026-10-15

---

## 1. Overview and Incident Criteria
This runbook defines the emergency operational procedure for handling primary database failures, replication lag spikes, and forced regional Multi-AZ failovers for the core transactional Aurora PostgreSQL cluster (`aurora-prod-cluster-01`).

### Trigger Conditions
- High severity alerts (`DBPrimaryUnreachable`, `AuroraEngineHang`, or `ReplicationLagExceeded`).
- Primary writer node CPU utilization exceeds 98% for > 5 consecutive minutes without auto-recovery.
- Unscheduled storage failover indicated in AWS Health Dashboard / CloudWatch.

---

## 2. Pre-Failover Health Checks
Before triggering an automated or manual failover, the on-call engineer must verify:

1. **Replication Lag Check**: Ensure the target read replica has `AuroraReplicaLag` under 100 milliseconds.
   ```bash
   aws rds describe-db-clusters \
     --db-cluster-identifier aurora-prod-cluster-01 \
     --query 'DBClusters[0].DBClusterMembers'
   ```
2. **Connection State**: Inspect active client connections via PgBouncer:
   ```bash
   psql -h pgbouncer.internal.corp -p 6432 -U pgbouncer_admin -c "SHOW POOLS;"
   ```
3. **Target Read Replica Status**: Confirm that `aurora-prod-replica-02` (in Availability Zone `us-east-1b`) is in status `available`.

---

## 3. Step-by-Step Failover Procedure

### Step 3.1: Trigger Controlled Cluster Failover
Initiate cluster failover to promote the selected read replica to writer:
```bash
aws rds failover-db-cluster \
  --db-cluster-identifier aurora-prod-cluster-01 \
  --target-db-instance-identifier aurora-prod-replica-02
```

### Step 3.2: Verify Replica Promotion
Monitor cluster state transitions until the target instance role switches to `writer`:
```bash
aws rds describe-db-instances \
  --db-instance-identifier aurora-prod-replica-02 \
  --query 'DBInstances[0].DBInstanceStatus'
```
*Expected transition duration: 25 to 45 seconds.*

### Step 3.3: Drain and Reload Connection Pools
Once DNS propagation completes for the cluster writer endpoint:
1. Reload PgBouncer connection pools to flush stale socket file descriptors:
   ```bash
   psql -h pgbouncer.internal.corp -p 6432 -U pgbouncer_admin -c "RELOAD; RESUME;"
   ```
2. Validate application health check endpoints return HTTP 200:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" https://api.internal.corp/health/db
   ```

---

## 4. Post-Failover Verification and Escalation
1. Confirm write transactions are committing by checking CloudWatch metric `WriteThroughput`.
2. Ensure automated snapshot is initiated post-failover.
3. Post notification to `#incident-prod` on Slack with the failover timestamp, old primary identifier, and new primary identifier.
4. If failover exceeds 180 seconds or replica does not assume writer status, immediately page the Tier-3 Database Architect via PagerDuty.
