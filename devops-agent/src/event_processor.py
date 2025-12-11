"""
Event Processor
Handles incoming events from CloudWatch Alarms via EventBridge
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Event priority levels"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class Event:
    """Represents an incident event"""
    
    def __init__(self, event_data: Dict[str, Any]):
        self.event_id = event_data.get('id', '')
        self.timestamp = event_data.get('time', datetime.utcnow().isoformat())
        self.source = event_data.get('source', '')
        self.detail_type = event_data.get('detail-type', '')
        self.detail = event_data.get('detail', {})
        self.priority = self._determine_priority()
        self.raw_data = event_data
    
    def _determine_priority(self) -> EventPriority:
        """Determine event priority based on alarm state and metrics"""
        detail = self.detail
        
        # Check alarm state
        alarm_state = detail.get('state', {}).get('value', '')
        if alarm_state == 'ALARM':
            # Check for critical keywords in alarm name
            alarm_name = detail.get('alarmName', '').lower()
            if any(keyword in alarm_name for keyword in ['critical', 'oom', 'node', 'down']):
                return EventPriority.CRITICAL
            return EventPriority.HIGH
        
        return EventPriority.MEDIUM
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'source': self.source,
            'detail_type': self.detail_type,
            'priority': self.priority.name,
            'detail': self.detail
        }


class EventProcessor:
    """Processes CloudWatch alarm events and triggers workflows"""
    
    def __init__(self, workflow_engine, slack):
        self.workflow_engine = workflow_engine
        self.slack = slack
        self.event_queue = asyncio.PriorityQueue()
        self.running = False
        self.processing_task = None
        
        # Configuration
        self.poll_interval = int(os.getenv('EVENT_POLL_INTERVAL', '5'))
        self.max_concurrent_events = int(os.getenv('MAX_CONCURRENT_EVENTS', '3'))
        
        logger.info(f"Event Processor initialized (poll_interval={self.poll_interval}s)")
    
    async def start(self):
        """Start event processing"""
        self.running = True
        self.processing_task = asyncio.create_task(self._process_events())
        
        # Start simulated event ingestion (in real scenario, this would be EventBridge)
        asyncio.create_task(self._simulate_event_ingestion())
        
        logger.info("Event Processor started")
    
    async def stop(self):
        """Stop event processing"""
        self.running = False
        
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Event Processor stopped")
    
    async def _simulate_event_ingestion(self):
        """
        Simulate event ingestion from EventBridge
        In production, this would be replaced with actual EventBridge integration
        """
        while self.running:
            await asyncio.sleep(60)  # Check every minute for demo purposes
            
            # This is where you would poll EventBridge or SQS queue
            # For now, this is a placeholder
            logger.debug("Checking for new events...")
    
    async def process_event(self, event_data: Dict[str, Any]):
        """Process a single event"""
        try:
            event = Event(event_data)
            logger.info(f"Received event: {event.event_id} (priority={event.priority.name})")
            
            # Add to priority queue
            await self.event_queue.put((event.priority.value, event))
            
        except Exception as e:
            logger.error(f"Failed to process event: {e}", exc_info=True)
    
    async def _process_events(self):
        """Main event processing loop"""
        active_tasks = []
        
        while self.running:
            try:
                # Clean up completed tasks
                active_tasks = [t for t in active_tasks if not t.done()]
                
                # Check if we can process more events
                if len(active_tasks) < self.max_concurrent_events:
                    try:
                        # Get next event from queue (with timeout)
                        priority, event = await asyncio.wait_for(
                            self.event_queue.get(),
                            timeout=1.0
                        )
                        
                        # Create task to handle event
                        task = asyncio.create_task(self._handle_event(event))
                        active_tasks.append(task)
                        
                    except asyncio.TimeoutError:
                        pass  # No events in queue
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _handle_event(self, event: Event):
        """Handle a single event by triggering appropriate workflow"""
        incident_id = f"INC-{event.event_id[:8]}"
        
        try:
            logger.info(f"Handling event {event.event_id} as incident {incident_id}")
            
            # Send initial notification
            await self.slack.send_notification(
                channel=os.getenv('SLACK_CHANNEL', '#eks-incidents'),
                message=f"🚨 New incident detected: `{incident_id}`\n"
                       f"Source: {event.source}\n"
                       f"Priority: {event.priority.name}",
                severity=event.priority.name.lower(),
                incident_id=incident_id
            )
            
            # Determine workflow based on event type
            workflow_name = self._determine_workflow(event)
            
            # Execute workflow
            result = await self.workflow_engine.execute_workflow(
                workflow_name=workflow_name,
                incident_id=incident_id,
                event=event
            )
            
            # Send completion notification
            if result.get('success'):
                await self.slack.send_notification(
                    channel=os.getenv('SLACK_CHANNEL', '#eks-incidents'),
                    message=f"✅ Incident `{incident_id}` resolved\n"
                           f"Root cause: {result.get('root_cause', 'Unknown')}\n"
                           f"Resolution: {result.get('resolution', 'N/A')}",
                    severity="info",
                    incident_id=incident_id
                )
            else:
                await self.slack.send_notification(
                    channel=os.getenv('SLACK_CHANNEL', '#eks-incidents'),
                    message=f"❌ Incident `{incident_id}` investigation failed\n"
                           f"Error: {result.get('error', 'Unknown error')}",
                    severity="high",
                    incident_id=incident_id
                )
            
        except Exception as e:
            logger.error(f"Failed to handle event {event.event_id}: {e}", exc_info=True)
            
            # Send error notification
            try:
                await self.slack.send_notification(
                    channel=os.getenv('SLACK_CHANNEL', '#eks-incidents'),
                    message=f"⚠️ Error processing incident `{incident_id}`\n"
                           f"Error: {str(e)}",
                    severity="high",
                    incident_id=incident_id
                )
            except Exception:
                pass
    
    def _determine_workflow(self, event: Event) -> str:
        """Determine which workflow to execute based on event characteristics"""
        detail = event.detail
        alarm_name = detail.get('alarmName', '').lower()
        
        # Check alarm name patterns
        if 'memory' in alarm_name or 'oom' in alarm_name:
            return 'memory_leak_investigation'
        elif 'cpu' in alarm_name or 'throttl' in alarm_name:
            return 'high_cpu_investigation'
        elif 'latency' in alarm_name or 'response' in alarm_name:
            return 'high_latency_investigation'
        elif 'node' in alarm_name or 'pressure' in alarm_name:
            return 'node_pressure_investigation'
        elif 'restart' in alarm_name or 'crash' in alarm_name:
            return 'pod_crash_investigation'
        else:
            return 'generic_investigation'
