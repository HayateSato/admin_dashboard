"""
Central Anonymization API — Python Client

Drop this file into any Python project (Flutter companion scripts, batch jobs,
other services) that needs to call the Central Anonymization API server.

Usage:
    from anon_client import CentralAnonClient

    client = CentralAnonClient(
        base_url='https://your-server:6000',
        api_key='your-api-key',   # omit if server has no API_KEY set
        verify_ssl=False,         # False for self-signed cert; True for Let's Encrypt
    )

    result = client.anonymize(records, k_value=10)
"""

from __future__ import annotations

import time
import logging
from typing import List, Dict, Optional, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class AnonClientError(Exception):
    """Raised when the server returns an error response."""


class CentralAnonClient:
    """
    HTTP client for the Central Anonymization API server.

    Parameters
    ----------
    base_url : str
        Server root URL, e.g. ``https://localhost:6000``.
    api_key : str, optional
        Value for the ``X-API-Key`` header. Leave empty if the server
        was started without ``API_KEY``.
    verify_ssl : bool
        ``True``  → verify TLS certificate (use for Let's Encrypt / production).
        ``False`` → skip verification (use for self-signed / dev).
    timeout : int
        Request timeout in seconds (default 120 — anonymizing large batches
        can take a while).
    retries : int
        Number of automatic retries on network errors (default 2).
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 120,
        retries: int = 2,
    ) -> None:
        self.base_url   = base_url.rstrip('/')
        self.verify_ssl = verify_ssl
        self.timeout    = timeout

        self._session = requests.Session()
        if api_key:
            self._session.headers['X-API-Key'] = api_key
        self._session.headers['Content-Type'] = 'application/json'

        # Automatic retry on connection errors / 5xx (not on 4xx — those are caller mistakes)
        retry = Retry(
            total=retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['GET', 'POST'],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount('https://', adapter)
        self._session.mount('http://',  adapter)

    # ── Public API ──────────────────────────────────────────────────────────

    def health_check(self) -> Dict[str, Any]:
        """
        Check whether the server is running and the hierarchy is loaded.

        Returns
        -------
        dict
            ``{'status': 'ok', 'hierarchy_loaded': True, 'hierarchy_size': 5001, ...}``
        """
        return self._get('/health')

    def get_info(self) -> Dict[str, Any]:
        """
        Return server configuration (algorithm details, supported k-values, etc.).
        Requires auth if API_KEY is set on the server.
        """
        return self._get('/api/v1/info')

    def anonymize(
        self,
        records: List[Dict[str, Any]],
        k_value: int = 10,
        batch_size_seconds: int = 5,
    ) -> Dict[str, Any]:
        """
        Anonymize a list of ECG records.

        Parameters
        ----------
        records : list of dict
            Each record must have at least:
            - ``timestamp`` (int, milliseconds since epoch)
            - ``ecg``       (int, value in range -2500 to 2500)

            Any extra fields (``unique_key``, ``deviceAddress``, etc.) are
            preserved and passed back in the response unchanged.

        k_value : int
            k-anonymity level. One of: 5, 10, 20, 50.

        batch_size_seconds : int
            Time-window width for grouping records before applying k-anonymity.
            Smaller windows = faster processing but potentially lower utility.
            Matches the default used by the admin dashboard (5 seconds).

        Returns
        -------
        dict
            Full server response::

                {
                    'success': True,
                    'anonymized_records': [ {...}, ... ],
                    'stats': {
                        'total_input':        N,
                        'total_output':       N,
                        'k_value_used':       10,
                        'batch_size_seconds': 5,
                        'batches_processed':  M,
                        'validation':         { ... }
                    }
                }

        Raises
        ------
        AnonClientError
            If the server returns ``success: false``.
        requests.HTTPError
            If the HTTP status is 4xx / 5xx.
        """
        payload = {
            'records':            records,
            'k_value':            k_value,
            'batch_size_seconds': batch_size_seconds,
        }
        response = self._post('/api/v1/anonymize', payload)
        if not response.get('success'):
            raise AnonClientError(response.get('error', 'Unknown server error'))
        return response

    def anonymize_records_only(
        self,
        records: List[Dict[str, Any]],
        k_value: int = 10,
        batch_size_seconds: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Convenience wrapper — same as :meth:`anonymize` but returns only
        the ``anonymized_records`` list.
        """
        return self.anonymize(records, k_value, batch_size_seconds)['anonymized_records']

    def is_healthy(self) -> bool:
        """Return True if the server is reachable and the hierarchy is loaded."""
        try:
            h = self.health_check()
            return h.get('status') == 'ok' and h.get('hierarchy_loaded', False)
        except Exception:
            return False

    # ── Internal helpers ────────────────────────────────────────────────────

    def _get(self, path: str) -> Dict[str, Any]:
        url = self.base_url + path
        resp = self._session.get(url, verify=self.verify_ssl, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: dict) -> Dict[str, Any]:
        url = self.base_url + path
        resp = self._session.post(url, json=payload, verify=self.verify_ssl, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()
