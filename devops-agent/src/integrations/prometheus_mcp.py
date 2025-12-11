"""
Prometheus MCP Client
Provides natural language query interface to Prometheus metrics
"""

import os
import logging
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class PrometheusMCPClient:
    """Client for Prometheus MCP Server"""
    
    def __init__(self):
        self.mcp_url = os.getenv('PROMETHEUS_MCP_URL', 'http://prometheus-mcp-server:8080')
        self.session = None
        
        logger.info(f"Prometheus MCP client initialized (URL: {self.mcp_url})")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Query Prometheus using natural language
        
        Example queries:
        - "Show me memory usage for pod petadoptionshistory-py over the last hour"
        - "What is the CPU usage for all pods in namespace default?"
        - "Show me request rate for service payforadoption-go"
        """
        
        try:
            session = await self._get_session()
            
            payload = {
                'query': natural_language_query,
                'context': {
                    'cluster': os.getenv('EKS_CLUSTER_NAME', 'PetAdoptions-EKS')
                }
            }
            
            async with session.post(
                f"{self.mcp_url}/api/v1/query",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                
                if response.status == 200:
                    result = await response.json()
                    return self._parse_query_result(result)
                else:
                    logger.error(f"MCP query failed: {response.status}")
                    return self._get_fallback_metrics()
        
        except Exception as e:
            logger.error(f"Failed to query Prometheus MCP: {e}")
            return self._get_fallback_metrics()
    
    async def get_pod_metrics(
        self,
        pod_name: str,
        namespace: str = 'default',
        metric_type: str = 'memory'
    ) -> Dict[str, Any]:
        """Get specific metrics for a pod"""
        
        query = f"Show me {metric_type} usage for pod {pod_name} in namespace {namespace} over the last hour"
        return await self.query(query)
    
    async def get_service_metrics(
        self,
        service_name: str,
        metric_type: str = 'request_rate'
    ) -> Dict[str, Any]:
        """Get metrics for a service"""
        
        query = f"Show me {metric_type} for service {service_name} over the last hour"
        return await self.query(query)
    
    async def get_node_metrics(
        self,
        node_name: str
    ) -> Dict[str, Any]:
        """Get metrics for a node"""
        
        query = f"Show me resource usage for node {node_name} over the last hour"
        return await self.query(query)
    
    async def detect_anomalies(
        self,
        metric_name: str,
        resource_name: str
    ) -> Dict[str, Any]:
        """Detect anomalies in metrics"""
        
        query = f"Detect anomalies in {metric_name} for {resource_name}"
        return await self.query(query)
    
    def _parse_query_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse MCP query result"""
        
        try:
            data = result.get('data', {})
            
            return {
                'success': True,
                'current': data.get('current_value', 0),
                'max': data.get('max_value', 0),
                'min': data.get('min_value', 0),
                'average': data.get('average_value', 0),
                'trend': data.get('trend', 'unknown'),
                'anomalies': data.get('anomalies', []),
                'promql': result.get('promql_query', ''),
                'insights': result.get('insights', []),
                'values': data.get('values', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to parse MCP result: {e}")
            return self._get_fallback_metrics()
    
    def _get_fallback_metrics(self) -> Dict[str, Any]:
        """Return fallback metrics when MCP is unavailable"""
        
        return {
            'success': False,
            'current': 0,
            'max': 0,
            'min': 0,
            'average': 0,
            'trend': 'unknown',
            'anomalies': [],
            'promql': '',
            'insights': ['MCP server unavailable, using fallback'],
            'values': []
        }
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
