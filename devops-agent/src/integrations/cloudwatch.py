"""
CloudWatch Container Insights Integration
Provides access to EKS metrics and logs
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class CloudWatchIntegration:
    """Integration with CloudWatch Container Insights"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.cluster_name = os.getenv('EKS_CLUSTER_NAME', 'PetAdoptions-EKS')
        
        # Initialize AWS clients
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.logs = boto3.client('logs', region_name=self.region)
        
        # Log group names
        self.container_insights_log_group = f'/aws/containerinsights/{self.cluster_name}/performance'
        self.application_log_group = f'/aws/containerinsights/{self.cluster_name}/application'
        
        logger.info(f"CloudWatch integration initialized for cluster: {self.cluster_name}")
    
    async def get_service_metrics(
        self,
        service_name: str,
        metric_name: str = 'Latency',
        period_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get metrics for a service"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/EKS',
                MetricName=metric_name,
                Dimensions=[
                    {'Name': 'ServiceName', 'Value': service_name},
                    {'Name': 'ClusterName', 'Value': self.cluster_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,  # 5 minutes
                Statistics=['Average', 'Maximum', 'Minimum'],
                Unit='Milliseconds'
            )
            
            datapoints = response.get('Datapoints', [])
            
            if datapoints:
                # Sort by timestamp
                datapoints.sort(key=lambda x: x['Timestamp'])
                
                return {
                    'current': datapoints[-1].get('Average', 0),
                    'max': max(d.get('Maximum', 0) for d in datapoints),
                    'min': min(d.get('Minimum', 0) for d in datapoints),
                    'p99': datapoints[-1].get('Maximum', 0),  # Simplified
                    'p50': datapoints[-1].get('Average', 0),
                    'datapoints': datapoints
                }
            else:
                return {
                    'current': 0,
                    'max': 0,
                    'min': 0,
                    'p99': 0,
                    'p50': 0,
                    'datapoints': []
                }
                
        except ClientError as e:
            logger.error(f"Failed to get service metrics: {e}")
            return {}
    
    async def get_pod_metrics(
        self,
        pod_name: str,
        namespace: str = 'default',
        metric_name: str = 'pod_memory_utilization',
        period_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get metrics for a pod"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            # Query Logs Insights for Container Insights metrics
            query = f"""
            fields @timestamp, {metric_name}
            | filter Namespace = "{namespace}"
            | filter PodName = "{pod_name}"
            | sort @timestamp desc
            | limit 100
            """
            
            response = self.logs.start_query(
                logGroupName=self.container_insights_log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            query_id = response['queryId']
            
            # Wait for query to complete
            import time
            for _ in range(10):
                time.sleep(1)
                result = self.logs.get_query_results(queryId=query_id)
                
                if result['status'] == 'Complete':
                    results = result.get('results', [])
                    
                    if results:
                        values = [
                            float(field['value'])
                            for result in results
                            for field in result
                            if field['field'] == metric_name
                        ]
                        
                        if values:
                            return {
                                'current': values[0] if values else 0,
                                'max': max(values),
                                'min': min(values),
                                'average': sum(values) / len(values),
                                'trend': self._calculate_trend(values),
                                'values': values
                            }
                    break
            
            return {
                'current': 0,
                'max': 0,
                'min': 0,
                'average': 0,
                'trend': 'unknown',
                'values': []
            }
            
        except ClientError as e:
            logger.error(f"Failed to get pod metrics: {e}")
            return {}
    
    async def get_container_insights_query(
        self,
        query: str,
        period_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Execute a Container Insights query"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            response = self.logs.start_query(
                logGroupName=self.container_insights_log_group,
                startTime=int(start_time.timestamp()),
                endTime=int(end_time.timestamp()),
                queryString=query
            )
            
            query_id = response['queryId']
            
            # Poll for results
            import time
            for _ in range(20):
                time.sleep(1)
                result = self.logs.get_query_results(queryId=query_id)
                
                if result['status'] == 'Complete':
                    return result.get('results', [])
                elif result['status'] == 'Failed':
                    logger.error(f"Query failed: {result.get('statistics', {})}")
                    return []
            
            logger.warning("Query timed out")
            return []
            
        except ClientError as e:
            logger.error(f"Failed to execute query: {e}")
            return []
    
    async def get_pod_logs(
        self,
        pod_name: str,
        namespace: str = 'default',
        lines: int = 100
    ) -> List[str]:
        """Get logs for a pod from CloudWatch"""
        
        try:
            # Query for pod logs
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=1)
            
            query = f"""
            fields @timestamp, @message
            | filter kubernetes.pod_name = "{pod_name}"
            | filter kubernetes.namespace_name = "{namespace}"
            | sort @timestamp desc
            | limit {lines}
            """
            
            results = await self.get_container_insights_query(query, period_minutes=60)
            
            logs = []
            for result in results:
                for field in result:
                    if field['field'] == '@message':
                        logs.append(field['value'])
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get pod logs: {e}")
            return []
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from a series of values"""
        if len(values) < 2:
            return 'unknown'
        
        # Simple linear trend
        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
        
        if second_half > first_half * 1.1:
            return 'increasing'
        elif second_half < first_half * 0.9:
            return 'decreasing'
        else:
            return 'stable'
    
    async def check_alarms(self, alarm_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Check CloudWatch alarms status"""
        
        try:
            if alarm_names:
                response = self.cloudwatch.describe_alarms(
                    AlarmNames=alarm_names
                )
            else:
                response = self.cloudwatch.describe_alarms(
                    StateValue='ALARM',
                    MaxRecords=100
                )
            
            alarms = []
            for alarm in response.get('MetricAlarms', []):
                alarms.append({
                    'name': alarm['AlarmName'],
                    'state': alarm['StateValue'],
                    'reason': alarm.get('StateReason', ''),
                    'timestamp': alarm.get('StateUpdatedTimestamp', ''),
                    'metric': alarm.get('MetricName', ''),
                    'namespace': alarm.get('Namespace', '')
                })
            
            return alarms
            
        except ClientError as e:
            logger.error(f"Failed to check alarms: {e}")
            return []
