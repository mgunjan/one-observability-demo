"""
Prometheus MCP Server
Provides natural language query interface to AWS Managed Prometheus
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from .query_translator import QueryTranslator
from .prometheus_client import PrometheusClient
from .insight_generator import InsightGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Prometheus MCP Server",
    description="Natural language interface to Prometheus metrics",
    version="1.0.0"
)

# Initialize components
query_translator = QueryTranslator()
prometheus_client = PrometheusClient()
insight_generator = InsightGenerator()


class QueryRequest(BaseModel):
    """Query request model"""
    query: str
    context: Optional[Dict[str, Any]] = None
    time_range: Optional[str] = None


class QueryResponse(BaseModel):
    """Query response model"""
    success: bool
    promql_query: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    insights: Optional[list] = None
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    # Return Prometheus-compatible metrics
    return JSONResponse(content={"message": "Metrics endpoint"})


@app.post("/api/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Process natural language query and return Prometheus results
    
    Example queries:
    - "Show me memory usage for pod petadoptionshistory-py over the last hour"
    - "What is the CPU usage for all pods in namespace default?"
    - "Show me request rate for service payforadoption-go"
    """
    
    try:
        logger.info(f"Received query: {request.query}")
        
        # Translate natural language to PromQL
        translation_result = await query_translator.translate(
            query=request.query,
            context=request.context or {}
        )
        
        if not translation_result.get('success'):
            return QueryResponse(
                success=False,
                error=translation_result.get('error', 'Failed to translate query')
            )
        
        promql = translation_result['promql']
        time_range = request.time_range or translation_result.get('time_range', '1h')
        
        logger.info(f"Translated to PromQL: {promql}")
        
        # Execute PromQL query
        query_result = await prometheus_client.query_range(
            query=promql,
            time_range=time_range
        )
        
        if not query_result.get('success'):
            return QueryResponse(
                success=False,
                error=query_result.get('error', 'Query execution failed')
            )
        
        # Generate insights
        insights = await insight_generator.generate(
            query=request.query,
            promql=promql,
            data=query_result['data']
        )
        
        return QueryResponse(
            success=True,
            promql_query=promql,
            data=query_result['data'],
            insights=insights
        )
        
    except Exception as e:
        logger.error(f"Query processing error: {e}", exc_info=True)
        return QueryResponse(
            success=False,
            error=str(e)
        )


@app.get("/api/v1/templates")
async def list_templates():
    """List available query templates"""
    
    templates = await query_translator.list_templates()
    
    return {
        "success": True,
        "templates": templates
    }


@app.get("/api/v1/metrics/discover")
async def discover_metrics():
    """Discover available metrics from Prometheus"""
    
    try:
        metrics = await prometheus_client.discover_metrics()
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Metric discovery error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/query/suggest")
async def suggest_queries(request: QueryRequest):
    """Suggest related queries based on context"""
    
    try:
        suggestions = await query_translator.suggest_queries(
            query=request.query,
            context=request.context or {}
        )
        
        return {
            "success": True,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Query suggestion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def main():
    """Run the server"""
    port = int(os.getenv('PORT', '8080'))
    host = os.getenv('HOST', '0.0.0.0')
    
    logger.info(f"Starting Prometheus MCP Server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
