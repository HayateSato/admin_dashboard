"""
Audit Logging Module
"""

import logging
import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Log and manage audit events"""

    def __init__(self, config):
        self.config = config
        self.events = []
        self.audit_file = os.path.join(config.LOG_DIR, 'audit.log')

    def log_event(self, user_id: int, event_type: str, description: str,
                 ip_address: str, metadata: Optional[Dict] = None):
        """Log audit event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'event_type': event_type,
            'description': description,
            'ip_address': ip_address,
            'metadata': metadata or {}
        }

        self.events.append(event)

        # Write to file
        try:
            with open(self.audit_file, 'a') as f:
                f.write(f"{event['timestamp']} | User {user_id} | {event_type} | {description} | {ip_address}\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

        logger.info(f"Audit: {event_type} by user {user_id}")

    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Get recent audit events"""
        return sorted(self.events, key=lambda x: x['timestamp'], reverse=True)[:limit]

    def get_events(self, event_type: str = 'all', user_id: Optional[int] = None,
                  start_date: Optional[str] = None, end_date: Optional[str] = None,
                  limit: int = 100) -> List[Dict]:
        """Get filtered audit events"""
        filtered = self.events

        if event_type != 'all':
            filtered = [e for e in filtered if e['event_type'] == event_type]

        if user_id:
            filtered = [e for e in filtered if e['user_id'] == int(user_id)]

        if start_date:
            filtered = [e for e in filtered if e['timestamp'] >= start_date]

        if end_date:
            filtered = [e for e in filtered if e['timestamp'] <= end_date]

        return sorted(filtered, key=lambda x: x['timestamp'], reverse=True)[:limit]

    def export_to_csv(self, start_date: Optional[str], end_date: Optional[str]) -> str:
        """Export audit log to CSV"""
        events = self.get_events(start_date=start_date, end_date=end_date, limit=10000)

        filename = f"audit_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(self.config.LOG_DIR, filename)

        with open(filepath, 'w', newline='') as f:
            fieldnames = ['timestamp', 'user_id', 'event_type', 'description', 'ip_address']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for event in events:
                writer.writerow({k: event[k] for k in fieldnames})

        logger.info(f"Exported {len(events)} audit events to {filepath}")

        return filepath
