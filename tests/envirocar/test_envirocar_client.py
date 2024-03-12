import unittest

import geopandas as gpd

from src.envirocar.client.api.track_api import TrackAPI
from src.envirocar.client.client_config import ECConfig
from src.envirocar.client.download_client import DownloadClient
from src.envirocar.client.request_param import BboxSelector


class TestDownloadClient(unittest.TestCase):
    def setUp(self):
        self.config = ECConfig()
        self.client = DownloadClient(config=self.config)
        self.track_api = TrackAPI(self.client)

    def test_download(self):
        tracks = self.track_api.get_tracks(num_results=4, page_limit=3)
        self.assertEqual(len(tracks["track.id"].unique()), 4)

    def test_get_max_page(self):
        path = self.track_api.TRACKS_ENDPOINT
        params = {"limit": 100, "page": 1}
        max_page = self.track_api.get_max_page(path=path, params=params)
        self.assertTrue(max_page > 1)

    def test_bbox_download(self):
        bbox = BboxSelector(
            [
                7.598676681518555,
                51.95045473660811,
                7.624168395996093,
                51.965899201787714,
            ]
        )
        tracks = self.track_api.get_tracks(bbox=bbox, num_results=3)
        self.assertEqual(len(tracks["track.id"].unique()), 3)

    def test_no_result_download(self):
        bbox = BboxSelector(
            [
                51.95045473660811,
                7.598676681518555,
                7.624168395996093,
                51.965899201787714,
            ]
        )
        tracks = self.track_api.get_tracks(bbox=bbox, num_results=3)
        self.assertTrue(isinstance(tracks, gpd.GeoDataFrame))
        self.assertTrue(tracks.empty)


if __name__ == "__main__":
    unittest.main()
