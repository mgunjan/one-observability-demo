# Demo Scenarios for DevOps Agent

This document provides detailed scenarios for demonstrating the AWS DevOps Agent and Prometheus MCP integration.

## Scenario 1: Memory Leak Detection and Resolution

### Overview
Demonstrate automated detection and resolution of a memory leak in the `petadoptionshistory-py` service.

### Setup

1. Ensure the Pet Adoptions application is running normally
2. Verify baseline metrics in Grafana
3. Confirm Slack notifications are working

### Execution Steps

#### Step 1: Inject Memory Leak

```bash
# Navigate to chaos engineering directory
cd chaos-engineering/scenarios

# Apply memory leak scenario
kubectl apply -f memory-leak-petadoptionshistory.yaml

# Verify the chaos pod is running
kubectl get pods -n default | grep memory-leak
```

#### Step 2: Observe Initial Metrics

```bash
# Watch memory usage increase
kubectl top pod -n default | grep petadoptionshistory

# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace ContainerInsights \
  --metric-name pod_memory_utilization \
  --dimensions Name=PodName,Value=petadoptionshistory-py-xxx \
  --start-time $(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 60 \
  --statistics Average
```

**Expected Timeline:**
- **T+0:** Memory leak injection starts
- **T+2min:** Memory usage at 40%
- **T+4min:** Memory usage at 70%
- **T+6min:** Memory usage at 85% - Alarm triggers

#### Step 3: Alarm Triggers

**CloudWatch Alarm fires when memory > 85%**

```bash
# Verify alarm state
aws cloudwatch describe-alarms \
  --alarm-names "PetAdoptionsHistory-HighMemory"
```

#### Step 4: Agent Investigation

**Watch the DevOps Agent work in real-time:**

```bash
# Follow agent logs
kubectl logs -f -n devops-agent -l app=devops-agent
```

**Expected Agent Actions:**
1. Receives alarm via EventBridge
2. Identifies the problematic pod
3. Queries Prometheus for memory trend
4. Detects increasing memory pattern
5. Checks for OOMKill events
6. Reviews recent deployments
7. Generates root cause analysis

#### Step 5: Slack Notifications

**You should receive Slack notifications:**

1. **Initial Alert (T+6min)**
   ```
   🚨 New incident detected: INC-abc12345
   Source: aws.cloudwatch
   Priority: HIGH
   
   Pod: petadoptionshistory-py-xxx
   Memory Usage: 87%
   ```

2. **Investigation Update (T+7min)**
   ```
   🔍 Investigating incident: INC-abc12345
   
   Findings:
   - Memory usage increasing steadily
   - Current: 450MB / 512MB limit
   - Trend: +50MB every 2 minutes
   - No recent deployments
   ```

3. **Root Cause (T+7.5min)**
   ```
   ✅ Root cause identified: INC-abc12345
   
   Cause: Memory leak detected
   - Memory growth rate: 25MB/min
   - Estimated time to OOMKill: 3 minutes
   - No OOMKill events yet
   
   Recommendations:
   1. Restart pod to clear memory
   2. Increase memory limit to 1Gi
   3. Enable memory profiling
   4. Review application code
   ```

4. **Resolution (T+8min - if auto-remediation enabled)**
   ```
   🔧 Applying remediation: INC-abc12345
   
   Action: Pod restart initiated
   Pod: petadoptionshistory-py-xxx deleted
   New pod: petadoptionshistory-py-yyy created
   Status: Healthy
   ```

#### Step 6: Verify Resolution

```bash
# Check new pod status
kubectl get pods -n default | grep petadoptionshistory

# Verify memory usage is back to normal
kubectl top pod -n default | grep petadoptionshistory

# Check application is responding
curl http://<service-endpoint>/api/health
```

#### Step 7: Cleanup

```bash
# Remove memory leak injection
kubectl delete -f memory-leak-petadoptionshistory.yaml

# Verify services are stable
kubectl get pods -n default
```

### Success Criteria

- ✅ Memory leak detected within 30 seconds of alarm
- ✅ Root cause identified within 2 minutes
- ✅ Remediation recommended with confidence score > 80%
- ✅ Service availability maintained throughout
- ✅ All Slack notifications delivered
- ✅ Total MTTR < 2 minutes

### Demo Script

**Narrator:**
> "We're now going to simulate a memory leak in our Python service. This is a common issue that typically takes 10-15 minutes to diagnose manually. Let's see how our DevOps Agent handles it."

[Inject chaos]

> "I've triggered the memory leak. Notice the memory usage climbing in Grafana. Within a few minutes, we'll hit our alarm threshold."

[Wait for alarm - 6 minutes]

> "There's the alarm! Watch what happens next. The DevOps Agent receives the event via EventBridge..."

