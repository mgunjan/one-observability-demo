"""
AWS DevOps Agent Main Entry Point
Handles incident detection, investigation, and remediation for EKS workloads
"""

import os
import sys
import logging
import asyncio
import signal
from typing import Dict, Any, Optional
from datetime import datetime

from .event_processor import EventProcessor
from .workflow_engine import WorkflowEngine
from .integrations.cloudwatch import CloudWatchIntegration
from .integrations.kubernetes_client import KubernetesIntegration
from .integrations.xray import XRayIntegration
from .integrations.slack import SlackIntegration
from .integrations.prometheus_mcp import PrometheusMCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class DevOpsAgent:
    """Main DevOps Agent orchestrator"""
    
    def __init__(self):
        self.running = False
        self.event_processor = None
        self.workflow_engine = None
        
        # Initialize integrations
        self.cloudwatch = CloudWatchIntegration()
        self.kubernetes = KubernetesIntegration()
        self.xray = XRayIntegration()
        self.slack = SlackIntegration()
        self.prometheus_mcp = PrometheusMCPClient()
        
        # Configuration from environment
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.cluster_name = os.getenv('EKS_CLUSTER_NAME', 'PetAdoptions-EKS')
        self.slack_channel = os.getenv('SLACK_CHANNEL', '#eks-incidents')
        
        logger.info(f"Initializing DevOps Agent for cluster: {self.cluster_name}")
    
    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Initializing integrations...")
            
            # Initialize Kubernetes client
            await self.kubernetes.initialize()
            
            # Initialize workflow engine with integrations
            self.workflow_engine = WorkflowEngine(
                cloudwatch=self.cloudwatch,
                kubernetes=self.kubernetes,
                xray=self.xray,
                prometheus_mcp=self.prometheus_mcp,
                slack=self.slack
            )
            
            # Initialize event processor
            self.event_processor = EventProcessor(
                workflow_engine=self.workflow_engine,
                slack=self.slack
            )
            
            logger.info("DevOps Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent: {e}", exc_info=True)
            raise
    
    async def start(self):
        """Start the agent"""
        self.running = True
        logger.info("Starting DevOps Agent...")
        
        try:
            # Start event processing loop
            await self.event_processor.start()
            
            # Send startup notification
            await self.slack.send_notification(
                channel=self.slack_channel,
                message=f"🚀 DevOps Agent started for cluster `{self.cluster_name}`",
                severity="info"
            )
            
            # Main loop
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Agent error: {e}", exc_info=True)
            await self.stop()
    
    async def stop(self):
        """Stop the agent gracefully"""
        logger.info("Stopping DevOps Agent...")
        self.running = False
        
        if self.event_processor:
            await self.event_processor.stop()
        
        # Send shutdown notification
        try:
            await self.slack.send_notification(
                channel=self.slack_channel,
                message=f"🛑 DevOps Agent stopped for cluster `{self.cluster_name}`",
                severity="warning"
            )
        except Exception as e:
            logger.warning(f"Failed to send shutdown notification: {e}")
        
        logger.info("DevOps Agent stopped")
    
    def handle_signal(self, sig, frame):
        """Handle termination signals"""
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(self.stop())


async def main():
    """Main entry point"""
    agent = DevOpsAgent()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, agent.handle_signal)
    signal.signal(signal.SIGTERM, agent.handle_signal)
    
    try:
        await agent.initialize()
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
