import json

from .common import InfoExtractor
from ..utils import ExtractorError, traverse_obj, str_or_none, int_or_none, url_or_none


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

    @staticmethod
    def _collect_images(info):
        def prepare_thumbnail(image_type, image, webp=False):
            w, h = int_or_none(image.get("width")), int_or_none(image.get("width"))
            thumb_id = image_type
            if w is not None:
                thumb_id = f"{thumb_id}_{w}"
            if webp:
                thumb_id = f"{thumb_id}_webp"

            url = url_or_none(image.get("url"))
            if webp:
                url = url_or_none(image.get("webp"))

            return {
                "id": thumb_id,
                "url": url,
                "width": w,
                "height": h,
            }

                
        thumbnails = []
        for image_type, images in (info.get('images') or {}).items():
            for image in images:
                thumbnails.append(prepare_thumbnail(image_type, image))
                thumbnails.append(prepare_thumbnail(image_type, image, webp=True))

        if not thumbnails:
            seen_urls = set()
            for thumb_id in ("detail", "large", "small"):
                url = url_or_none(info.get(f"image_{thumb_id}_url"))
                if url is not None and url not in seen_urls:
                    thumbnails.append({
                        "id": thumb_id,
                        "url": url,
                    })
                    seen_urls.add(url)

        return thumbnails
            
    def _real_extract(self, url):
        album_id = self._match_id(url)
        webpage = self._download_webpage(url, album_id)

        config = self._search_json(
            r'<script[^>]+id=(["\'])shoebox-extrememusic\1>', webpage, "config JSON", album_id, end_pattern="</script>"
        )

        album_info = None
        for k, v in config.items():
            if k.startswith("album-"):
                album_info = json.loads(v)
                break

        if album_info is None:
            raise ExtractorError("Unable to extract album information", video_id=album_id)

        track_sounds = {}
        for ts in album_info.get("track_sounds") or []:
            track_sounds[ts['id']] = ts

        entries = []
        for track in album_info.get("tracks") or []:
            entry = {
                **traverse_obj(track, {
                    'id': ('id', {int_or_none}),
                    'track': ('title', {str_or_none}),
                    'thumbnails': ({self._collect_images},),
                    'tags': ('keywords', ..., 'label', {str_or_none}),
                    'artists': ('artists', ..., 'name', {str_or_none}),
                    'composers': ('composers', ..., 'name', {str_or_none}),
                    'genres': ('genre', ..., 'label', {str_or_none}),
                }),
                # 'thumbnails': self._collect_images(track),
            }
            entries.append(entry)
        import pprint

        pprint.pprint(album_info)

        r= self.playlist_result(
            entries,
            playlist_id=album_id,
            **traverse_obj(
                album_info,
                {
                    "playlist_title": ("album", "title", {str_or_none}),
                    "playlist_description": ("album", "description", {str_or_none}),
                    "playlist_count": ("album", "track_count", {int_or_none}),
                    "thumbnails": ("album", {self._collect_images}),
                },
            ),
        )
        print(r)
        return r
        # return {
        #     "id": album_id,
        #     # "thumbnails": self._collect_images(album_info.get("album")),
        # }
