from .common import PostProcessor


class ExtractZipPP(PostProcessor):

    def run(self, information):
        # We only run when the extension is ".temp", since ".zip" is not allowed by yt-dlp.
        if information['ext'] != 'temp':
            return [], information

        # filepath = information['filepath']
        return [], information
