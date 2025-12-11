"""
Query Translator
Translates natural language queries to PromQL
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class QueryTranslator:
    """Translates natural language to PromQL"""
    
    def __init__(self):
        self.templates = self._load_templates()
        logger.info(f"Query translator initialized with {len(self.templates)} templates")
    
    def _load_templates(self) -> List[Dict[str, Any]]:
        """Load PromQL query templates"""
        
        return [
            {
                'pattern': r'memory usage.*pod\s+(\S+)',
                'promql': 'container_memory_usage_bytes{{pod="{pod_name}"}}',
                'description': 'Memory usage for a specific pod',
                'category': 'memory'
            },
            {
                'pattern': r'cpu usage.*pod\s+(\S+)',
                'promql': 'rate(container_cpu_usage_seconds_total{{pod="{pod_name}"}}[5m])',
                'description': 'CPU usage for a specific pod',
                'category': 'cpu'
            },
            {
                'pattern': r'memory usage.*namespace\s+(\S+)',
                'promql': 'sum(container_memory_usage_bytes{{namespace="{namespace}"}}) by (pod)',
                'description': 'Memory usage by pod in namespace',
                'category': 'memory'
            },
            {
                'pattern': r'cpu usage.*namespace\s+(\S+)',
                'promql': 'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod)',
                'description': 'CPU usage by pod in namespace',
                'category': 'cpu'
            },
            {
                'pattern': r'request rate.*service\s+(\S+)',
                'promql': 'rate(http_requests_total{{service="{service_name}"}}[5m])',
                'description': 'Request rate for a service',
                'category': 'requests'
            },
            {
                'pattern': r'error rate.*service\s+(\S+)',
                'promql': 'rate(http_requests_total{{service="{service_name}",status=~"5.."}}[5m])',
                'description': 'Error rate for a service',
                'category': 'errors'
            },
            {
                'pattern': r'latency.*service\s+(\S+)',
                'promql': 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service_name}"}}[5m]))',
                'description': 'P99 latency for a service',
                'category': 'latency'
            },
            {
                'pattern': r'resource usage.*node\s+(\S+)',
                'promql': 'node_memory_MemAvailable_bytes{{node="{node_name}"}} / node_memory_MemTotal_bytes{{node="{node_name}"}}',
                'description': 'Memory availability on a node',
                'category': 'node'
            },
            {
                'pattern': r'pod count.*namespace\s+(\S+)',
                'promql': 'count(kube_pod_info{{namespace="{namespace}"}}) by (namespace)',
                'description': 'Count of pods in namespace',
                'category': 'pods'
            },
            {
                'pattern': r'restart count.*pod\s+(\S+)',
                'promql': 'kube_pod_container_status_restarts_total{{pod="{pod_name}"}}',
                'description': 'Container restart count for pod',
                'category': 'restarts'
            }
        ]
    
    async def translate(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Translate natural language query to PromQL"""
        
        try:
            query_lower = query.lower()
            
            # Try to match against templates
            for template in self.templates:
                match = re.search(template['pattern'], query_lower)
                
                if match:
                    # Extract parameters
                    params = self._extract_parameters(match, template)
                    
                    # Build PromQL query
                    promql = template['promql'].format(**params)
                    
                    # Determine time range
                    time_range = self._extract_time_range(query)
                    
                    return {
                        'success': True,
                        'promql': promql,
                        'template': template['description'],
                        'category': template['category'],
                        'time_range': time_range,
                        'parameters': params
                    }
            
            # If no template matched, try to construct query from keywords
            promql = self._construct_from_keywords(query)
            
            if promql:
                return {
                    'success': True,
                    'promql': promql,
                    'template': 'keyword-based',
                    'category': 'generic',
                    'time_range': self._extract_time_range(query)
                }
            
            return {
                'success': False,
                'error': 'Could not translate query. Please provide more specific information.'
            }
            
        except Exception as e:
            logger.error(f"Translation error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_parameters(
        self,
        match: re.Match,
        template: Dict[str, Any]
    ) -> Dict[str, str]:
        """Extract parameters from regex match"""
        
        params = {}
        
        if 'pod' in template['promql']:
            params['pod_name'] = match.group(1) if match.lastindex >= 1 else ''
        
        if 'namespace' in template['promql']:
            params['namespace'] = match.group(1) if match.lastindex >= 1 else ''
        
        if 'service' in template['promql']:
            params['service_name'] = match.group(1) if match.lastindex >= 1 else ''
        
        if 'node' in template['promql']:
            params['node_name'] = match.group(1) if match.lastindex >= 1 else ''
        
        return params
    
    def _extract_time_range(self, query: str) -> str:
        """Extract time range from query"""
        
        query_lower = query.lower()
        
        if 'last hour' in query_lower or 'past hour' in query_lower:
            return '1h'
        elif 'last 30 minutes' in query_lower:
            return '30m'
        elif 'last 15 minutes' in query_lower:
            return '15m'
        elif 'last 5 minutes' in query_lower:
            return '5m'
        elif 'last day' in query_lower or 'past day' in query_lower:
            return '1d'
        elif 'last week' in query_lower:
            return '7d'
        else:
            return '1h'  # Default
    
    def _construct_from_keywords(self, query: str) -> Optional[str]:
        """Attempt to construct PromQL from keywords"""
        
        query_lower = query.lower()
        
        # This is a simplified keyword-based construction
        # In production, this would be more sophisticated
        
        if 'memory' in query_lower and 'pod' in query_lower:
            return 'container_memory_usage_bytes'
        elif 'cpu' in query_lower and 'pod' in query_lower:
            return 'rate(container_cpu_usage_seconds_total[5m])'
        elif 'request' in query_lower:
            return 'rate(http_requests_total[5m])'
        
        return None
    
    async def list_templates(self) -> List[Dict[str, Any]]:
        """List all available query templates"""
        
        return [
            {
                'description': t['description'],
                'category': t['category'],
                'example': self._generate_example(t)
            }
            for t in self.templates
        ]
    
    def _generate_example(self, template: Dict[str, Any]) -> str:
        """Generate example query for a template"""
        
        pattern = template['pattern']
        
        if 'pod' in pattern:
            return pattern.replace(r'(\S+)', 'my-pod-name')
        elif 'namespace' in pattern:
            return pattern.replace(r'(\S+)', 'default')
        elif 'service' in pattern:
            return pattern.replace(r'(\S+)', 'my-service')
        elif 'node' in pattern:
            return pattern.replace(r'(\S+)', 'node-1')
        
        return pattern
    
    async def suggest_queries(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Suggest related queries"""
        
        suggestions = []
        query_lower = query.lower()
        
        # Suggest related metrics
        if 'memory' in query_lower:
            suggestions.extend([
                "Show me memory usage trend over the last day",
                "Compare memory usage across all pods",
                "Detect memory leaks in the application"
            ])
        elif 'cpu' in query_lower:
            suggestions.extend([
                "Show me CPU throttling events",
                "Compare CPU usage across all pods",
                "Show me CPU usage spikes"
            ])
        elif 'latency' in query_lower or 'request' in query_lower:
            suggestions.extend([
                "Show me error rate for the service",
                "Compare latency across services",
                "Show me slow requests"
            ])
        
        return suggestions[:5]  # Return top 5 suggestions
