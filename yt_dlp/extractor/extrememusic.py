import json

from .common import InfoExtractor
from ..utils import ExtractorError, traverse_obj, str_or_none, int_or_none


class ExtremeMusicAlbumIE(InfoExtractor):
    _VALID_URL = r"https?://(?:www\.)?extrememusic\.com/albums/(?P<id>[0-9]+)"
    _TESTS = [
        {
            "url": "https://www.extrememusic.com/albums/6778",
            "info_dict": {
                "id": "6778",
                "ext": "mp4",
            },
        }
    ]

    def _real_extract(self, url):
        album_id = self._match_id(url)
        webpage = self._download_webpage(url, album_id)

        config = self._search_json(
            r'<script[^>]+id=(["\'])shoebox-extrememusic\1>', webpage, "config JSON", album_id, end_pattern="</script>"
        )
        print(config.keys())
        album_info = None
        for k, v in config.items():
            if k.startswith("album-"):
                album_info = json.loads(v)
                break

        if album_info is None:
            raise ExtractorError("Unable to extract album information", video_id=album_id)

        tracks = album_info.get("tracks") or []
        import pprint

        pprint.pprint(album_info)
        thumbnails = []
        for key, images in traverse_obj(album_info, ("album", "images"), default={}, get_all=False).items():
            for image in images:
                pass

        return {
            "id": album_id,
            **traverse_obj(
                album_info,
                {
                    "title": ("album", "title", {str_or_none}),
                    "description": ("album", "description", {str_or_none}),
                    "playlist_count": ("album", "track_count", {int_or_none}),
                },
            ),
        }