[Show Slack notification]

> "First notification in Slack - incident detected. Now the agent is investigating by querying multiple data sources: CloudWatch Container Insights, Prometheus, Kubernetes API..."

[Show investigation logs]

> "Notice how it's using natural language to query Prometheus: 'Show me memory usage for pod petadoptionshistory-py over the last hour.' The Prometheus MCP server translates this to PromQL and returns the results."

[Show root cause notification]

> "There's the root cause! Memory leak identified with an increasing trend. Look at the actionable recommendations - restart the pod, increase limits, enable profiling. Total investigation time: under 2 minutes."

---

## Scenario 2: CPU Throttling and Latency Spike

### Overview
Demonstrate detection and resolution of CPU throttling causing high latency in `payforadoption-go` service.

### Setup

1. Configure latency alerts (P99 > 1000ms)
2. Verify X-Ray tracing is active
3. Ensure HPA is configured

### Execution Steps

#### Step 1: Inject CPU Stress

```bash
kubectl apply -f cpu-stress-payforadoption.yaml
```

#### Step 2: Generate Load

```bash
# Use the traffic generator
kubectl exec -it traffic-generator-xxx -- /bin/bash
./generate-traffic.sh --service payforadoption --rate 100rps
```

**Expected Timeline:**
- **T+0:** CPU stress starts
- **T+1min:** CPU usage at 90%
- **T+2min:** Latency increases to 800ms
- **T+3min:** Latency > 1000ms - Alarm triggers
- **T+4min:** CPU throttling detected

#### Step 3: Agent Investigation

**Agent Actions:**
1. Identifies high latency via CloudWatch
2. Analyzes X-Ray traces for slow requests
3. Queries Prometheus for CPU metrics
4. Detects CPU throttling
5. Correlates latency with resource constraints
6. Checks HPA configuration

**Slack Notifications:**

1. **Alert:**
   ```
   🚨 High latency detected: INC-def45678
   Service: payforadoption-go
   P99 Latency: 1250ms (threshold: 1000ms)
   ```

2. **Investigation:**
   ```
   🔍 Analyzing traces and metrics...
   
   Findings:
   - 80% of requests > 1000ms
   - CPU usage: 95% (throttled)
   - CPU limit: 200m
   - No downstream service issues
   - HPA: Current 2/2 pods (max reached)
   ```

3. **Root Cause:**
   ```
   ✅ Root cause: CPU throttling
   
   Latency spike caused by insufficient CPU resources.
   Service is at max HPA replicas (2) and each pod is 
   CPU throttled.
   
   Recommendations:
   1. Increase CPU limit to 500m
   2. Increase HPA max replicas to 5
   3. Consider vertical pod autoscaling
   ```

#### Step 4: Apply Remediation

If auto-remediation is enabled:

```bash
# Agent increases CPU limits
kubectl patch deployment payforadoption-go -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"payforadoption","resources":{"limits":{"cpu":"500m"}}}]}}}}'

# Agent updates HPA
kubectl patch hpa payforadoption-go -p \
  '{"spec":{"maxReplicas":5}}'
```

#### Step 5: Verify Resolution

```bash
# Check new pods with higher limits
kubectl describe pod payforadoption-go-xxx | grep -A 2 Limits

# Verify HPA scaled up
kubectl get hpa payforadoption-go

# Check latency improved
# (Check Grafana or X-Ray ServiceLens)
```

### Success Criteria

- ✅ High latency detected within 30 seconds
- ✅ CPU throttling identified as root cause
- ✅ Correlation between CPU and latency established
- ✅ Remediation applied within 1 minute
- ✅ Latency returns to normal < 500ms
- ✅ Total MTTR < 3 minutes

---

## Scenario 3: Node Pressure and Pod Evictions

### Overview
Demonstrate handling of node resource pressure causing multiple pod evictions.

### Setup

1. Identify a node with available capacity
2. Configure node pressure alerts
3. Verify pod disruption budgets

### Execution Steps

#### Step 1: Inject Node Pressure

```bash
# Apply node stress
kubectl apply -f node-pressure-scenario.yaml

# This deploys a stress pod that consumes node resources
```

**Expected Timeline:**
- **T+0:** Node stress starts
- **T+2min:** Node memory at 85%
- **T+4min:** Node MemoryPressure condition
- **T+5min:** Pod evictions begin
- **T+6min:** Alarm triggers

#### Step 2: Agent Investigation

**Agent Actions:**
1. Detects node pressure alarm
2. Identifies affected node
3. Lists all pods on node
4. Checks resource usage per pod
5. Reviews eviction events
6. Identifies resource-intensive pods

**Slack Notifications:**

