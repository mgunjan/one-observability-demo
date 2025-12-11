"""
Insight Generator
Generates human-readable insights from Prometheus query results
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class InsightGenerator:
    """Generates insights from Prometheus query results"""
    
    def __init__(self):
        logger.info("Insight Generator initialized")
    
    async def generate(
        self,
        query: str,
        promql: str,
        data: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from query results"""
        
        insights = []
        
        try:
            # Current value insight
            current_value = data.get('current_value', 0)
            if current_value > 0:
                insights.append(f"Current value: {current_value:.2f}")
            
            # Trend insight
            trend = data.get('trend', 'unknown')
            if trend == 'increasing':
                insights.append("⚠️ Metric is increasing over time - monitor closely")
            elif trend == 'decreasing':
                insights.append("✅ Metric is decreasing - situation improving")
            elif trend == 'stable':
                insights.append("ℹ️ Metric is stable")
            
            # Range insights
            max_value = data.get('max_value', 0)
            min_value = data.get('min_value', 0)
            avg_value = data.get('average_value', 0)
            
            if max_value > 0 and min_value >= 0:
                variation = ((max_value - min_value) / max_value * 100) if max_value > 0 else 0
                if variation > 50:
                    insights.append(f"High variability detected: {variation:.1f}% variation between min and max")
            
            # Threshold insights (if applicable)
            insights.extend(self._check_thresholds(query, current_value, avg_value))
            
            # Anomaly insights
            anomalies = data.get('anomalies', [])
            if anomalies:
                insights.append(f"🔍 {len(anomalies)} anomalies detected")
            
            # Series count insight
            series_count = data.get('series_count', 0)
            if series_count > 10:
                insights.append(f"High cardinality: {series_count} time series returned")
            
            # Add PromQL query for reference
            insights.append(f"PromQL: `{promql}`")
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate insights: {e}", exc_info=True)
            return ["Unable to generate insights"]
    
    def _check_thresholds(
        self,
        query: str,
        current: float,
        average: float
    ) -> List[str]:
        """Check common threshold violations"""
        
        insights = []
        query_lower = query.lower()
        
        # Memory thresholds
        if 'memory' in query_lower:
            if current > 90:
                insights.append("🔴 CRITICAL: Memory usage > 90% - OOMKill risk")
            elif current > 80:
                insights.append("🟠 WARNING: Memory usage > 80%")
            elif current > 70:
                insights.append("🟡 CAUTION: Memory usage > 70%")
        
        # CPU thresholds
        if 'cpu' in query_lower:
            if current > 85:
                insights.append("🔴 CRITICAL: CPU usage > 85% - throttling likely")
            elif current > 70:
                insights.append("🟠 WARNING: CPU usage > 70%")
        
        # Latency thresholds (assuming milliseconds)
        if 'latency' in query_lower or 'duration' in query_lower:
            if current > 3000:
                insights.append("🔴 CRITICAL: Latency > 3s - user experience severely impacted")
            elif current > 1000:
                insights.append("🟠 WARNING: Latency > 1s - user experience degraded")
            elif current > 500:
                insights.append("🟡 CAUTION: Latency > 500ms")
        
        # Error rate thresholds
        if 'error' in query_lower:
            if current > 5:
                insights.append("🔴 CRITICAL: Error rate > 5%")
            elif current > 1:
                insights.append("🟠 WARNING: Error rate > 1%")
        
        return insights
