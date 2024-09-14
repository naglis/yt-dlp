from .common import InfoExtractor


class ExtremeMusicAlbumIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?extrememusic\.com/albums/(?P<id>[0-9]+)'
    _TESTS = [{
        'url': 'https://www.extrememusic.com/albums/6778',
        'info_dict': {
            'id': '6778',
            'ext': 'mp4',
        },
    }]

    def _real_extract(self, url):
        album_id = self._match_id(url)
        webpage = self._download_webpage(url, album_id)


        config = self._search_json(r'<script[^>]+id=(["\'])shoebox-extrememusic\1>', webpage, 'config JSON', album_id, end_pattern='</script>')

        return {
            'id': album_id,
            'title': '',
            'description': self._og_search_description(webpage),
            'uploader': self._search_regex(r'<div[^>]+id="uploader"[^>]*>([^<]+)<', webpage, 'uploader', fatal=False),
        }
