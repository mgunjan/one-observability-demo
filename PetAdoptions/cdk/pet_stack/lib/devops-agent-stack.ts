import * as cdk from 'aws-cdk-lib';
import * as eks from 'aws-cdk-lib/aws-eks';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as ecr from 'aws-cdk-lib/aws-ecr';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import { Construct } from 'constructs';
import * as path from 'path';
import * as fs from 'fs';

export interface DevOpsAgentStackProps extends cdk.StackProps {
  cluster: eks.Cluster;
  prometheusWorkspaceId: string;
  slackWebhookUrl?: string;
  grafanaUrl?: string;
}

export class DevOpsAgentStack extends cdk.Stack {
  public readonly agentServiceAccount: eks.ServiceAccount;
  public readonly mcpServiceAccount: eks.ServiceAccount;
  public readonly eventQueue: sqs.Queue;
  
  constructor(scope: Construct, id: string, props: DevOpsAgentStackProps) {
    super(scope, id, props);

    const { cluster, prometheusWorkspaceId, slackWebhookUrl, grafanaUrl } = props;

    // =========================================================================
    // ECR Repositories
    // =========================================================================

    const devopsAgentRepo = new ecr.Repository(this, 'DevOpsAgentRepository', {
      repositoryName: 'devops-agent',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          maxImageCount: 10,
          description: 'Keep only 10 images'
        }
      ]
    });

    const prometheusMcpRepo = new ecr.Repository(this, 'PrometheusMCPRepository', {
      repositoryName: 'prometheus-mcp-server',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      imageScanOnPush: true,
      lifecycleRules: [
        {
          maxImageCount: 10,
          description: 'Keep only 10 images'
        }
      ]
    });

    // =========================================================================
    // Secrets Manager for Slack Token
    // =========================================================================

    const slackSecret = new secretsmanager.Secret(this, 'SlackBotToken', {
      secretName: 'devops-agent/slack-token',
      description: 'Slack bot token for DevOps Agent notifications',
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ 
          bot_token: slackWebhookUrl || 'REPLACE_WITH_ACTUAL_TOKEN'
        }),
        generateStringKey: 'webhook_url'
      }
    });

    // =========================================================================
    // SQS Queue for Event Processing
    // =========================================================================

    const deadLetterQueue = new sqs.Queue(this, 'EventDLQ', {
      queueName: 'devops-agent-events-dlq',
      retentionPeriod: cdk.Duration.days(14)
    });

    this.eventQueue = new sqs.Queue(this, 'EventQueue', {
      queueName: 'devops-agent-events',
      visibilityTimeout: cdk.Duration.minutes(5),
      receiveMessageWaitTime: cdk.Duration.seconds(20),
      deadLetterQueue: {
        queue: deadLetterQueue,
        maxReceiveCount: 3
      }
    });

    // =========================================================================
    // IAM Role for DevOps Agent (IRSA)
    // =========================================================================

    const agentNamespace = cluster.addManifest('DevOpsAgentNamespace', {
      apiVersion: 'v1',
      kind: 'Namespace',
      metadata: {
        name: 'devops-agent',
        labels: {
          app: 'devops-agent',
          monitoring: 'enabled'
        }
      }
    });

    this.agentServiceAccount = cluster.addServiceAccount('DevOpsAgentSA', {
      name: 'devops-agent',
      namespace: 'devops-agent'
    });

    this.agentServiceAccount.node.addDependency(agentNamespace);

    // Grant permissions to DevOps Agent
    // CloudWatch Logs and Metrics
    this.agentServiceAccount.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'cloudwatch:GetMetricStatistics',
        'cloudwatch:ListMetrics',
        'cloudwatch:GetMetricData',
        'cloudwatch:DescribeAlarms',
        'cloudwatch:DescribeAlarmsForMetric'
      ],
      resources: ['*']
    }));

    this.agentServiceAccount.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'logs:StartQuery',
        'logs:GetQueryResults',
        'logs:StopQuery',
        'logs:DescribeLogGroups',
        'logs:DescribeLogStreams',
        'logs:FilterLogEvents',
        'logs:GetLogEvents'
      ],
      resources: [
        `arn:aws:logs:${this.region}:${this.account}:log-group:/aws/containerinsights/${cluster.clusterName}/*`
      ]
    }));

    // X-Ray permissions
    this.agentServiceAccount.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'xray:GetServiceGraph',
        'xray:GetTraceSummaries',
        'xray:GetTraceGraph',
        'xray:BatchGetTraces',
        'xray:GetTimeSeriesServiceStatistics'
      ],
      resources: ['*']
    }));

    // Secrets Manager access for Slack token
    slackSecret.grantRead(this.agentServiceAccount);

    // SQS permissions
    this.eventQueue.grantConsumeMessages(this.agentServiceAccount);

    // EKS describe permissions
    this.agentServiceAccount.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'eks:DescribeCluster',
        'eks:ListClusters'
      ],
      resources: [cluster.clusterArn]
    }));

    // =========================================================================
    // IAM Role for Prometheus MCP Server (IRSA)
    // =========================================================================

    this.mcpServiceAccount = cluster.addServiceAccount('PrometheusMCPSA', {
      name: 'prometheus-mcp-server',
      namespace: 'devops-agent'
    });

    this.mcpServiceAccount.node.addDependency(agentNamespace);

    // Grant AMP permissions
    this.mcpServiceAccount.addToPrincipalPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'aps:QueryMetrics',
        'aps:GetSeries',
        'aps:GetLabels',
        'aps:GetMetricMetadata'
      ],
      resources: [
        `arn:aws:aps:${this.region}:${this.account}:workspace/${prometheusWorkspaceId}`
      ]
    }));

    // =========================================================================
    // RBAC for DevOps Agent
    // =========================================================================

    const agentClusterRole = cluster.addManifest('DevOpsAgentClusterRole', {
      apiVersion: 'rbac.authorization.k8s.io/v1',
      kind: 'ClusterRole',
      metadata: {
        name: 'devops-agent'
      },
      rules: [
        {
          apiGroups: [''],
          resources: ['pods', 'pods/log', 'pods/status', 'pods/exec'],
          verbs: ['get', 'list', 'watch', 'delete', 'create']
        },
        {
          apiGroups: [''],
          resources: ['events'],
          verbs: ['get', 'list', 'watch']
        },
        {
          apiGroups: [''],
          resources: ['nodes', 'nodes/status'],
          verbs: ['get', 'list', 'watch']
        },
        {
          apiGroups: [''],
          resources: ['services'],
          verbs: ['get', 'list', 'watch']
        },
        {
          apiGroups: ['apps'],
          resources: ['deployments', 'deployments/scale', 'statefulsets', 'statefulsets/scale', 'replicasets'],
          verbs: ['get', 'list', 'watch', 'patch', 'update']
        },
        {
          apiGroups: ['autoscaling'],
          resources: ['horizontalpodautoscalers'],
          verbs: ['get', 'list', 'watch', 'create', 'update', 'patch']
        },
        {
          apiGroups: ['metrics.k8s.io'],
          resources: ['pods', 'nodes'],
          verbs: ['get', 'list']
        }
      ]
    });

    cluster.addManifest('DevOpsAgentClusterRoleBinding', {
      apiVersion: 'rbac.authorization.k8s.io/v1',
      kind: 'ClusterRoleBinding',
      metadata: {
        name: 'devops-agent'
      },
      roleRef: {
        apiGroup: 'rbac.authorization.k8s.io',
        kind: 'ClusterRole',
        name: 'devops-agent'
      },
      subjects: [
        {
          kind: 'ServiceAccount',
          name: 'devops-agent',
          namespace: 'devops-agent'
        }
      ]
    }).node.addDependency(agentClusterRole);

    // =========================================================================
    // ConfigMap for DevOps Agent
    // =========================================================================

    cluster.addManifest('DevOpsAgentConfigMap', {
      apiVersion: 'v1',
      kind: 'ConfigMap',
      metadata: {
        name: 'devops-agent-config',
        namespace: 'devops-agent'
      },
      data: {
        'config.yaml': `
agent:
  name: "EKS DevOps Agent"
  cluster_name: "${cluster.clusterName}"
  region: "${this.region}"

event_processor:
  poll_interval: 5
  max_concurrent_events: 3

integrations:
  cloudwatch:
    enabled: true
    container_insights: true
  
  kubernetes:
    enabled: true
    in_cluster: true
  
  xray:
    enabled: true
  
  prometheus_mcp:
    enabled: true
    url: "http://prometheus-mcp-server.devops-agent.svc.cluster.local:8080"
  
  slack:
    enabled: true
    channel: "#eks-incidents"

workflows:
  memory_leak_investigation:
    enabled: true
    auto_remediate: false
  
  high_cpu_investigation:
    enabled: true
    auto_remediate: false
  
  high_latency_investigation:
    enabled: true
    auto_remediate: false

thresholds:
  memory:
    warning: 80
    critical: 90
  cpu:
    warning: 70
    critical: 85
  latency:
    warning_ms: 1000
    critical_ms: 3000
`
      }
    }).node.addDependency(agentNamespace);

    // =========================================================================
    // Prometheus MCP Server Deployment
    // =========================================================================

    const mcpDeployment = cluster.addManifest('PrometheusMCPDeployment', {
      apiVersion: 'apps/v1',
      kind: 'Deployment',
      metadata: {
        name: 'prometheus-mcp-server',
        namespace: 'devops-agent',
        labels: {
          app: 'prometheus-mcp-server'
        }
      },
      spec: {
        replicas: 2,
        selector: {
          matchLabels: {
            app: 'prometheus-mcp-server'
          }
        },
        template: {
          metadata: {
            labels: {
              app: 'prometheus-mcp-server'
            }
          },
          spec: {
            serviceAccountName: 'prometheus-mcp-server',
            containers: [
              {
                name: 'mcp-server',
                image: `${prometheusMcpRepo.repositoryUri}:latest`,
                ports: [
                  {
                    containerPort: 8080,
                    name: 'http'
                  }
                ],
                env: [
                  {
                    name: 'AWS_REGION',
                    value: this.region
                  },
                  {
                    name: 'AMP_WORKSPACE_ID',
                    value: prometheusWorkspaceId
                  },
                  {
                    name: 'PORT',
                    value: '8080'
                  }
                ],
                resources: {
                  requests: {
                    cpu: '250m',
                    memory: '512Mi'
                  },
                  limits: {
                    cpu: '500m',
                    memory: '1Gi'
                  }
                },
                livenessProbe: {
                  httpGet: {
                    path: '/health',
                    port: 8080
                  },
                  initialDelaySeconds: 30,
                  periodSeconds: 30
                },
                readinessProbe: {
                  httpGet: {
                    path: '/health',
                    port: 8080
                  },
                  initialDelaySeconds: 10,
                  periodSeconds: 10
                }
              }
            ]
          }
        }
      }
    });

    mcpDeployment.node.addDependency(this.mcpServiceAccount);

    // MCP Service
    cluster.addManifest('PrometheusMCPService', {
      apiVersion: 'v1',
      kind: 'Service',
      metadata: {
        name: 'prometheus-mcp-server',
        namespace: 'devops-agent'
      },
      spec: {
        selector: {
          app: 'prometheus-mcp-server'
        },
        ports: [
          {
            port: 8080,
            targetPort: 8080,
            protocol: 'TCP'
          }
        ],
        type: 'ClusterIP'
      }
    }).node.addDependency(mcpDeployment);

    // =========================================================================
    // DevOps Agent Deployment
    // =========================================================================

    const agentDeployment = cluster.addManifest('DevOpsAgentDeployment', {
      apiVersion: 'apps/v1',
      kind: 'Deployment',
      metadata: {
        name: 'devops-agent',
        namespace: 'devops-agent',
        labels: {
          app: 'devops-agent'
        }
      },
      spec: {
        replicas: 1,
        selector: {
          matchLabels: {
            app: 'devops-agent'
          }
        },
        template: {
          metadata: {
            labels: {
              app: 'devops-agent'
            }
          },
          spec: {
            serviceAccountName: 'devops-agent',
            containers: [
              {
                name: 'agent',
                image: `${devopsAgentRepo.repositoryUri}:latest`,
                env: [
                  {
                    name: 'AWS_REGION',
                    value: this.region
                  },
                  {
                    name: 'EKS_CLUSTER_NAME',
                    value: cluster.clusterName
                  },
                  {
                    name: 'SLACK_CHANNEL',
                    value: '#eks-incidents'
                  },
                  {
                    name: 'PROMETHEUS_MCP_URL',
                    value: 'http://prometheus-mcp-server.devops-agent.svc.cluster.local:8080'
                  },
                  {
                    name: 'GRAFANA_URL',
                    value: grafanaUrl || 'https://grafana.example.com'
                  },
                  {
                    name: 'SLACK_SECRET_NAME',
                    value: 'devops-agent/slack-token'
                  }
                ],
                resources: {
                  requests: {
                    cpu: '250m',
                    memory: '512Mi'
                  },
                  limits: {
                    cpu: '500m',
                    memory: '1Gi'
                  }
                }
              }
            ]
          }
        }
      }
    });

    agentDeployment.node.addDependency(this.agentServiceAccount);

    // =========================================================================
    // EventBridge Rule for CloudWatch Alarms
    // =========================================================================

    const alarmRule = new events.Rule(this, 'CloudWatchAlarmRule', {
      ruleName: 'devops-agent-cloudwatch-alarms',
      description: 'Sends CloudWatch alarms to DevOps Agent',
      eventPattern: {
        source: ['aws.cloudwatch'],
        detailType: ['CloudWatch Alarm State Change'],
        detail: {
          alarmName: [
            { prefix: cluster.clusterName }
          ]
        }
      },
      targets: [
        new targets.SqsQueue(this.eventQueue)
      ]
    });

    // =========================================================================
    // Outputs
    // =========================================================================

    new cdk.CfnOutput(this, 'DevOpsAgentRepositoryUri', {
      value: devopsAgentRepo.repositoryUri,
      description: 'DevOps Agent ECR Repository URI',
      exportName: 'DevOpsAgentRepositoryUri'
    });

    new cdk.CfnOutput(this, 'PrometheusMCPRepositoryUri', {
      value: prometheusMcpRepo.repositoryUri,
      description: 'Prometheus MCP Server ECR Repository URI',
      exportName: 'PrometheusMCPRepositoryUri'
    });

    new cdk.CfnOutput(this, 'EventQueueUrl', {
      value: this.eventQueue.queueUrl,
      description: 'SQS Queue URL for events',
      exportName: 'DevOpsAgentEventQueueUrl'
    });

    new cdk.CfnOutput(this, 'SlackSecretArn', {
      value: slackSecret.secretArn,
      description: 'Slack token secret ARN',
      exportName: 'DevOpsAgentSlackSecretArn'
    });
  }
}
