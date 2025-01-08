import functools
import json
import re

from .common import InfoExtractor
from ..utils import (
    float_or_none,
    int_or_none,
    parse_iso8601,
    parse_resolution,
    str_or_none,
    traverse_obj,
    try_call,
    url_or_none,
)


class RuutuIE(InfoExtractor):
    _VALID_URL = r'''https?://(?:www\.)?ruutu\.fi/(?:video|movie|stream)/(?P<id>\d+)'''
    _TESTS = [
        {
            'url': 'http://www.ruutu.fi/video/2058907',
            'md5': '210ed58cd15afa61c25dc020986083a4',
            'info_dict': {
                'id': '2058907',
                'ext': 'mp4',
                'title': 'Oletko aina halunnut tietää mitä tapahtuu vain hetki ennen lähetystä? - Nyt se selvisi!',
                'description': 'md5:cfc6ccf0e57a814360df464a91ff67d6',
                'thumbnail': r're:^https?://.*\.jpg$',
                'duration': 114,
                'age_limit': 0,
                'upload_date': '20150508',
                'channel': 'HitMix',
                'channel_id': '55',
                'timestamp': 1431083940,
                'media_type': 'video_clip',
                'chapters': [],
                'categories': [],
            },
        },
        {
            'url': 'http://www.ruutu.fi/video/2057306',
            'md5': '12f3b0b64087547b3747e5fbd092907f',
            'info_dict': {
                'id': '2057306',
                'ext': 'mp4',
                'title': 'Superpesis: katso koko kausi Ruudussa',
                'description': 'md5:bfb7336df2a12dc21d18fa696c9f8f23',
                'thumbnail': r're:^https?://.*\.jpg$',
                'duration': 40,
                'age_limit': 0,
                'upload_date': '20150507',
                'series': 'Superpesis',
                'categories': ['Urheilu', 'Pesäpallo'],
                'media_type': 'video_clip',
                'channel_id': '93',
                'series_id': '1379173',
                'timestamp': 1430990580,
                'chapters': [],
                'channel': 'Ruutu.fi',
            },
        },
    ]
    _API_BASE = 'https://mcc.nm-ovp.nelonenmedia.fi'

    @classmethod
    def _extract_embed_urls(cls, url, webpage):
        # nelonen.fi
        settings = try_call(
            lambda: json.loads(re.search(
                r'jQuery\.extend\(Drupal\.settings, ({.+?})\);', webpage).group(1), strict=False))
        if settings:
            video_id = traverse_obj(settings, (
                'mediaCrossbowSettings', 'file', 'field_crossbow_video_id', 'und', 0, 'value'))
            if video_id:
                return [f'http://www.ruutu.fi/video/{video_id}']
        # hs.fi and is.fi
        settings = try_call(
            lambda: json.loads(re.search(
                '(?s)<script[^>]+id=[\'"]__NEXT_DATA__[\'"][^>]*>([^<]+)</script>',
                webpage).group(1), strict=False))
        if settings:
            video_ids = set(traverse_obj(settings, (
                'props', 'pageProps', 'page', 'assetData', 'splitBody', ..., 'video', 'sourceId')) or [])
            if video_ids:
                return [f'http://www.ruutu.fi/video/{v}' for v in video_ids]
            video_id = traverse_obj(settings, (
                'props', 'pageProps', 'page', 'assetData', 'mainVideo', 'sourceId'))
            if video_id:
                return [f'http://www.ruutu.fi/video/{video_id}']

    def _extract_thumbnails(self, media):
        thumbnails = []
        for name, image_map in (media.get('images') or {}).items():
            for resolution, url in image_map.items():
                url = url_or_none(url)
                if not url:
                    continue

                thumbnails.append({
                    'id': f'{name}_{resolution}',
                    'url': url,
                    **parse_resolution(resolution),
                })

        return thumbnails

    def _extract_formats_and_subtitles(self, video_id, media):
        formats, subtitles, seen_urls = [], {}, set()
        for name, fmt in (media.get('streamUrls') or {}).items():
            if not fmt or fmt.get('withCredentials'):
                continue

            url = url_or_none(fmt.get('url'))
            if not url or url in seen_urls:
                continue
            else:
                seen_urls.add(url)

            if name in ('android', 'apple', 'audioHls', 'cast', 'samsung', 'webHls'):
                fmts, subs = self._extract_m3u8_formats_and_subtitles(url, video_id, fatal=False)
                formats.extend(fmts)
                self._merge_subtitles(subs, target=subtitles)
            elif name == 'dash':
                formats.extend(self._extract_mpd_formats(url, video_id, fatal=False))
            else:
                fmt = {
                    'format_id': name,
                    'url': url,
                }

                if name == 'audioMp3':
                    fmt.update(acodec='mp3', vcodec='mp3')
                elif name == 'http':
                    # For some videos the HTTP URL returns 404.
                    fmt.update(preference=-1001)

                formats.append(fmt)

        self._merge_subtitles({
            s['language']: [{
                'name': s.get('name'),
                'url': s['url'],
        }] for s in (media.get('subtitles') or [])}, target=subtitles)

        return formats, subtitles

    def _real_extract(self, url):
        video_id = self._match_id(url)

        video_json = self._download_json(
            f'{self._API_BASE}/v2/media/{video_id}', video_id)

        media = traverse_obj(video_json, ('clip', 'playback', 'media'), default={})
        formats, subtitles = self._extract_formats_and_subtitles(video_id, media)

        if not formats:
            if traverse_obj(video_json, ('clip', 'playback', 'drm', 'enabled')):
                self.report_drm(video_id)

        metadata = traverse_obj(video_json, ('clip', 'metadata'), default={}, expected_type=dict)
        timestamp = min(traverse_obj(metadata, ('online_rights', ..., 'start_date', {parse_iso8601}), default=[], expected_type=int), default=None)

        duration = traverse_obj(video_json, ('clip', 'playback', 'runtime', {float_or_none}))
        chapters = []
        if duration is not None:
            end_credits_start = traverse_obj(video_json, ('clip', 'playback', 'endCredits', {float_or_none}))
            if end_credits_start is not None:
                chapters.append({
                    'start_time': end_credits_start,
                    'end_time': duration,
                    'title': 'End Credits',
                })

        return {
            'id': video_id,
            'duration': duration,
            'chapters': chapters,
            'timestamp': timestamp,
            **traverse_obj(
                metadata, {
                    'title': ('programName', {str_or_none}),
                    'description': ('description', {str_or_none}),
                    'age_limit': ('ageLimit', {functools.partial(int_or_none, default=0)}),
                    'channel': ('channelName', {str_or_none}),
                    'channel_id': ('channelId', {str_or_none}),
                    'series': ('seriesName', {str_or_none}),
                    'series_id': ('seriesId', {str_or_none}),
                }),
            **traverse_obj(video_json, {
                'categories': ('clip', 'passthroughVariables', 'themes', {lambda v: v.split(',') if v else []}),
                'media_type': ('clip', 'playback', 'mediaType', {str_or_none}),
            }),
            'formats': formats,
            'subtitles': subtitles,
            'thumbnails': self._extract_thumbnails(media),
        }

        # formats = []
        # processed_urls = []

        # def extract_formats(node):
        #     for child in node:
        #         if child.tag.endswith('Files'):
        #             extract_formats(child)
        #         elif child.tag.endswith('File'):
        #             video_url = child.text
        #             if (not video_url or video_url in processed_urls
        #                     or any(p in video_url for p in ('NOT_USED', 'NOT-USED'))):
        #                 continue
        #             processed_urls.append(video_url)
        #             ext = determine_ext(video_url)
        #             auth_video_url = url_or_none(self._download_webpage(
        #                 f'{self._API_BASE}/auth/access/v2', video_id,
        #                 note=f'Downloading authenticated {ext} stream URL',
        #                 fatal=False, query={'stream': video_url}))
        #             if auth_video_url:
        #                 processed_urls.append(auth_video_url)
        #                 video_url = auth_video_url
        #             if ext == 'm3u8':
        #                 formats.extend(self._extract_m3u8_formats(
        #                     video_url, video_id, 'mp4',
        #                     entry_protocol='m3u8_native', m3u8_id='hls',
        #                     fatal=False))
        #             elif ext == 'f4m':
        #                 formats.extend(self._extract_f4m_formats(
        #                     video_url, video_id, f4m_id='hds', fatal=False))
        #             elif ext == 'mpd':
        #                 # video-only and audio-only streams are of different
        #                 # duration resulting in out of sync issue
        #                 continue
        #                 formats.extend(self._extract_mpd_formats(
        #                     video_url, video_id, mpd_id='dash', fatal=False))
        #             elif ext == 'mp3' or child.tag == 'AudioMediaFile':
        #                 formats.append({
        #                     'format_id': 'audio',
        #                     'url': video_url,
        #                     'vcodec': 'none',
        #                 })
        #             else:
        #                 proto = urllib.parse.urlparse(video_url).scheme
        #                 if not child.tag.startswith('HTTP') and proto != 'rtmp':
        #                     continue
        #                 preference = -1 if proto == 'rtmp' else 1
        #                 label = child.get('label')
        #                 tbr = int_or_none(child.get('bitrate'))
        #                 format_id = f'{proto}-{label if label else tbr}' if label or tbr else proto
        #                 if not self._is_valid_url(video_url, video_id, format_id):
        #                     continue
        #                 width, height = (int_or_none(x) for x in child.get('resolution', 'x').split('x')[:2])
        #                 formats.append({
        #                     'format_id': format_id,
        #                     'url': video_url,
        #                     'width': width,
        #                     'height': height,
        #                     'tbr': tbr,
        #                     'preference': preference,
        #                 })

        # extract_formats(video_xml.find('./Clip'))

        # def pv(name):
        #     value = try_call(lambda: find_xpath_attr(
        #         video_xml, './Clip/PassthroughVariables/variable', 'name', name).get('value'))
        #     if value != 'NA':
        #         return value or None

        # if not formats:
        #     if (not self.get_param('allow_unplayable_formats')
        #             and xpath_text(video_xml, './Clip/DRM', default=None)):
        #         self.report_drm(video_id)
        #     ns_st_cds = pv('ns_st_cds')
        #     if ns_st_cds != 'free':
        #         raise ExtractorError(f'This video is {ns_st_cds}.', expected=True)

        # themes = pv('themes')

        # return {
        #     'id': video_id,
        #     'title': xpath_attr(video_xml, './/Behavior/Program', 'program_name', 'title', fatal=True),
        #     'description': xpath_attr(video_xml, './/Behavior/Program', 'description', 'description'),
        #     'thumbnail': xpath_attr(video_xml, './/Behavior/Startpicture', 'href', 'thumbnail'),
        #     'duration': int_or_none(xpath_text(video_xml, './/Runtime', 'duration')) or int_or_none(pv('runtime')),
        #     'age_limit': int_or_none(xpath_text(video_xml, './/AgeLimit', 'age limit')),
        #     'upload_date': unified_strdate(pv('date_start')),
        #     'series': pv('series_name'),
        #     'season_number': int_or_none(pv('season_number')),
        #     'episode_number': int_or_none(pv('episode_number')),
        #     'categories': themes.split(',') if themes else None,
        #     'formats': formats,
        # }
