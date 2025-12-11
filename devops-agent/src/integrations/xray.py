"""
AWS X-Ray Integration
Provides access to distributed tracing data
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class XRayIntegration:
    """Integration with AWS X-Ray"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.xray = boto3.client('xray', region_name=self.region)
        
        logger.info("X-Ray integration initialized")
    
    async def get_service_map(
        self,
        service_name: str,
        period_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get service map for a service"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            response = self.xray.get_service_graph(
                StartTime=start_time,
                EndTime=end_time
            )
            
            services = response.get('Services', [])
            
            # Find the target service and its dependencies
            service_map = {
                'service': service_name,
                'dependencies': [],
                'dependents': []
            }
            
            for service in services:
                edges = service.get('Edges', [])
                for edge in edges:
                    if edge.get('ReferenceId'):
                        service_map['dependencies'].append({
                            'name': edge.get('ReferenceId'),
                            'response_time_histogram': edge.get('ResponseTimeHistogram', []),
                            'summary_statistics': edge.get('SummaryStatistics', {})
                        })
            
            return service_map
            
        except ClientError as e:
            logger.error(f"Failed to get service map: {e}")
            return {}
    
    async def get_slow_traces(
        self,
        service_name: str,
        threshold_seconds: float = 1.0,
        period_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get slow traces for a service"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            # Build filter expression
            filter_expression = f'duration >= {threshold_seconds}'
            
            response = self.xray.get_trace_summaries(
                StartTime=start_time,
                EndTime=end_time,
                FilterExpression=filter_expression
            )
            
            trace_summaries = response.get('TraceSummaries', [])
            
            slow_traces = []
            for summary in trace_summaries[:10]:  # Limit to 10 traces
                trace_id = summary.get('Id')
                
                # Get full trace details
                trace_details = await self._get_trace_details(trace_id)
                
                slow_traces.append({
                    'trace_id': trace_id,
                    'duration': summary.get('Duration', 0),
                    'response_time': summary.get('ResponseTime', 0),
                    'http_status': summary.get('Http', {}).get('HttpStatus'),
                    'bottleneck': self._identify_bottleneck(trace_details),
                    'segments': trace_details
                })
            
            return slow_traces
            
        except ClientError as e:
            logger.error(f"Failed to get slow traces: {e}")
            return []
    
    async def _get_trace_details(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get detailed segments for a trace"""
        
        try:
            response = self.xray.batch_get_traces(
                TraceIds=[trace_id]
            )
            
            traces = response.get('Traces', [])
            
            if traces:
                segments = []
                for segment in traces[0].get('Segments', []):
                    doc = segment.get('Document', '{}')
                    
                    import json
                    try:
                        segment_data = json.loads(doc)
                        segments.append({
                            'id': segment_data.get('id'),
                            'name': segment_data.get('name'),
                            'start_time': segment_data.get('start_time'),
                            'end_time': segment_data.get('end_time'),
                            'duration': segment_data.get('end_time', 0) - segment_data.get('start_time', 0),
                            'http': segment_data.get('http', {}),
                            'error': segment_data.get('error', False),
                            'fault': segment_data.get('fault', False)
                        })
                    except json.JSONDecodeError:
                        pass
                
                return segments
            
            return []
            
        except ClientError as e:
            logger.error(f"Failed to get trace details: {e}")
            return []
    
    def _identify_bottleneck(self, segments: List[Dict[str, Any]]) -> Optional[str]:
        """Identify the bottleneck segment in a trace"""
        
        if not segments:
            return None
        
        # Find segment with longest duration
        slowest = max(segments, key=lambda s: s.get('duration', 0))
        
        return slowest.get('name')
    
    async def get_error_traces(
        self,
        service_name: str,
        period_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get traces with errors"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            response = self.xray.get_trace_summaries(
                StartTime=start_time,
                EndTime=end_time,
                FilterExpression='error = true OR fault = true'
            )
            
            trace_summaries = response.get('TraceSummaries', [])
            
            error_traces = []
            for summary in trace_summaries[:10]:
                error_traces.append({
                    'trace_id': summary.get('Id'),
                    'duration': summary.get('Duration', 0),
                    'has_error': summary.get('HasError', False),
                    'has_fault': summary.get('HasFault', False),
                    'http_status': summary.get('Http', {}).get('HttpStatus'),
                    'http_url': summary.get('Http', {}).get('HttpURL')
                })
            
            return error_traces
            
        except ClientError as e:
            logger.error(f"Failed to get error traces: {e}")
            return []
    
    async def get_trace_analytics(
        self,
        service_name: str,
        period_minutes: int = 60
    ) -> Dict[str, Any]:
        """Get analytics for traces"""
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(minutes=period_minutes)
            
            response = self.xray.get_time_series_service_statistics(
                StartTime=start_time,
                EndTime=end_time,
                GroupName=service_name
            )
            
            time_series = response.get('TimeSeriesServiceStatistics', [])
            
            if time_series:
                # Aggregate statistics
                total_count = sum(ts.get('EdgeSummaryStatistics', {}).get('TotalCount', 0) for ts in time_series)
                error_count = sum(ts.get('EdgeSummaryStatistics', {}).get('ErrorStatistics', {}).get('TotalCount', 0) for ts in time_series)
                fault_count = sum(ts.get('EdgeSummaryStatistics', {}).get('FaultStatistics', {}).get('TotalCount', 0) for ts in time_series)
                
                return {
                    'total_requests': total_count,
                    'error_count': error_count,
                    'fault_count': fault_count,
                    'error_rate': error_count / total_count if total_count > 0 else 0,
                    'fault_rate': fault_count / total_count if total_count > 0 else 0
                }
            
            return {
                'total_requests': 0,
                'error_count': 0,
                'fault_count': 0,
                'error_rate': 0,
                'fault_rate': 0
            }
            
        except ClientError as e:
            logger.error(f"Failed to get trace analytics: {e}")
            return {}
