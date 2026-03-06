"""Minimal qBittorrent Web API client (stdlib only)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any


class QbittorrentApiError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class QbittorrentConfig:
    base_url: str
    username: str
    password: str
    timeout_seconds: float = 10.0


class QbittorrentClient:
    """Thin thread-safe client for qBittorrent Web API v2."""

    def __init__(self, config: QbittorrentConfig) -> None:
        self._config = config
        self._base_url = config.base_url.rstrip('/')
        self._timeout_seconds = max(2.0, float(config.timeout_seconds))

        jar = CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

        self._lock = threading.RLock()
        self._is_logged_in = False

    @property
    def base_url(self) -> str:
        return self._base_url

    def login(self, *, force: bool = False) -> None:
        with self._lock:
            if self._is_logged_in and not force:
                return

            payload = {
                'username': self._config.username,
                'password': self._config.password,
            }
            response_text = self._request_locked(
                'POST',
                '/api/v2/auth/login',
                form_data=payload,
            ).strip()

            if response_text.lower() != 'ok.':
                raise QbittorrentApiError(
                    f'qBittorrent login failed: {response_text or "empty response"}',
                )

            self._is_logged_in = True

    def add_torrent(self, *, uri: str) -> None:
        value = (uri or '').strip()
        if not value:
            raise QbittorrentApiError('Torrent URI is empty.')

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/add',
            form_data={'urls': value},
        )

    def list_torrents(self, *, hashes: str = '') -> list[dict[str, Any]]:
        query = {}
        if hashes.strip():
            query['hashes'] = hashes.strip()

        response_text = self._request_with_auth(
            'GET',
            '/api/v2/torrents/info',
            query_params=query,
        )

        try:
            decoded = json.loads(response_text or '[]')
        except Exception as exc:  # noqa: BLE001
            raise QbittorrentApiError(f'Invalid qBittorrent JSON payload: {exc}') from exc

        if not isinstance(decoded, list):
            raise QbittorrentApiError('Unexpected qBittorrent response shape for torrents/info.')

        return [item for item in decoded if isinstance(item, dict)]

    def list_files(self, *, torrent_hash: str) -> list[dict[str, Any]]:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return []

        response_text = self._request_with_auth(
            'GET',
            '/api/v2/torrents/files',
            query_params={'hash': value},
        )

        try:
            decoded = json.loads(response_text or '[]')
        except Exception as exc:  # noqa: BLE001
            raise QbittorrentApiError(f'Invalid qBittorrent files payload: {exc}') from exc

        if not isinstance(decoded, list):
            raise QbittorrentApiError(
                'Unexpected qBittorrent response shape for torrents/files.',
            )

        return [item for item in decoded if isinstance(item, dict)]

    def pause_torrent(self, torrent_hash: str) -> None:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/pause',
            form_data={'hashes': value},
        )

    def resume_torrent(self, torrent_hash: str) -> None:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/resume',
            form_data={'hashes': value},
        )

    def delete_torrent(self, torrent_hash: str, *, delete_files: bool = False) -> None:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/delete',
            form_data={
                'hashes': value,
                'deleteFiles': 'true' if delete_files else 'false',
            },
        )

    def enable_sequential_download(self, torrent_hash: str) -> None:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/toggleSequentialDownload',
            form_data={'hashes': value},
        )

    def enable_first_last_piece_priority(self, torrent_hash: str) -> None:
        value = (torrent_hash or '').strip().lower()
        if not value:
            return

        self._request_with_auth(
            'POST',
            '/api/v2/torrents/toggleFirstLastPiecePrio',
            form_data={'hashes': value},
        )

    def _request_with_auth(
        self,
        method: str,
        path: str,
        *,
        form_data: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> str:
        with self._lock:
            if not self._is_logged_in:
                self.login(force=True)

            try:
                return self._request_locked(
                    method,
                    path,
                    form_data=form_data,
                    query_params=query_params,
                )
            except QbittorrentApiError as exc:
                if exc.status_code not in {401, 403}:
                    raise

            self._is_logged_in = False
            self.login(force=True)
            return self._request_locked(
                method,
                path,
                form_data=form_data,
                query_params=query_params,
            )

    def _request_locked(
        self,
        method: str,
        path: str,
        *,
        form_data: dict[str, str] | None = None,
        query_params: dict[str, str] | None = None,
    ) -> str:
        normalized_path = path if path.startswith('/') else f'/{path}'
        url = f'{self._base_url}{normalized_path}'

        if query_params:
            url = f"{url}?{urllib.parse.urlencode(query_params)}"

        data_bytes: bytes | None = None
        headers: dict[str, str] = {}
        if form_data is not None:
            data_bytes = urllib.parse.urlencode(form_data).encode('utf-8')
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        request = urllib.request.Request(
            url=url,
            data=data_bytes,
            method=method.upper(),
            headers=headers,
        )

        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                body = response.read().decode('utf-8', errors='replace')
                return body
        except urllib.error.HTTPError as exc:
            body = ''
            try:
                body = exc.read().decode('utf-8', errors='replace')
            except Exception:  # noqa: BLE001
                body = ''

            raise QbittorrentApiError(
                f'qBittorrent HTTP {exc.code} for {normalized_path}: {body}',
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise QbittorrentApiError(f'qBittorrent request failed: {exc}') from exc
        except Exception as exc:  # noqa: BLE001
            raise QbittorrentApiError(f'qBittorrent request exception: {exc}') from exc


