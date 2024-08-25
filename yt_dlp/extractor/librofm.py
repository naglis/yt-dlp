import json

from .common import InfoExtractor
from ..utils import urljoin, parse_iso8601, traverse_obj, join_nonempty


class LibroFmIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?libro\.fm/audiobooks/(?P<isbn>[0-9]{13})(?:-(?P<display_id>[a-z0-9-]+))?'
    _NETRC_MACHINE = 'librofm'
    _BASE_URL = "https://libro.fm"
    _LOGIN_URL = f"{_BASE_URL}/oauth/token"
    _USER_AGENT = "okhttp/3.14.9"
    _USER_AGENT_DOWNLOAD = (
        "AndroidDownloadManager/11 (Linux; U; Android 11; "
        "Android SDK built for x86_64 Build/RSR1.210722.013.A2)"
    )
    _CLIENT_VERSION = (
        "Android: Libro.fm 7.6.1 Build: 194 Device: Android SDK built for x86_64 "
        "(unknown sdk_phone_x86_64) AndroidOS: 11 SDK: 30"
    )
    _TESTS = [{
        'url': 'https://libro.fm/audiobooks/9781250761170-the-design',
        'md5': 'TODO: md5 sum of the first 10241 bytes of the video file (use --test)',
        'info_dict': {
            # For videos, only the 'id' and 'ext' fields are required to RUN the test:
            'id': '9781250761170',
            'ext': 'mp4',
            # Then if the test run fails, it will output the missing/incorrect fields.
            # Properties can be added as:
            # * A value, e.g.
            #     'title': 'Video title goes here',
            # * MD5 checksum; start the string with 'md5:', e.g.
            #     'description': 'md5:098f6bcd4621d373cade4e832627b4f6',
            # * A regular expression; start the string with 're:', e.g.
            #     'thumbnail': r're:^https?://.*\.jpg$',
            # * A count of elements in a list; start the string with 'count:', e.g.
            #     'tags': 'count:10',
            # * Any Python type, e.g.
            #     'view_count': int,
        }
    }]

    _ACCESS_TOKEN = None

    def _perform_login(self, username, password):
        if username == "__token__":
            self._ACCESS_TOKEN = password
        else:
            login_json = self._download_json(self._LOGIN_URL, None, note='Logging in', errnote='Login failed', headers={
                'Content-Type': 'application/json',
                'User-Agent': self._USER_AGENT,
            },
            data=json.dumps({
                "grant_type": "password",
                "username": username,
                "password": password,
            }).encode())
            access_token = login_json["access_token"]
            self.to_screen(f'The access token is {access_token!r}. Use it and "__token__" as the username to avoid login requests.')
            self._ACCESS_TOKEN = access_token

    def _process_part(self, part):
        return {
            'formats': [{
                 'url': part['url'],
                 # 'ext': 'zip',
                 'format': 'zip archive of mp3 files',
                 # 'acodec': 'mp3',
                 # 'container': 'zip',
                 'filesize': part['size_bytes'],
                 'http_headers': {
                     'User-Agent': self._USER_AGENT_DOWNLOAD,
                 },
            }]
        }
        
    def _real_extract(self, url):
        isbn, display_id = self._match_valid_url(url).group('isbn', 'display_id')

        if self._ACCESS_TOKEN is None:
            self.raise_login_required('Logging in is required in order to download purchased audiobooks', method='password')

        details = self._download_json(urljoin(self._BASE_URL, f'/api/v7/explore/audiobook_details/{isbn}'), isbn, headers={
            'Authorization': f'Bearer {self._ACCESS_TOKEN}',
            'User-Agent': self._USER_AGENT,
        }, note='Downloading audiobook details JSON', errnote='Failed to download audiobook details JSON')

        audiobook_data = traverse_obj(details, ('data', 'audiobook'))
        audiobook_info = audiobook_data.get('audiobook_info', {})

        thumbnail = None
        if (cover_url := audiobook_data.get("cover_url")):
            thumbnail = self._proto_relative_url(cover_url)

        info = {
            'id': isbn,
            'title': audiobook_data["title"],
            'alt_title': audiobook_data.get('subtitle'),
            'display_id': display_id,
            'thumbnail': thumbnail,
            'description': audiobook_data.get("description"),
            # XXX: Does this make sense (publisher being used as the value for uploader)?
            'uploader': audiobook_data.get('publisher'),
            'creators': audiobook_data.get('authors') or [],
            'timestamp': parse_iso8601(audiobook_data.get('created_at')),
            'release_timestamp': parse_iso8601(audiobook_data.get('publication_date')),
            'modified_timestamp': parse_iso8601(audiobook_data.get('updated_at')),
            'duration': audiobook_info.get('duration'),
            'categories': [g['name'] for g in audiobook_data.get('genres') or []],
            'cast': audiobook_info.get('narrators') or [],
        }

        # Does this make sense?
        if (series := audiobook_data.get('series')):
            info['series'] = series

            if (series_num := audiobook_data.get('series_num')) is not None:
                info['season_number'] = series_num

        manifest = self._download_json(urljoin(self._BASE_URL, "/api/v9/download-manifest"), isbn, query={'isbn': isbn, 'client_version': self._CLIENT_VERSION}, headers={
            'Authorization': f'Bearer {self._ACCESS_TOKEN}',
            'User-Agent': self._USER_AGENT,
        }, note='Downloading download manifest JSON', errnote='Failed to download download manifest JSON')

        parts = traverse_obj(manifest, ('parts', ...))
        entries = [{
            **info,
            'id': f'{isbn}-{i}',
            'title': join_nonempty(info.get('title'), f'(Part {i})', delim=' '),
            **self._process_part(part),
        } for i, part in enumerate(parts, start=1)]

        return {
            **info,
            **entries[0],
            'id': isbn,
            'title': info.get('title')
        } if len(entries) == 1 else {
            '_type': 'multi_video',
            **info,
            'entries': entries,
        }
