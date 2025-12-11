"""
Slack Integration
Provides notification and interactive command capabilities
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import boto3
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Integration with Slack for notifications and commands"""
    
    def __init__(self):
        # Get Slack token from Secrets Manager or environment
        self.slack_token = self._get_slack_token()
        self.client = WebClient(token=self.slack_token) if self.slack_token else None
        
        self.default_channel = os.getenv('SLACK_CHANNEL', '#eks-incidents')
        
        if not self.client:
            logger.warning("Slack token not configured, notifications disabled")
        else:
            logger.info("Slack integration initialized")
    
    def _get_slack_token(self) -> Optional[str]:
        """Get Slack token from Secrets Manager or environment"""
        
        # Try environment variable first
        token = os.getenv('SLACK_BOT_TOKEN')
        if token:
            return token
        
        # Try Secrets Manager
        secret_name = os.getenv('SLACK_SECRET_NAME', 'devops-agent/slack-token')
        
        try:
            secrets_client = boto3.client('secretsmanager', region_name=os.getenv('AWS_REGION', 'us-east-1'))
            response = secrets_client.get_secret_value(SecretId=secret_name)
            
            import json
            secret_data = json.loads(response['SecretString'])
            return secret_data.get('bot_token')
            
        except Exception as e:
            logger.warning(f"Failed to get Slack token from Secrets Manager: {e}")
            return None
    
    async def send_notification(
        self,
        channel: str,
        message: str,
        severity: str = 'info',
        incident_id: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """Send a notification to Slack"""
        
        if not self.client:
            logger.info(f"[SLACK] {channel}: {message}")
            return None
        
        try:
            # Choose emoji based on severity
            emoji_map = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢',
                'info': 'ℹ️',
                'warning': '⚠️'
            }
            
            emoji = emoji_map.get(severity.lower(), 'ℹ️')
            
            # Build message blocks
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} {message}"
                    }
                }
            ]
            
            if incident_id:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Incident ID:* {incident_id} | *Timestamp:* {datetime.utcnow().isoformat()}"
                        }
                    ]
                })
            
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=message,  # Fallback text
                thread_ts=thread_ts
            )
            
            return response.get('ts')
            
        except SlackApiError as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return None
    
    async def send_investigation_summary(
        self,
        channel: str,
        incident_id: str,
        result: Dict[str, Any],
        thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """Send investigation summary with rich formatting"""
        
        if not self.client:
            logger.info(f"[SLACK] Investigation summary for {incident_id}")
            return None
        
        try:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📊 Investigation Summary: {incident_id}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Workflow:*\n{result.get('workflow', 'N/A')}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Duration:*\n{result.get('duration', 0):.2f}s"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Root Cause:*\n{result.get('root_cause', 'Unknown')}"
                    }
                }
            ]
            
            # Add recommendations
            recommendations = result.get('recommendations', [])
            if recommendations:
                rec_text = "\n".join([f"• {rec}" for rec in recommendations])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Recommendations:*\n{rec_text}"
                    }
                })
            
            # Add actions
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View Grafana Dashboard"
                        },
                        "url": self._get_grafana_url(),
                        "style": "primary"
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "View in CloudWatch"
                        },
                        "url": self._get_cloudwatch_url()
                    }
                ]
            })
            
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"Investigation summary for {incident_id}",
                thread_ts=thread_ts
            )
            
            return response.get('ts')
            
        except SlackApiError as e:
            logger.error(f"Failed to send investigation summary: {e}")
            return None
    
    async def send_remediation_approval(
        self,
        channel: str,
        incident_id: str,
        action: str,
        details: Dict[str, Any],
        thread_ts: Optional[str] = None
    ) -> Optional[str]:
        """Send remediation action for approval"""
        
        if not self.client:
            logger.info(f"[SLACK] Remediation approval request for {incident_id}: {action}")
            return None
        
        try:
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"⚡ *Remediation Approval Required*\n\n"
                               f"*Incident:* {incident_id}\n"
                               f"*Action:* {action}\n"
                               f"*Details:* {details.get('description', 'N/A')}"
                    }
                },
                {
                    "type": "actions",
                    "block_id": f"remediation_{incident_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✅ Approve"
                            },
                            "style": "primary",
                            "value": f"approve_{incident_id}_{action}",
                            "action_id": "approve_remediation"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "❌ Reject"
                            },
                            "style": "danger",
                            "value": f"reject_{incident_id}_{action}",
                            "action_id": "reject_remediation"
                        }
                    ]
                }
            ]
            
            response = self.client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=f"Remediation approval required for {incident_id}",
                thread_ts=thread_ts
            )
            
            return response.get('ts')
            
        except SlackApiError as e:
            logger.error(f"Failed to send remediation approval: {e}")
            return None
    
    async def update_message(
        self,
        channel: str,
        timestamp: str,
        message: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Update an existing message"""
        
        if not self.client:
            return False
        
        try:
            self.client.chat_update(
                channel=channel,
                ts=timestamp,
                text=message,
                blocks=blocks
            )
            return True
            
        except SlackApiError as e:
            logger.error(f"Failed to update Slack message: {e}")
            return False
    
    async def add_reaction(
        self,
        channel: str,
        timestamp: str,
        reaction: str
    ) -> bool:
        """Add a reaction to a message"""
        
        if not self.client:
            return False
        
        try:
            self.client.reactions_add(
                channel=channel,
                timestamp=timestamp,
                name=reaction
            )
            return True
            
        except SlackApiError as e:
            logger.error(f"Failed to add reaction: {e}")
            return False
    
    def _get_grafana_url(self) -> str:
        """Get Grafana dashboard URL"""
        grafana_url = os.getenv('GRAFANA_URL', 'https://grafana.example.com')
        return f"{grafana_url}/d/eks-cluster-monitoring"
    
    def _get_cloudwatch_url(self) -> str:
        """Get CloudWatch console URL"""
        region = os.getenv('AWS_REGION', 'us-east-1')
        cluster_name = os.getenv('EKS_CLUSTER_NAME', 'PetAdoptions-EKS')
        return f"https://{region}.console.aws.amazon.com/cloudwatch/home?region={region}#container-insights:performance/EKS:Cluster?~(query~(cluster~'{cluster_name}))"
