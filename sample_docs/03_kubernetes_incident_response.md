# EKS Kubernetes Incident Response Standard Operating Procedure

## Document Information
- **Owner**: Kubernetes Platform Engineering
- **Document ID**: SOP-K8S-092
- **Cluster**: `eks-production-east-01`
- **Revision**: 3.4

---

## 1. CrashLoopBackOff Triage
When pods enter `CrashLoopBackOff`, execute the following diagnostic sequence:

### Step 1: Capture Terminated Container Logs
```bash
kubectl logs -n core-services <pod-name> --previous --tail=100
```
Inspect for unhandled fatal runtime exceptions, missing environment variables, or database connection pool exhaustion.

### Step 2: Describe Pod Events
```bash
kubectl describe pod -n core-services <pod-name>
```
Look for `Liveness probe failed` or `Readiness probe failed` HTTP 500 error responses.

---

## 2. OOMKilled (Exit Code 137) Remediation
If container exit code is `137`, the container was terminated by the Linux kernel Out-Of-Memory (OOM) killer.

### Remediation Protocol:
1. Verify memory limits in Deployment specification:
   ```bash
   kubectl get deployment -n core-services <deployment-name> -o jsonpath='{.spec.template.spec.containers[*].resources}'
   ```
2. Temporary Emergency Patch: Increase memory limit by 50% using `kubectl patch`:
   ```bash
   kubectl patch deployment -n core-services <deployment-name> -p '{"spec":{"template":{"spec":{"containers":[{"name":"app","resources":{"limits":{"memory":"4Gi"}}}]}}}}'
   ```
3. Take heap dump prior to pod restart if memory profiling profiler sidecar is enabled.

---

## 3. Worker Node Draining and Maintenance
When a worker node experiences disk pressure or hardware degradation:

1. **Cordon the Node**: Prevent new pods from scheduling onto the target node:
   ```bash
   kubectl cordon <node-name>
   ```
2. **Drain the Node**: Safely evict running workloads respecting Pod Disruption Budgets (PDB):
   ```bash
   kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data --timeout=180s
   ```
3. **Terminate Instance**: Terminate underlying EC2 instance via AWS Auto Scaling Group; ASG will automatically launch a healthy replacement node.
