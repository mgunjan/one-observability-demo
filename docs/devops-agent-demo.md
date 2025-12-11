# AWS DevOps Agent and Prometheus MCP Demo

## Overview

This demo showcases the AWS DevOps Agent and Prometheus MCP Server integration for automated incident detection, investigation, and remediation in Amazon EKS clusters.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EKS Cluster                              │
│                                                                  │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐ │
│  │  Pet Site    │      │ PetSearch    │      │PayForAdoption│ │
│  │  (Frontend)  │─────▶│   (Java)     │─────▶│    (Go)      │ │
│  └──────────────┘      └──────────────┘      └──────────────┘ │
│         │                      │                      │         │
│         └──────────────────────┴──────────────────────┘         │
│                                │                                │
│                    ┌───────────▼───────────┐                   │
│                    │  DevOps Agent         │                   │
│                    │  - Event Processing   │                   │
│                    │  - Workflow Engine    │                   │
│                    │  - Integrations       │                   │
│                    └───────────┬───────────┘                   │
│                                │                                │
│                    ┌───────────▼───────────┐                   │
│                    │ Prometheus MCP Server │                   │
│                    │  - Query Translation  │                   │
│                    │  - Natural Language   │                   │
│                    └───────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼──────┐ ┌─────▼─────┐ ┌─────▼──────┐
        │  CloudWatch  │ │    AMP    │ │   X-Ray    │
        │   Container  │ │(Prometheus)│ │  (Traces)  │
        │   Insights   │ └───────────┘ └────────────┘
        └──────────────┘
                │
        ┌───────▼───────┐
        │ EventBridge   │
        │   (Alarms)    │
        └───────────────┘
                │
        ┌───────▼───────┐
        │    Slack      │
        │(Notifications)│
        └───────────────┘
```

## Key Features

### 1. Automated Incident Detection
- CloudWatch alarms trigger EventBridge events
- DevOps Agent receives and prioritizes incidents
- Automatic classification based on alarm patterns

### 2. Intelligent Investigation
- Multi-source data correlation (metrics, logs, traces)
- Natural language queries to Prometheus via MCP
- Root cause analysis using investigation workflows

### 3. Remediation Recommendations
- Context-aware remediation suggestions
- Safety checks before execution
- Approval workflows via Slack

### 4. Real-time Notifications
- Slack integration for incident updates
- Rich message formatting with context
- Interactive buttons for approvals
- Links to Grafana dashboards

## Demo Scenarios

### Scenario 1: Memory Leak in petadoptionshistory-py

**Symptoms:**
- Gradual memory increase
- OOMKill events
- Pod restarts

**Investigation Steps:**
1. Alarm triggers on high memory usage
2. Agent identifies the pod
3. Queries Prometheus for memory trend
4. Detects increasing pattern (memory leak)
5. Reviews recent deployments
6. Checks OOMKill events

**Resolution:**
- Restart pod to clear memory
- Recommend memory limit increase
- Suggest enabling memory profiling

**Expected MTTR:** < 2 minutes (vs. 10-15 minutes manual)

### Scenario 2: CPU Throttling in payforadoption-go

**Symptoms:**
- Increased latency
- CPU at limit
- Request timeouts

**Investigation Steps:**
1. Alarm triggers on high latency
2. Agent identifies service
3. Queries X-Ray for slow traces
4. Correlates with CPU metrics via Prometheus MCP
5. Detects CPU throttling
6. Checks HPA configuration

**Resolution:**
- Increase CPU limits
- Enable HPA for auto-scaling
- Scale service horizontally

**Expected MTTR:** < 2 minutes (vs. 12-18 minutes manual)

### Scenario 3: Node Pressure Event

**Symptoms:**
- Multiple pod evictions
- Node memory pressure
- Service disruptions

**Investigation Steps:**
1. Alarm triggers on node condition
2. Agent identifies affected node
3. Lists all pods on node
4. Checks resource usage per pod
5. Identifies resource hogs
6. Reviews eviction events

**Resolution:**
- Cordon node to stop new scheduling
- Drain pods gracefully to other nodes
- Recommend adding nodes to cluster

**Expected MTTR:** < 3 minutes (vs. 15-20 minutes manual)

## Demo Execution

### Prerequisites

1. EKS cluster running with Pet Adoptions application
2. CloudWatch Container Insights enabled
3. AWS Managed Prometheus (AMP) workspace configured
4. X-Ray tracing enabled
5. DevOps Agent and Prometheus MCP Server deployed
6. Slack workspace configured

### Running the Demo

#### Step 1: Verify Setup

```bash
# Check DevOps Agent status
kubectl get pods -n devops-agent

