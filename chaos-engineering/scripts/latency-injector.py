#!/usr/bin/env python3
"""
Latency Injector
Adds artificial latency to service responses
"""

import os
import sys
import time
import random
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


class LatencyInjectorHandler(BaseHTTPRequestHandler):
    """HTTP handler that injects latency"""
    
    latency_ms = 1000  # Default latency in milliseconds
    variance_ms = 200  # Variance in latency
    
    def do_GET(self):
        """Handle GET requests with injected latency"""
        
        # Parse query parameters
        parsed_path = urlparse(self.path)
        params = parse_qs(parsed_path.query)
        
        # Calculate latency (with variance)
        base_latency = self.latency_ms / 1000.0
        variance = self.variance_ms / 1000.0
        actual_latency = base_latency + random.uniform(-variance, variance)
        actual_latency = max(0, actual_latency)  # Ensure non-negative
        
        logger.info(f"Request to {self.path} - injecting {actual_latency*1000:.0f}ms latency")
        
        # Inject latency
        time.sleep(actual_latency)
        
        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('X-Injected-Latency-Ms', str(int(actual_latency * 1000)))
        self.end_headers()
        
        response = {
            'status': 'ok',
            'injected_latency_ms': int(actual_latency * 1000),
            'timestamp': time.time()
        }
        
        import json
        self.wfile.write(json.dumps(response).encode())
    
    def do_POST(self):
        """Handle POST requests with injected latency"""
        self.do_GET()
    
    def log_message(self, format, *args):
        """Override to use logger instead of stderr"""
        logger.info(format % args)


def run_server(port: int, latency_ms: int, variance_ms: int):
    """Run the latency injector server"""
    
    LatencyInjectorHandler.latency_ms = latency_ms
    LatencyInjectorHandler.variance_ms = variance_ms
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, LatencyInjectorHandler)
    
    logger.info(f"Latency Injector Server starting on port {port}")
    logger.info(f"Injecting {latency_ms}ms ± {variance_ms}ms latency")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server interrupted")
    finally:
        httpd.server_close()
        logger.info("Server stopped")


def main():
    """Main entry point"""
    
    port = int(os.getenv('PORT', '8080'))
    latency_ms = int(os.getenv('LATENCY_MS', '1000'))
    variance_ms = int(os.getenv('VARIANCE_MS', '200'))
    
    run_server(port, latency_ms, variance_ms)


if __name__ == "__main__":
    main()
