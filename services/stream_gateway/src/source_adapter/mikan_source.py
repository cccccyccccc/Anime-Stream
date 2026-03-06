"""Mikan source adapter for stream gateway.

This module extracts anime summary/detail payloads from mikan.tangbai.cc pages
without external dependencies, so it can run in minimal Python environments.
"""

from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


class MikanSourceAdapter:
    def __init__(
        self,
        *,
        base_url: str = 'https://mikan.tangbai.cc',
        request_timeout: float = 10.0,
        cache_ttl_seconds: int = 180,
        max_home_items: int = 24,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._request_timeout = max(2.0, request_timeout)
        self._cache_ttl_seconds = max(10, cache_ttl_seconds)
        self._max_home_items = max(8, max_home_items)

        self._home_cache: _CacheEntry | None = None
        self._search_cache: dict[str, _CacheEntry] = {}
        self._detail_cache: dict[str, _CacheEntry] = {}

    @property
    def base_url(self) -> str:
        return self._base_url

    def fetch_home(self) -> list[dict[str, Any]]:
        cached = self._read_cache(self._home_cache)
        if cached is not None:
            return cached

        html_text = self._fetch_text('/')
        items = self._parse_home_cards(html_text)
        if len(items) > self._max_home_items:
            items = items[: self._max_home_items]

        self._home_cache = self._new_cache(items)
        return items

    def search(self, query: str) -> list[dict[str, Any]]:
        normalized_query = self._normalize_spaces(query)
        if not normalized_query:
            return self.fetch_home()

        cache_key = normalized_query.lower()
        cached = self._read_cache(self._search_cache.get(cache_key))
        if cached is not None:
            return cached

        search_url = f'/Home/Search?searchstr={quote_plus(normalized_query)}'
        html_text = self._fetch_text(search_url)
        items = self._parse_search_cards(html_text)

        if not items:
            lowered = normalized_query.lower()
            fallback = self.fetch_home()
            items = [
                item
                for item in fallback
                if lowered in str(item.get('title', '')).lower()
            ]

        self._search_cache[cache_key] = self._new_cache(items)
        return items

    def fetch_detail(self, anime_id: str) -> dict[str, Any]:
        normalized_id = self._normalize_id(anime_id)
        if not normalized_id:
            raise ValueError('anime_id is empty')

        cached = self._read_cache(self._detail_cache.get(normalized_id))
        if cached is not None:
            return cached

        html_text = self._fetch_text(f'/Home/Bangumi/{normalized_id}')
        detail = self._parse_detail(html_text, normalized_id)

        self._detail_cache[normalized_id] = self._new_cache(detail)
        return detail

    def resolve_episode(self, anime_id: str, episode_id: str) -> dict[str, Any] | None:
        normalized_episode = self._normalize_spaces(episode_id)

        detail = self.fetch_detail(anime_id)
        episodes = detail.get('episodes')
        if not isinstance(episodes, list):
            return None

        episode_items = [item for item in episodes if isinstance(item, dict)]
        if not episode_items:
            return None

        normalized_episode_lower = normalized_episode.lower()
        if not normalized_episode or normalized_episode_lower in {'latest', 'newest', 'last'}:
            return self._pick_latest_episode_with_source(episode_items)

        for item in episode_items:
            if str(item.get('id', '')).strip().lower() == normalized_episode_lower:
                return item

        target_episode_no = self._extract_episode_number(normalized_episode)
        if target_episode_no is not None:
            for item in episode_items:
                item_episode_no = self._extract_episode_number(str(item.get('id', '')))
                if item_episode_no is None:
                    item_episode_no = self._extract_episode_number(str(item.get('title', '')))

                if item_episode_no is not None and item_episode_no == target_episode_no:
                    return item

        return self._pick_latest_episode_with_source(episode_items)

    def _pick_latest_episode_with_source(
        self,
        episode_items: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for item in episode_items:
            magnet = self._normalize_spaces(str(item.get('magnet', '')))
            torrent_url = self._normalize_spaces(str(item.get('torrentUrl', '')))
            if magnet or torrent_url:
                return item

        return episode_items[0] if episode_items else None

    def _extract_episode_number(self, text: str) -> int | None:
        normalized = self._normalize_spaces(text).lower()
        if not normalized:
            return None

        match = re.search(
            r'(?:^|\b)(?:ep|e|episode)[\s._-]*(\d{1,4})(?:\b|$)',
            normalized,
            flags=re.IGNORECASE,
        )
        if match is None:
            match = re.search(r'(?:-|_|\s)(\d{1,4})(?:\b|$)', normalized)

        if match is None and normalized.isdigit():
            try:
                return int(normalized)
            except Exception:  # noqa: BLE001
                return None

        if match is None:
            return None

        try:
            return int(match.group(1))
        except Exception:  # noqa: BLE001
            return None

    def _fetch_text(self, path: str) -> str:
        absolute_url = self._absolute_url(path)
        req = Request(
            absolute_url,
            headers={
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/124.0.0.0 Safari/537.36'
                ),
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            },
        )

        with urlopen(req, timeout=self._request_timeout) as response:
            charset = response.headers.get_content_charset() or 'utf-8'
            payload = response.read()

        return payload.decode(charset, errors='ignore')

    def _parse_home_cards(self, html_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for match in re.finditer(
            r'<li>[\s\S]*?data-bangumiid="(?P<id>\d+)"[\s\S]*?</li>',
            html_text,
        ):
            block = match.group(0)
            anime_id = match.group('id')
            if anime_id in seen:
                continue

            title = self._extract_title_from_card_block(block, anime_id)
            if not title:
                continue

            date_text = self._clean_text(
                self._extract_first(r'<div class="date-text">([\s\S]*?)</div>', block)
            )
            episode_num = self._clean_text(
                self._extract_first(r'<div class="num-node[^>]*>\s*([^<]+)\s*</div>', block)
            )

            published = date_text.replace('更新', '').strip()
            subtitle_parts = []
            if date_text:
                subtitle_parts.append(date_text)
            if episode_num:
                subtitle_parts.append(f'EP {episode_num}')

            item = {
                'id': anime_id,
                'title': title,
                'subtitle': ' · '.join(subtitle_parts) if subtitle_parts else 'Latest update',
                'latestEpisodeId': 'latest',
                'source': 'mikan.tangbai.cc',
                'posterUrl': self._absolute_url(
                    self._extract_first(r'data-src="([^"]+)"', block)
                ),
                'fansubGroup': '',
                'publishedAt': published,
            }

            items.append(item)
            seen.add(anime_id)

        return items

    def _parse_search_cards(self, html_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for match in re.finditer(
            r'<li>[\s\S]*?<a href="/Home/Bangumi/(?P<id>\d+)"[\s\S]*?</li>',
            html_text,
        ):
            block = match.group(0)
            anime_id = match.group('id')
            if anime_id in seen:
                continue

            title = self._extract_title_from_card_block(block, anime_id)
            if not title:
                continue

            date_text = self._clean_text(
                self._extract_first(r'<div class="date-text">([\s\S]*?)</div>', block)
            )
            episode_num = self._clean_text(
                self._extract_first(r'<div class="num-node[^>]*>\s*([^<]+)\s*</div>', block)
            )
            published = date_text.replace('更新', '').strip()

            subtitle_parts = []
            if date_text:
                subtitle_parts.append(date_text)
            if episode_num:
                subtitle_parts.append(f'EP {episode_num}')
            if not subtitle_parts:
                subtitle_parts.append('Search result')

            item = {
                'id': anime_id,
                'title': title,
                'subtitle': ' · '.join(subtitle_parts),
                'latestEpisodeId': 'latest',
                'source': 'mikan.tangbai.cc',
                'posterUrl': self._absolute_url(
                    self._extract_first(r'data-src="([^"]+)"', block)
                ),
                'fansubGroup': '',
                'publishedAt': published,
            }

            items.append(item)
            seen.add(anime_id)

        return items

    def _extract_title_from_card_block(self, block: str, anime_id: str) -> str:
        from_anchor = self._clean_text(
            self._extract_first(
                rf'href="/Home/Bangumi/{re.escape(anime_id)}"[^>]*>([\s\S]*?)</a>',
                block,
            )
        )
        if from_anchor:
            return from_anchor

        from_title_attr = self._clean_text(
            self._extract_first(r'class="an-text"[^>]*title="([^"]+)"', block)
        )
        if from_title_attr:
            return from_title_attr

        from_text_div = self._clean_text(
            self._extract_first(r'class="an-text"[^>]*>([\s\S]*?)</div>', block)
        )
        return from_text_div

    def _parse_detail(self, html_text: str, anime_id: str) -> dict[str, Any]:
        title_html = self._extract_first(
            r'<p class="bangumi-title">([\s\S]*?)</p>',
            html_text,
        )
        title = self._clean_text(title_html)

        if not title:
            title = self._clean_text(
                self._extract_first(r'<title>[\s\S]*?-\s*([\s\S]*?)</title>', html_text)
            )

        poster = self._absolute_url(
            self._extract_first(
                r'class="bangumi-poster"[^>]*url\(["\']?([^"\')]+)',
                html_text,
            )
        )

        info_lines_raw = re.findall(
            r'<p class="bangumi-info">([\s\S]*?)</p>',
            html_text,
        )
        info_lines = [self._clean_text(line) for line in info_lines_raw]
        info_lines = [line for line in info_lines if line]

        description = '\n'.join(info_lines) if info_lines else 'No description from source.'
        tags = self._extract_tags_from_info_lines(info_lines)

        episodes = self._parse_episode_rows(html_text)
        first_episode = episodes[0] if episodes else {}

        fansub_group = self._extract_fansub_group(str(first_episode.get('title', '')))
        published_at = str(first_episode.get('publishedAt', ''))

        return {
            'id': anime_id,
            'title': title,
            'description': description,
            'source': 'mikan.tangbai.cc',
            'posterUrl': poster,
            'fansubGroup': fansub_group,
            'publishedAt': published_at,
            'tags': tags,
            'episodes': episodes,
        }

    def _parse_episode_rows(self, html_text: str) -> list[dict[str, Any]]:
        episodes: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for row_match in re.finditer(
            r'<tr>[\s\S]*?class="js-episode-select"[\s\S]*?</tr>',
            html_text,
        ):
            row_html = row_match.group(0)

            magnet = self._normalize_magnet(
                self._extract_first_of(
                    [
                        r'data-magnet="([^"]+)"',
                        r'data-clipboard-text="(magnet:[^"]+)"',
                        r'href="(magnet:[^"]+)"',
                        r'value="(magnet:[^"]+)"',
                    ],
                    row_html,
                    unescape_html=True,
                )
            )

            episode_id = self._extract_first_of(
                [
                    r'href="/Home/Episode/([A-Za-z0-9]+)"',
                    r'data-episodeid="([A-Za-z0-9]+)"',
                    r'data-episode-id="([A-Za-z0-9]+)"',
                ],
                row_html,
            )
            if not episode_id and magnet:
                hash_match = re.search(r'btih:([A-Za-z0-9]+)', magnet, flags=re.IGNORECASE)
                if hash_match:
                    episode_id = hash_match.group(1)

            title = self._clean_text(
                self._extract_first_of(
                    [
                        r'class="magnet-link-wrap"[^>]*>([\s\S]*?)</a>',
                        r'class="magnet-link"[^>]*>([\s\S]*?)</a>',
                        r'<a[^>]*target="_blank"[^>]*>([\s\S]*?)</a>',
                    ],
                    row_html,
                )
            )
            size = self._clean_text(
                self._extract_first(
                    r'<td>\s*([0-9]+(?:\.[0-9]+)?\s*(?:KB|MB|GB|TB))\s*</td>',
                    row_html,
                )
            )
            published_at = self._clean_text(
                self._extract_first(
                    r'<td>\s*([0-9]{4}/[0-9]{2}/[0-9]{2}\s*[0-9]{2}:[0-9]{2})\s*</td>',
                    row_html,
                )
            )

            torrent_rel = self._extract_first_of(
                [
                    r'href="(/Download/[^"]+\.torrent[^"]*)"',
                    r'href="(/Download/[^"]+)"',
                    r'data-torrent="(/Download/[^"]+)"',
                    r'data-url="(/Download/[^"]+)"',
                ],
                row_html,
            )

            normalized_id = self._normalize_spaces(episode_id)
            if not normalized_id:
                normalized_id = self._build_episode_id_from_title(title, len(episodes) + 1)

            if normalized_id in seen_ids:
                continue

            episode = {
                'id': normalized_id,
                'title': title or f'Episode {len(episodes) + 1}',
                'subtitle': size or 'Unknown size',
                'publishedAt': published_at,
                'magnet': magnet,
                'torrentUrl': self._absolute_url(torrent_rel),
            }

            episodes.append(episode)
            seen_ids.add(normalized_id)

        return episodes

    def _extract_first_of(
        self,
        patterns: list[str],
        text: str,
        *,
        unescape_html: bool = False,
    ) -> str:
        for pattern in patterns:
            value = self._extract_first(pattern, text)
            if unescape_html:
                value = html.unescape(value)

            normalized = self._normalize_spaces(value)
            if normalized:
                return normalized

        return ''

    def _normalize_magnet(self, value: str) -> str:
        raw = self._normalize_spaces(html.unescape(value))
        if not raw:
            return ''

        match = re.search(r'(magnet:\?[^"\'\s<>]+)', raw, flags=re.IGNORECASE)
        if match is not None:
            return match.group(1)

        if raw.lower().startswith('magnet:?'):
            return raw

        return ''
    def _extract_tags_from_info_lines(self, info_lines: list[str]) -> list[str]:
        tags: list[str] = []

        for line in info_lines:
            if '：' in line:
                key = self._normalize_spaces(line.split('：', 1)[0])
                if key:
                    tags.append(key)

        deduped: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            lowered = tag.lower()
            if lowered in seen:
                continue
            deduped.append(tag)
            seen.add(lowered)

        return deduped

    def _extract_fansub_group(self, title: str) -> str:
        normalized = self._normalize_spaces(title)
        if not normalized:
            return ''

        match = re.match(r'^\[([^\]]+)\]', normalized)
        if not match:
            return ''

        return self._normalize_spaces(match.group(1))

    def _build_episode_id_from_title(self, title: str, index: int) -> str:
        normalized_title = self._normalize_spaces(title)
        if not normalized_title:
            return f'ep-{index}'

        hash_key = abs(hash(normalized_title)) % (10**10)
        return f'ep-{hash_key}'

    def _absolute_url(self, maybe_relative: str) -> str:
        value = self._normalize_spaces(maybe_relative)
        if not value:
            return ''
        if value.startswith('http://') or value.startswith('https://'):
            return value
        return urljoin(f'{self._base_url}/', value.lstrip('/'))

    def _extract_first(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ''
        return match.group(1)

    def _clean_text(self, raw: str) -> str:
        if not raw:
            return ''
        without_tags = re.sub(r'<br\s*/?>', ' ', raw, flags=re.IGNORECASE)
        without_tags = re.sub(r'<[^>]+>', ' ', without_tags)
        unescaped = html.unescape(without_tags)
        return self._normalize_spaces(unescaped)

    def _normalize_spaces(self, value: str) -> str:
        return re.sub(r'\s+', ' ', value or '').strip()

    def _normalize_id(self, anime_id: str) -> str:
        value = self._normalize_spaces(anime_id)
        if not value:
            return ''

        if value.isdigit():
            return value

        digits = re.findall(r'\d+', value)
        if digits:
            return digits[0]

        return value

    def _new_cache(self, value: Any) -> _CacheEntry:
        return _CacheEntry(
            expires_at=time.time() + self._cache_ttl_seconds,
            value=value,
        )

    def _read_cache(self, cache_entry: _CacheEntry | None) -> Any | None:
        if cache_entry is None:
            return None
        if cache_entry.expires_at <= time.time():
            return None
        return cache_entry.value




