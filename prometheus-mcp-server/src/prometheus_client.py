"""
Prometheus Client for AWS Managed Prometheus
Handles PromQL query execution with AWS SigV4 authentication
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests

logger = logging.getLogger(__name__)


class PrometheusClient:
    """Client for AWS Managed Prometheus"""
    
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.workspace_id = os.getenv('AMP_WORKSPACE_ID', '')
        
        if not self.workspace_id:
            logger.warning("AMP_WORKSPACE_ID not set, client will not work")
        
        self.query_url = f"https://aps-workspaces.{self.region}.amazonaws.com/workspaces/{self.workspace_id}/api/v1/query"
        self.query_range_url = f"https://aps-workspaces.{self.region}.amazonaws.com/workspaces/{self.workspace_id}/api/v1/query_range"
        
        # AWS credentials
        self.session = boto3.Session()
        self.credentials = self.session.get_credentials()
        
        logger.info(f"Prometheus client initialized for workspace: {self.workspace_id}")
    
    def _sign_request(self, request: requests.PreparedRequest) -> requests.PreparedRequest:
        """Sign request with AWS SigV4"""
        
        aws_request = AWSRequest(
            method=request.method,
            url=request.url,
            data=request.body,
            headers=dict(request.headers)
        )
        
        SigV4Auth(self.credentials, 'aps', self.region).add_auth(aws_request)
        
        # Update original request with signed headers
        request.headers.update(dict(aws_request.headers))
        
        return request
    
    async def query(self, promql: str, time: Optional[str] = None) -> Dict[str, Any]:
        """Execute instant PromQL query"""
        
        try:
            params = {'query': promql}
            
            if time:
                params['time'] = time
            
            # Create request
            req = requests.Request('GET', self.query_url, params=params)
            prepared = req.prepare()
            
            # Sign request
            signed_request = self._sign_request(prepared)
            
            # Execute
            session = requests.Session()
            response = session.send(signed_request, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': self._parse_query_result(data),
                    'raw': data
                }
            else:
                logger.error(f"Query failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"Query failed: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Query execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    async def query_range(
        self,
        query: str,
        time_range: str = '1h',
        step: str = '15s'
    ) -> Dict[str, Any]:
        """Execute range PromQL query"""
        
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)
            
            params = {
                'query': query,
                'start': start_time.timestamp(),
                'end': end_time.timestamp(),
                'step': step
            }
            
            # Create request
            req = requests.Request('GET', self.query_range_url, params=params)
            prepared = req.prepare()
            
            # Sign request
            signed_request = self._sign_request(prepared)
            
            # Execute
            session = requests.Session()
            response = session.send(signed_request, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'data': self._parse_range_result(data),
                    'raw': data
                }
            else:
                logger.error(f"Query range failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f"Query range failed: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Query range execution error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_query_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse instant query result"""
        
        data = result.get('data', {})
        result_type = data.get('resultType', '')
        results = data.get('result', [])
        
        if not results:
            return {
                'current_value': 0,
                'values': [],
                'series_count': 0
            }
        
        if result_type == 'vector':
            # Extract values from vector result
            values = []
            for result_item in results:
                metric = result_item.get('metric', {})
                value = result_item.get('value', [None, '0'])
                
                values.append({
                    'metric': metric,
                    'value': float(value[1]) if len(value) > 1 else 0,
                    'timestamp': value[0] if len(value) > 0 else None
                })
            
            current = values[0]['value'] if values else 0
            
            return {
                'current_value': current,
                'values': values,
                'series_count': len(values)
            }
        
        return {
            'current_value': 0,
            'values': [],
            'series_count': 0
        }
    
    def _parse_range_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse range query result"""
        
        data = result.get('data', {})
        results = data.get('result', [])
        
        if not results:
            return {
                'current_value': 0,
                'max_value': 0,
                'min_value': 0,
                'average_value': 0,
                'trend': 'unknown',
                'values': [],
                'series_count': 0
            }
        
        all_values = []
        series_data = []
        
        for result_item in results:
            metric = result_item.get('metric', {})
            values = result_item.get('values', [])
            
            # Extract numeric values
            numeric_values = [float(v[1]) for v in values]
            all_values.extend(numeric_values)
            
            series_data.append({
                'metric': metric,
                'values': numeric_values,
                'timestamps': [v[0] for v in values]
            })
        
        if all_values:
            current = all_values[-1]
            max_val = max(all_values)
            min_val = min(all_values)
            avg_val = sum(all_values) / len(all_values)
            trend = self._calculate_trend(all_values)
        else:
            current = max_val = min_val = avg_val = 0
            trend = 'unknown'
        
        return {
            'current_value': current,
            'max_value': max_val,
            'min_value': min_val,
            'average_value': avg_val,
            'trend': trend,
            'values': series_data,
            'series_count': len(series_data)
        }
    
    def _parse_time_range(self, time_range: str, end_time: datetime) -> datetime:
        """Parse time range string to datetime"""
        
        # Parse formats like: 1h, 30m, 1d, 7d
        unit = time_range[-1]
        value = int(time_range[:-1])
        
        if unit == 'h':
            return end_time - timedelta(hours=value)
        elif unit == 'm':
            return end_time - timedelta(minutes=value)
        elif unit == 'd':
            return end_time - timedelta(days=value)
        elif unit == 'w':
            return end_time - timedelta(weeks=value)
        else:
            # Default to 1 hour
            return end_time - timedelta(hours=1)
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend from time series values"""
        
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
    
    async def discover_metrics(self) -> List[str]:
        """Discover available metrics from Prometheus"""
        
        try:
            # Query for all metric names
            url = f"https://aps-workspaces.{self.region}.amazonaws.com/workspaces/{self.workspace_id}/api/v1/label/__name__/values"
            
            req = requests.Request('GET', url)
            prepared = req.prepare()
            signed_request = self._sign_request(prepared)
            
            session = requests.Session()
            response = session.send(signed_request, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            else:
                logger.error(f"Metric discovery failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Metric discovery error: {e}", exc_info=True)
            return []