1. **Alert:**
   ```
   🚨 Node pressure detected: INC-ghi78901
   Node: ip-10-0-1-123.ec2.internal
   Condition: MemoryPressure
   Pods affected: 8
   ```

2. **Investigation:**
   ```
   🔍 Analyzing node resources...
   
   Findings:
   - Node memory: 28GB / 32GB (87%)
   - Evicted pods: 3
   - Largest consumers:
     1. elasticsearch-0: 8GB
     2. analytics-worker: 6GB
     3. petadoptionshistory-py: 2GB
   
   - Recent changes: elasticsearch scaled to 3 replicas
   ```

3. **Root Cause:**
   ```
   ✅ Root cause: Node capacity exceeded
   
   Recent scaling of elasticsearch consumed additional 8GB,
   pushing node over capacity. Multiple pods evicted.
   
   Recommendations:
   1. Cordon node to prevent new scheduling
   2. Drain non-critical pods to other nodes
   3. Add new node to cluster
   4. Review resource requests/limits
   5. Consider node affinity rules
   ```

#### Step 3: Remediation

```bash
# Agent cordons the node
kubectl cordon ip-10-0-1-123.ec2.internal

# Gracefully drains pods
kubectl drain ip-10-0-1-123.ec2.internal \
  --ignore-daemonsets \
  --delete-emptydir-data \
  --grace-period=300

# Pods reschedule on healthy nodes
```

#### Step 4: Verify Resolution

```bash
# Check node status
kubectl get nodes

# Verify pods rescheduled
kubectl get pods -o wide | grep -v ip-10-0-1-123

# Check services are healthy
curl http://<service-endpoints>/health
```

### Success Criteria

- ✅ Node pressure detected immediately
- ✅ All affected pods identified
- ✅ Resource hogs found within 1 minute
- ✅ Safe remediation plan generated
- ✅ Zero downtime for critical services
- ✅ Total MTTR < 3 minutes

---

## Metrics Collection

### Baseline vs. Incident Metrics

| Metric | Baseline | During Incident | After Resolution |
|--------|----------|-----------------|------------------|
| MTTR | 10-15 min | N/A | < 2 min |
| Detection Time | 5-8 min | 20-30 sec | 20-30 sec |
| Investigation Time | 5-10 min | 30-90 sec | 30-90 sec |
| Resolution Time | 2-5 min | 30-60 sec | 30-60 sec |
| False Positives | 15-20% | 5% | 5% |
| Service Availability | 99.5% | 99.9% | 99.9% |

---

## Demo Tips

### Before the Demo

1. **Prepare the environment:**
   - Deploy all services
   - Verify monitoring is working
   - Test Slack notifications
   - Clear old alarms

2. **Test scenarios individually:**
   - Run each scenario at least once
   - Time the workflows
   - Verify all integrations

3. **Prepare talking points:**
   - Baseline manual process
   - MTTR improvements
   - Cost savings

### During the Demo

1. **Show the manual process first:**
   - Open multiple consoles
   - Show complexity of troubleshooting
   - Emphasize time and expertise required

2. **Run the automated scenario:**
   - Narrate what's happening
   - Show Slack notifications in real-time
   - Explain each investigation step

3. **Highlight key features:**
   - Natural language queries
   - Multi-source correlation
   - Intelligent recommendations

### After the Demo

1. **Show metrics:**
   - MTTR comparison dashboard
   - Cost savings calculation
   - Success rate statistics

2. **Q&A preparation:**
   - How to customize workflows?
   - Can it handle X scenario?
   - What about compliance/audit?
   - Integration with existing tools?

---

## Troubleshooting Demo Issues

### Alarm Doesn't Fire

```bash
# Manually trigger alarm for demo
aws cloudwatch set-alarm-state \
  --alarm-name "PetAdoptionsHistory-HighMemory" \
  --state-value ALARM \
  --state-reason "Demo trigger"
```

### Agent Doesn't Respond

```bash
# Check agent logs
kubectl logs -n devops-agent -l app=devops-agent --tail=50

# Verify EventBridge rule
aws events list-targets-by-rule --rule devops-agent-cloudwatch-alarms

# Check SQS queue
aws sqs get-queue-attributes \
  --queue-url <queue-url> \
  --attribute-names ApproximateNumberOfMessages
```

### Slack Notifications Missing

```bash
# Test Slack integration
kubectl exec -n devops-agent devops-agent-xxx -- \
  python -c "from src.integrations.slack import SlackIntegration; \
  slack = SlackIntegration(); \
  slack.send_notification('#eks-incidents', 'Test message', 'info')"
```

---

## Next Steps

After completing these scenarios:
1. Customize workflows for your environment
2. Add organization-specific playbooks
3. Enable auto-remediation (with approvals)
4. Integrate with ITSM tools
5. Set up alerting rules
