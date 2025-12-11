"""
Kubernetes API Integration
Provides access to EKS cluster resources and operations
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)


class KubernetesIntegration:
    """Integration with Kubernetes API"""
    
    def __init__(self):
        self.cluster_name = os.getenv('EKS_CLUSTER_NAME', 'PetAdoptions-EKS')
        self.core_v1 = None
        self.apps_v1 = None
        self.initialized = False
        
        logger.info(f"Kubernetes integration initialized for cluster: {self.cluster_name}")
    
    async def initialize(self):
        """Initialize Kubernetes clients"""
        try:
            # Try in-cluster config first, fallback to kubeconfig
            try:
                config.load_incluster_config()
                logger.info("Using in-cluster Kubernetes configuration")
            except config.ConfigException:
                config.load_kube_config()
                logger.info("Using kubeconfig file")
            
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            self.initialized = True
            
            logger.info("Kubernetes clients initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Kubernetes clients: {e}", exc_info=True)
            raise
    
    async def get_pod_events(
        self,
        pod_name: str,
        namespace: str = 'default'
    ) -> List[Dict[str, Any]]:
        """Get events for a pod"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            events = self.core_v1.list_namespaced_event(
                namespace=namespace,
                field_selector=f'involvedObject.name={pod_name}'
            )
            
            event_list = []
            for event in events.items:
                event_list.append({
                    'type': event.type,
                    'reason': event.reason,
                    'message': event.message,
                    'count': event.count,
                    'first_timestamp': event.first_timestamp,
                    'last_timestamp': event.last_timestamp
                })
            
            return event_list
            
        except ApiException as e:
            logger.error(f"Failed to get pod events: {e}")
            return []
    
    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: str = 'default',
        lines: int = 100
    ) -> List[str]:
        """Get logs for a pod"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            log_data = self.core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=lines
            )
            
            return log_data.split('\n') if log_data else []
            
        except ApiException as e:
            logger.error(f"Failed to get pod logs: {e}")
            return []
    
    async def get_restart_count(
        self,
        pod_name: str,
        namespace: str = 'default'
    ) -> int:
        """Get restart count for a pod"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            
            restart_count = 0
            if pod.status and pod.status.container_statuses:
                for container in pod.status.container_statuses:
                    restart_count += container.restart_count
            
            return restart_count
            
        except ApiException as e:
            logger.error(f"Failed to get restart count: {e}")
            return 0
    
    async def get_resource_limits(
        self,
        pod_name: str,
        namespace: str = 'default'
    ) -> Dict[str, Any]:
        """Get resource limits and requests for a pod"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            pod = self.core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            
            limits = {
                'cpu_request': 0,
                'cpu_limit': 0,
                'memory_request': 0,
                'memory_limit': 0
            }
            
            if pod.spec and pod.spec.containers:
                for container in pod.spec.containers:
                    if container.resources:
                        if container.resources.requests:
                            limits['cpu_request'] += self._parse_cpu(
                                container.resources.requests.get('cpu', '0')
                            )
                            limits['memory_request'] += self._parse_memory(
                                container.resources.requests.get('memory', '0')
                            )
                        
                        if container.resources.limits:
                            limits['cpu_limit'] += self._parse_cpu(
                                container.resources.limits.get('cpu', '0')
                            )
                            limits['memory_limit'] += self._parse_memory(
                                container.resources.limits.get('memory', '0')
                            )
            
            return limits
            
        except ApiException as e:
            logger.error(f"Failed to get resource limits: {e}")
            return {}
    
    async def get_recent_changes(
        self,
        namespace: str = 'default',
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get recent deployment changes"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace=namespace)
            
            recent_changes = []
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            for deployment in deployments.items:
                if deployment.metadata.creation_timestamp > cutoff_time:
                    recent_changes.append({
                        'name': deployment.metadata.name,
                        'type': 'deployment',
                        'timestamp': deployment.metadata.creation_timestamp,
                        'replicas': deployment.spec.replicas,
                        'image': deployment.spec.template.spec.containers[0].image if deployment.spec.template.spec.containers else 'unknown'
                    })
            
            return recent_changes
            
        except ApiException as e:
            logger.error(f"Failed to get recent changes: {e}")
            return []
    
    async def get_node_metrics(self, node_name: str) -> Dict[str, Any]:
        """Get metrics for a node"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            node = self.core_v1.read_node(name=node_name)
            
            metrics = {
                'name': node.metadata.name,
                'status': 'Unknown',
                'conditions': [],
                'capacity': {},
                'allocatable': {}
            }
            
            if node.status:
                # Status
                for condition in node.status.conditions or []:
                    if condition.type == 'Ready':
                        metrics['status'] = condition.status
                    
                    metrics['conditions'].append({
                        'type': condition.type,
                        'status': condition.status,
                        'reason': condition.reason,
                        'message': condition.message
                    })
                
                # Capacity and allocatable
                if node.status.capacity:
                    metrics['capacity'] = {
                        'cpu': node.status.capacity.get('cpu', '0'),
                        'memory': node.status.capacity.get('memory', '0'),
                        'pods': node.status.capacity.get('pods', '0')
                    }
                
                if node.status.allocatable:
                    metrics['allocatable'] = {
                        'cpu': node.status.allocatable.get('cpu', '0'),
                        'memory': node.status.allocatable.get('memory', '0'),
                        'pods': node.status.allocatable.get('pods', '0')
                    }
            
            return metrics
            
        except ApiException as e:
            logger.error(f"Failed to get node metrics: {e}")
            return {}
    
    async def get_pods_on_node(self, node_name: str) -> List[Dict[str, Any]]:
        """Get all pods running on a specific node"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            pods = self.core_v1.list_pod_for_all_namespaces(
                field_selector=f'spec.nodeName={node_name}'
            )
            
            pod_list = []
            for pod in pods.items:
                pod_info = {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'phase': pod.status.phase if pod.status else 'Unknown',
                    'cpu': 0,  # Would need metrics API for actual values
                    'memory': 0
                }
                
                pod_list.append(pod_info)
            
            return pod_list
            
        except ApiException as e:
            logger.error(f"Failed to get pods on node: {e}")
            return []
    
    async def get_eviction_events(self, node_name: str) -> List[Dict[str, Any]]:
        """Get eviction events for a node"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            events = self.core_v1.list_event_for_all_namespaces(
                field_selector=f'involvedObject.name={node_name},reason=Evicted'
            )
            
            evictions = []
            for event in events.items:
                evictions.append({
                    'pod': event.involved_object.name,
                    'namespace': event.involved_object.namespace,
                    'reason': event.reason,
                    'message': event.message,
                    'timestamp': event.last_timestamp
                })
            
            return evictions
            
        except ApiException as e:
            logger.error(f"Failed to get eviction events: {e}")
            return []
    
    async def restart_pod(
        self,
        pod_name: str,
        namespace: str = 'default'
    ) -> bool:
        """Restart a pod by deleting it (deployment will recreate)"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            self.core_v1.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                grace_period_seconds=30
            )
            
            logger.info(f"Pod {pod_name} deleted for restart")
            return True
            
        except ApiException as e:
            logger.error(f"Failed to restart pod: {e}")
            return False
    
    async def scale_deployment(
        self,
        deployment_name: str,
        replicas: int,
        namespace: str = 'default'
    ) -> bool:
        """Scale a deployment"""
        
        if not self.initialized:
            await self.initialize()
        
        try:
            # Get current deployment
            deployment = self.apps_v1.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            # Update replicas
            deployment.spec.replicas = replicas
            
            # Apply update
            self.apps_v1.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            logger.info(f"Deployment {deployment_name} scaled to {replicas} replicas")
            return True
            
        except ApiException as e:
            logger.error(f"Failed to scale deployment: {e}")
            return False
    
    def _parse_cpu(self, cpu_string: str) -> float:
        """Parse CPU string to millicores"""
        if not cpu_string:
            return 0.0
        
        cpu_string = str(cpu_string)
        
        if cpu_string.endswith('m'):
            return float(cpu_string[:-1])
        else:
            return float(cpu_string) * 1000
    
    def _parse_memory(self, memory_string: str) -> float:
        """Parse memory string to MB"""
        if not memory_string:
            return 0.0
        
        memory_string = str(memory_string)
        
        units = {
            'Ki': 1 / 1024,
            'Mi': 1,
            'Gi': 1024,
            'K': 1 / 1000,
            'M': 1,
            'G': 1000
        }
        
        for unit, multiplier in units.items():
            if memory_string.endswith(unit):
                return float(memory_string[:-len(unit)]) * multiplier
        
        # Assume bytes
        return float(memory_string) / (1024 * 1024)
