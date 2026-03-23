"""
User and Policy Management Module
Manages admin users and patient privacy policies
"""

import logging
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Optional
import json

logger = logging.getLogger(__name__)


class UserManager:
    """Manage users and privacy policies"""

    def __init__(self, config):
        self.config = config
        # In production, use proper database
        # For now, using in-memory storage
        self.users = self._load_default_users()
        self.policies = {}

    def _load_default_users(self) -> Dict:
        """Load default admin users"""
        return {
            'admin': {
                'id': 1,
                'username': 'admin',
                'password_hash': self._hash_password('admin123'),  # Change in production!
                'role': 'admin',
                'email': 'admin@mcs-data-labs.com',
                'created_at': datetime.now().isoformat()
            }
        }

    def _hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        user = self.users.get(username)
        if user and user['password_hash'] == self._hash_password(password):
            return {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'email': user['email']
            }
        return None

    def get_all_users(self) -> List[Dict]:
        """Get list of all admin users"""
        return [
            {
                'id': u['id'],
                'username': u['username'],
                'role': u['role'],
                'email': u['email'],
                'created_at': u['created_at']
            }
            for u in self.users.values()
        ]

    def create_user(self, username: str, password: str, role: str, email: str) -> Dict:
        """Create new admin user"""
        if username in self.users:
            raise ValueError(f"User {username} already exists")

        user_id = max([u['id'] for u in self.users.values()], default=0) + 1

        user = {
            'id': user_id,
            'username': username,
            'password_hash': self._hash_password(password),
            'role': role,
            'email': email,
            'created_at': datetime.now().isoformat()
        }

        self.users[username] = user
        logger.info(f"Created user: {username}")

        return {k: v for k, v in user.items() if k != 'password_hash'}

    def update_user(self, user_id: int, data: Dict) -> Dict:
        """Update user details"""
        user = next((u for u in self.users.values() if u['id'] == user_id), None)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if 'email' in data:
            user['email'] = data['email']
        if 'role' in data:
            user['role'] = data['role']
        if 'password' in data:
            user['password_hash'] = self._hash_password(data['password'])

        user['updated_at'] = datetime.now().isoformat()

        logger.info(f"Updated user {user_id}")
        return {k: v for k, v in user.items() if k != 'password_hash'}

    def delete_user(self, user_id: int):
        """Delete user"""
        user = next((u for u in self.users.values() if u['id'] == user_id), None)
        if not user:
            raise ValueError(f"User {user_id} not found")

        username = user['username']
        del self.users[username]
        logger.info(f"Deleted user {user_id}")

    def get_all_policies(self) -> List[Dict]:
        """Get all patient privacy policies"""
        # In production, query PostgreSQL for user policies
        return [
            {'unique_key': k, **v}
            for k, v in self.policies.items()
        ]

    def get_user_policy(self, unique_key: str) -> Optional[Dict]:
        """Get privacy policy for specific patient"""
        # In production, query PostgreSQL
        return self.policies.get(unique_key)

    def update_user_policy(self, unique_key: str, k_value: int, time_window: int,
                          override_consent: bool, admin_user_id: int) -> Dict:
        """Update patient privacy policy (remote anonymization)"""
        policy = {
            'unique_key': unique_key,
            'k_value': k_value,
            'time_window': time_window,
            'override_consent': override_consent,
            'updated_by': admin_user_id,
            'updated_at': datetime.now().isoformat()
        }

        self.policies[unique_key] = policy

        # In production: Update PostgreSQL and publish to MQTT
        logger.info(f"Updated policy for {unique_key}: K={k_value}, window={time_window}s")

        return policy

    def get_data_access_permissions(self) -> List[Dict]:
        """Get data access permissions"""
        # In production, query from database
        return []

    def grant_permission(self, user_id: int, resource_type: str, resource_id: str,
                        permission_level: str, granted_by: int) -> Dict:
        """Grant data access permission"""
        permission = {
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'permission_level': permission_level,
            'granted_by': granted_by,
            'granted_at': datetime.now().isoformat()
        }

        logger.info(f"Granted {permission_level} access to {resource_type}/{resource_id} for user {user_id}")
        return permission
