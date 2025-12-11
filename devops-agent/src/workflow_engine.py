"""
Workflow Engine
Executes investigation and remediation workflows
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Executes investigation workflows for different incident types"""
    
    def __init__(self, cloudwatch, kubernetes, xray, prometheus_mcp, slack):
        self.cloudwatch = cloudwatch
        self.kubernetes = kubernetes
        self.xray = xray
        self.prometheus_mcp = prometheus_mcp
        self.slack = slack
        
        # Load workflow definitions
        self.workflows = self._load_workflows()
        
        logger.info(f"Workflow Engine initialized with {len(self.workflows)} workflows")
    
    def _load_workflows(self) -> Dict[str, Dict[str, Any]]:
        """Load workflow definitions"""
        # In production, these would be loaded from configuration files
        return {
            'memory_leak_investigation': {
                'name': 'Memory Leak Investigation',
                'steps': [
                    'identify_pod',
                    'collect_memory_metrics',
                    'check_oom_events',
                    'analyze_memory_trend',
                    'review_recent_changes',
                    'recommend_remediation'
                ]
            },
            'high_cpu_investigation': {
                'name': 'High CPU Investigation',
                'steps': [
                    'identify_pod',
                    'collect_cpu_metrics',
                    'check_cpu_throttling',
                    'analyze_request_patterns',
                    'review_resource_limits',
                    'recommend_remediation'
                ]
            },
            'high_latency_investigation': {
                'name': 'High Latency Investigation',
                'steps': [
                    'identify_service',
                    'collect_latency_metrics',
                    'analyze_traces',
                    'check_dependencies',
                    'correlate_with_resources',
                    'recommend_remediation'
                ]
            },
            'node_pressure_investigation': {
                'name': 'Node Pressure Investigation',
                'steps': [
                    'identify_node',
                    'collect_node_metrics',
                    'list_pods_on_node',
                    'check_resource_usage',
                    'analyze_evictions',
                    'recommend_remediation'
                ]
            },
            'pod_crash_investigation': {
                'name': 'Pod Crash Investigation',
                'steps': [
                    'identify_pod',
                    'collect_pod_events',
                    'analyze_logs',
                    'check_restart_count',
                    'review_resource_limits',
                    'recommend_remediation'
                ]
            },
            'generic_investigation': {
                'name': 'Generic Investigation',
                'steps': [
                    'identify_resource',
                    'collect_metrics',
                    'analyze_patterns',
                    'recommend_actions'
                ]
            }
        }
    
    async def execute_workflow(
        self,
        workflow_name: str,
        incident_id: str,
        event: Any
    ) -> Dict[str, Any]:
        """Execute a workflow"""
        
        if workflow_name not in self.workflows:
            logger.error(f"Unknown workflow: {workflow_name}")
            return {'success': False, 'error': f'Unknown workflow: {workflow_name}'}
        
        workflow = self.workflows[workflow_name]
        logger.info(f"Executing workflow '{workflow['name']}' for incident {incident_id}")
        
        context = {
            'incident_id': incident_id,
            'workflow_name': workflow_name,
            'event': event,
            'start_time': datetime.utcnow(),
            'findings': [],
            'metrics': {},
            'logs': [],
            'recommendations': []
        }
        
        try:
            # Execute workflow steps
            for step in workflow['steps']:
                logger.info(f"Executing step: {step}")
                
                step_result = await self._execute_step(step, context)
                context['findings'].append({
                    'step': step,
                    'result': step_result,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Check if we should continue
                if not step_result.get('continue', True):
                    break
            
            # Determine root cause
            root_cause = self._determine_root_cause(context)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(context, root_cause)
            
            context['end_time'] = datetime.utcnow()
            context['duration'] = (context['end_time'] - context['start_time']).total_seconds()
            context['root_cause'] = root_cause
            context['recommendations'] = recommendations
            
            return {
                'success': True,
                'incident_id': incident_id,
                'workflow': workflow_name,
                'root_cause': root_cause,
                'recommendations': recommendations,
                'duration': context['duration'],
                'findings': context['findings']
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            return {
                'success': False,
                'incident_id': incident_id,
                'workflow': workflow_name,
                'error': str(e)
            }
    
    async def _execute_step(self, step: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single workflow step"""
        
        # Map step names to handler methods
        step_handlers = {
            'identify_pod': self._identify_pod,
            'identify_service': self._identify_service,
            'identify_node': self._identify_node,
            'identify_resource': self._identify_resource,
            'collect_memory_metrics': self._collect_memory_metrics,
            'collect_cpu_metrics': self._collect_cpu_metrics,
            'collect_latency_metrics': self._collect_latency_metrics,
            'collect_node_metrics': self._collect_node_metrics,
            'collect_metrics': self._collect_generic_metrics,
            'check_oom_events': self._check_oom_events,
            'check_cpu_throttling': self._check_cpu_throttling,
            'analyze_traces': self._analyze_traces,
            'analyze_memory_trend': self._analyze_memory_trend,
            'analyze_request_patterns': self._analyze_request_patterns,
            'review_recent_changes': self._review_recent_changes,
            'review_resource_limits': self._review_resource_limits,
            'check_dependencies': self._check_dependencies,
            'correlate_with_resources': self._correlate_with_resources,
            'list_pods_on_node': self._list_pods_on_node,
            'check_resource_usage': self._check_resource_usage,
            'analyze_evictions': self._analyze_evictions,
            'collect_pod_events': self._collect_pod_events,
            'analyze_logs': self._analyze_logs,
            'check_restart_count': self._check_restart_count,
            'analyze_patterns': self._analyze_patterns,
            'recommend_remediation': self._recommend_remediation,
            'recommend_actions': self._recommend_actions
        }
        
        handler = step_handlers.get(step)
        if handler:
            return await handler(context)
        else:
            logger.warning(f"No handler for step: {step}")
            return {'success': False, 'error': f'No handler for step: {step}'}
    
    # Step handler implementations
    
    async def _identify_pod(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the problematic pod from alarm"""
        # Extract pod info from alarm
        alarm_name = context['event'].detail.get('alarmName', '')
        
        # Parse pod name from alarm (simplified)
        pod_name = 'petadoptionshistory-py'  # Example
        namespace = 'default'
        
        context['pod_name'] = pod_name
        context['namespace'] = namespace
        
        return {
            'success': True,
            'pod_name': pod_name,
            'namespace': namespace
        }
    
    async def _identify_service(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the affected service"""
        service_name = 'payforadoption-go'  # Example
        context['service_name'] = service_name
        
        return {'success': True, 'service_name': service_name}
    
    async def _identify_node(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the affected node"""
        node_name = 'ip-10-0-1-100.ec2.internal'  # Example
        context['node_name'] = node_name
        
        return {'success': True, 'node_name': node_name}
    
    async def _identify_resource(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Identify the affected resource"""
        return {'success': True, 'resource': 'unknown'}
    
    async def _collect_memory_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect memory metrics using Prometheus MCP"""
        pod_name = context.get('pod_name')
        
        if not pod_name:
            return {'success': False, 'error': 'Pod name not identified'}
        
        # Query Prometheus via MCP
        query = f"Show me memory usage for pod {pod_name} over the last hour"
        metrics = await self.prometheus_mcp.query(query)
        
        context['metrics']['memory'] = metrics
        
        return {
            'success': True,
            'memory_usage': metrics.get('current', 'N/A'),
            'trend': metrics.get('trend', 'unknown')
        }
    
    async def _collect_cpu_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect CPU metrics"""
        pod_name = context.get('pod_name')
        
        query = f"Show me CPU usage for pod {pod_name} over the last hour"
        metrics = await self.prometheus_mcp.query(query)
        
        context['metrics']['cpu'] = metrics
        
        return {
            'success': True,
            'cpu_usage': metrics.get('current', 'N/A'),
            'throttling': metrics.get('throttling', False)
        }
    
    async def _collect_latency_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect latency metrics"""
        service_name = context.get('service_name')
        
        # Get metrics from CloudWatch and X-Ray
        metrics = await self.cloudwatch.get_service_metrics(service_name)
        
        context['metrics']['latency'] = metrics
        
        return {
            'success': True,
            'p50': metrics.get('p50', 'N/A'),
            'p99': metrics.get('p99', 'N/A')
        }
    
    async def _collect_node_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect node-level metrics"""
        node_name = context.get('node_name')
        
        metrics = await self.kubernetes.get_node_metrics(node_name)
        context['metrics']['node'] = metrics
        
        return {'success': True, 'metrics': metrics}
    
    async def _collect_generic_metrics(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect generic metrics"""
        return {'success': True, 'metrics': {}}
    
    async def _check_oom_events(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for OOMKill events"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        events = await self.kubernetes.get_pod_events(pod_name, namespace)
        oom_events = [e for e in events if 'OOMKill' in e.get('reason', '')]
        
        context['oom_events'] = oom_events
        
        return {
            'success': True,
            'oom_kill_detected': len(oom_events) > 0,
            'oom_count': len(oom_events)
        }
    
    async def _check_cpu_throttling(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check for CPU throttling"""
        metrics = context.get('metrics', {}).get('cpu', {})
        
        throttling = metrics.get('throttling_ratio', 0) > 0.1
        
        return {
            'success': True,
            'throttling_detected': throttling,
            'throttling_ratio': metrics.get('throttling_ratio', 0)
        }
    
    async def _analyze_traces(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze X-Ray traces"""
        service_name = context.get('service_name')
        
        traces = await self.xray.get_slow_traces(service_name)
        
        context['traces'] = traces
        
        return {
            'success': True,
            'slow_traces_count': len(traces),
            'bottleneck': traces[0].get('bottleneck') if traces else None
        }
    
    async def _analyze_memory_trend(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze memory usage trend"""
        metrics = context.get('metrics', {}).get('memory', {})
        
        trend = metrics.get('trend', 'unknown')
        increasing = trend == 'increasing'
        
        return {
            'success': True,
            'trend': trend,
            'memory_leak_likely': increasing
        }
    
    async def _analyze_request_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze request patterns"""
        return {
            'success': True,
            'traffic_spike': False,
            'error_rate': 0.01
        }
    
    async def _review_recent_changes(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Review recent deployments and changes"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        recent_changes = await self.kubernetes.get_recent_changes(namespace)
        
        return {
            'success': True,
            'recent_changes': recent_changes,
            'recent_deployment': len(recent_changes) > 0
        }
    
    async def _review_resource_limits(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Review resource limits and requests"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        limits = await self.kubernetes.get_resource_limits(pod_name, namespace)
        
        context['resource_limits'] = limits
        
        return {
            'success': True,
            'limits': limits,
            'limits_appropriate': self._check_limits_appropriate(limits)
        }
    
    async def _check_dependencies(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check service dependencies"""
        service_name = context.get('service_name')
        
        dependencies = await self.xray.get_service_map(service_name)
        
        return {
            'success': True,
            'dependencies': dependencies,
            'dependency_issues': []
        }
    
    async def _correlate_with_resources(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Correlate latency with resource usage"""
        return {
            'success': True,
            'correlation': 'high',
            'resource_constrained': True
        }
    
    async def _list_pods_on_node(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """List all pods on a node"""
        node_name = context.get('node_name')
        
        pods = await self.kubernetes.get_pods_on_node(node_name)
        
        context['pods_on_node'] = pods
        
        return {
            'success': True,
            'pod_count': len(pods),
            'pods': pods
        }
    
    async def _check_resource_usage(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check resource usage on node"""
        pods = context.get('pods_on_node', [])
        
        # Aggregate resource usage
        total_cpu = sum(p.get('cpu', 0) for p in pods)
        total_memory = sum(p.get('memory', 0) for p in pods)
        
        return {
            'success': True,
            'total_cpu': total_cpu,
            'total_memory': total_memory,
            'resource_hog': max(pods, key=lambda p: p.get('memory', 0)) if pods else None
        }
    
    async def _analyze_evictions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze pod evictions"""
        node_name = context.get('node_name')
        
        evictions = await self.kubernetes.get_eviction_events(node_name)
        
        return {
            'success': True,
            'eviction_count': len(evictions),
            'evictions': evictions
        }
    
    async def _collect_pod_events(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Collect pod events"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        events = await self.kubernetes.get_pod_events(pod_name, namespace)
        
        context['pod_events'] = events
        
        return {
            'success': True,
            'event_count': len(events),
            'events': events
        }
    
    async def _analyze_logs(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze pod logs"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        logs = await self.kubernetes.get_pod_logs(pod_name, namespace)
        
        # Look for errors
        errors = [line for line in logs if 'error' in line.lower() or 'exception' in line.lower()]
        
        context['logs'] = logs
        context['error_logs'] = errors
        
        return {
            'success': True,
            'error_count': len(errors),
            'errors': errors[:5]  # First 5 errors
        }
    
    async def _check_restart_count(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Check pod restart count"""
        pod_name = context.get('pod_name')
        namespace = context.get('namespace')
        
        restart_count = await self.kubernetes.get_restart_count(pod_name, namespace)
        
        return {
            'success': True,
            'restart_count': restart_count,
            'frequent_restarts': restart_count > 5
        }
    
    async def _analyze_patterns(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze patterns in metrics and logs"""
        return {
            'success': True,
            'patterns': []
        }
    
    async def _recommend_remediation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Generate remediation recommendations"""
        recommendations = self._generate_recommendations(context, None)
        
        return {
            'success': True,
            'recommendations': recommendations
        }
    
    async def _recommend_actions(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Recommend generic actions"""
        return {
            'success': True,
            'actions': ['Review metrics', 'Check logs', 'Consult runbook']
        }
    
    def _check_limits_appropriate(self, limits: Dict[str, Any]) -> bool:
        """Check if resource limits are appropriate"""
        # Simplified logic
        return limits.get('memory_limit', 0) > 128  # At least 128Mi
    
    def _determine_root_cause(self, context: Dict[str, Any]) -> str:
        """Determine root cause from investigation findings"""
        
        workflow_name = context.get('workflow_name')
        findings = context.get('findings', [])
        
        # Analyze findings to determine root cause
        if workflow_name == 'memory_leak_investigation':
            if any('oom_kill_detected' in str(f) for f in findings):
                return "Memory leak causing OOMKill events"
            elif any('memory_leak_likely' in str(f) for f in findings):
                return "Increasing memory usage pattern detected"
            else:
                return "Memory pressure observed"
        
        elif workflow_name == 'high_cpu_investigation':
            if any('throttling_detected' in str(f) for f in findings):
                return "CPU throttling due to insufficient limits"
            else:
                return "High CPU utilization"
        
        elif workflow_name == 'high_latency_investigation':
            if any('resource_constrained' in str(f) for f in findings):
                return "Latency caused by resource constraints"
            elif any('bottleneck' in str(f) for f in findings):
                return "Bottleneck in downstream service"
            else:
                return "Elevated response times"
        
        elif workflow_name == 'node_pressure_investigation':
            return "Node under resource pressure"
        
        elif workflow_name == 'pod_crash_investigation':
            return "Pod experiencing frequent crashes"
        
        else:
            return "Investigation completed"
    
    def _generate_recommendations(
        self,
        context: Dict[str, Any],
        root_cause: Optional[str]
    ) -> List[str]:
        """Generate remediation recommendations"""
        
        workflow_name = context.get('workflow_name')
        recommendations = []
        
        if workflow_name == 'memory_leak_investigation':
            recommendations.append("Restart pod to clear memory")
            recommendations.append("Increase memory limit to 512Mi")
            recommendations.append("Review application code for memory leaks")
            recommendations.append("Enable memory profiling")
        
        elif workflow_name == 'high_cpu_investigation':
            recommendations.append("Increase CPU limit to 500m")
            recommendations.append("Enable HPA for automatic scaling")
            recommendations.append("Review code for CPU-intensive operations")
        
        elif workflow_name == 'high_latency_investigation':
            recommendations.append("Scale service horizontally")
            recommendations.append("Optimize slow queries")
            recommendations.append("Enable connection pooling")
            recommendations.append("Review timeout configurations")
        
        elif workflow_name == 'node_pressure_investigation':
            recommendations.append("Cordon node to prevent new scheduling")
            recommendations.append("Drain pods to other nodes")
            recommendations.append("Add new nodes to cluster")
        
        elif workflow_name == 'pod_crash_investigation':
            recommendations.append("Review application logs for errors")
            recommendations.append("Check resource limits")
            recommendations.append("Roll back to previous version if recent deployment")
        
        else:
            recommendations.append("Review metrics and logs")
            recommendations.append("Consult runbook documentation")
        
        return recommendations