# Check Prometheus MCP Server status
kubectl get pods -n devops-agent -l app=prometheus-mcp-server

# Check Pet Adoptions services
kubectl get pods -n default
```

#### Step 2: Inject Chaos (Memory Leak)

```bash
# Apply memory leak injector
kubectl apply -f chaos-engineering/scenarios/memory-leak-scenario.yaml

# Monitor in Slack channel
# You should see incident notification within 30 seconds
```

#### Step 3: Observe Investigation

Watch in Slack as the DevOps Agent:
1. Detects the incident
2. Investigates the root cause
3. Provides detailed analysis
4. Recommends remediation

#### Step 4: Review Results

```bash
# Check pod status
kubectl get pods -n default

# View agent logs
kubectl logs -n devops-agent -l app=devops-agent

# Check Grafana dashboards
# Open the link from Slack notification
```

#### Step 5: Clean Up

```bash
# Remove chaos injection
kubectl delete -f chaos-engineering/scenarios/memory-leak-scenario.yaml

# Verify services recovered
kubectl get pods -n default
```

### Repeating for Other Scenarios

**CPU Throttling:**
```bash
kubectl apply -f chaos-engineering/scenarios/cpu-stress-scenario.yaml
```

**Node Pressure:**
```bash
kubectl apply -f chaos-engineering/scenarios/node-pressure-scenario.yaml
```

## Natural Language Queries

The Prometheus MCP Server enables natural language queries:

```python
# Example queries
"Show me memory usage for pod petadoptionshistory-py over the last hour"
"What is the CPU usage for all pods in namespace default?"
"Show me request rate for service payforadoption-go"
"Detect anomalies in memory usage"
"Compare latency across all services"
```

## Metrics Collected

### Pod Metrics
- `container_memory_usage_bytes` - Memory usage
- `container_cpu_usage_seconds_total` - CPU usage
- `container_network_receive_bytes_total` - Network RX
- `container_network_transmit_bytes_total` - Network TX
- `kube_pod_container_status_restarts_total` - Restart count

### Service Metrics
- `http_requests_total` - Request count
- `http_request_duration_seconds` - Request latency
- `http_requests_errors_total` - Error count

### Node Metrics
- `node_memory_MemAvailable_bytes` - Available memory
- `node_cpu_seconds_total` - CPU usage
- `node_disk_io_time_seconds_total` - Disk I/O

## Troubleshooting

### Agent Not Receiving Events

```bash
# Check EventBridge rules
aws events list-rules --name-prefix "devops-agent"

# Check agent logs
kubectl logs -n devops-agent -l app=devops-agent --tail=100

# Verify IRSA configuration
kubectl describe sa devops-agent -n devops-agent
```

### Prometheus MCP Not Responding

```bash
# Check MCP server status
kubectl get pods -n devops-agent -l app=prometheus-mcp-server

# Check MCP logs
kubectl logs -n devops-agent -l app=prometheus-mcp-server --tail=100

# Test MCP endpoint
kubectl port-forward -n devops-agent svc/prometheus-mcp-server 8080:8080
curl http://localhost:8080/health
```

### Slack Notifications Not Arriving

```bash
# Check Slack token in Secrets Manager
aws secretsmanager get-secret-value --secret-id devops-agent/slack-token

# Verify agent has access to Secrets Manager
# Check IAM role permissions
```

## Performance Metrics

### MTTR Comparison

| Scenario | Manual MTTR | Automated MTTR | Improvement |
|----------|-------------|----------------|-------------|
| Memory Leak | 10-15 min | < 2 min | 83% reduction |
| CPU Throttling | 12-18 min | < 2 min | 89% reduction |
| Node Pressure | 15-20 min | < 3 min | 85% reduction |

### System Performance

- **Event Detection:** < 30 seconds
- **Investigation Duration:** 30-90 seconds
- **Total MTTR:** < 3 minutes
- **Query Response Time:** < 2 seconds (Prometheus MCP)
- **Notification Delivery:** < 15 seconds

## Next Steps

1. **Customize Workflows:** Add organization-specific investigation steps
2. **Extend Integrations:** Add more data sources (APM, logging)
3. **Auto-Remediation:** Enable automatic remediation with approvals
4. **ML Integration:** Add anomaly detection and predictive analytics
5. **Custom Playbooks:** Create runbooks for common scenarios

## Additional Resources

- [AWS DevOps Agent Architecture](./architecture.md)
- [Prometheus MCP Query Guide](./prometheus-mcp-guide.md)
- [Troubleshooting Guide](./troubleshooting.md)
- [Prerequisites](./prerequisites.md)
- [Demo Scenarios](./demo-scenarios.md)
