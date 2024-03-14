import json
from typing import Dict, Union, List

import geopandas as gpd
import pandas as pd
from ..download_client import DownloadClient
from ..request_param import BboxSelector, RequestParam, TimeSelector


class TrackAPI:
    """Handles the API access to the enviroCar backend and returns queried results as dataframes"""

    TRACKS_ENDPOINT = "tracks"
    TRACK_ENDPOINT = "tracks/{}"
    USERTRACKS_ENDPOINT = "users/{}/tracks"

    def __init__(self, api_client=None):
        self.api_client = api_client or DownloadClient()

    def get_max_page(
        self,
        path: Union[TRACK_ENDPOINT, TRACKS_ENDPOINT, USERTRACKS_ENDPOINT],
        params: Dict,
    ):
        result = self.api_client.download_links(RequestParam(path=path, params=params))
        if result is not None and "last" in result:
            # 'http://envirocar.org/tracks?limit=100&during=2020-04-01T00%3A00%3A00Z%2C2021-04-15T00%3A00%3A00Z&page=46'
            # Extract and return the page numer
            return int(result["last"]["url"].split("page=")[-1])
        return 1

    def get_tracks(
        self,
        username=None,
        bbox: BboxSelector = None,
        time_interval: TimeSelector = None,
        num_results=10,
        page_limit=100,
        skip_tracks: List[str] = None,
    ) -> pd.DataFrame:
        """Handles queries against the enviroCar api

        Keyword Arguments:
            username {str} -- the username to request tracks for (default: {None})
            bbox {BboxSelector} -- bbox query parameter (default: {None})
            time_interval {TimeSelector} -- time interval query parameter (default: {None})
            num_results {int} -- maximum number of tracks to request (default: {10})
            page_limit {int} -- page limit (default: {100})

        Returns:
            GeoDataFrame -- A GeoDataFrame containing the tracks matching the request parameters
        """
        path = self._get_path(username=username)

        # creating download_requests
        download_requests = []
        current_results = 0
        current_page = 1
        request_params = {"limit": page_limit, "page": current_page}
        if bbox:
            request_params.update(bbox.param)
        if time_interval:
            request_params.update(time_interval.param)
        if num_results is None:
            num_results = (
                self.get_max_page(path=path, params=request_params) * page_limit
            )
        while current_results < num_results:
            request_params.update({"page": current_page})

            request = RequestParam(path=path, params=request_params.copy())
            download_requests.append(request)

            current_results += page_limit
            current_page += 1

        # request for /tracks
        print("Downloading tracks metadata...")
        tracks_meta_df: pd.DataFrame = self.api_client.download(
            download_requests, decoder=_parse_tracks_list_df
        )
        # filter out tracks that are already downloaded
        if skip_tracks:
            tracks_meta_df = tracks_meta_df[
                ~tracks_meta_df["track.id"].isin(skip_tracks)
            ]
        tracks_meta_df = tracks_meta_df[:num_results]

        if not tracks_meta_df.empty:
            print("Downloading tracks...")
            ids = tracks_meta_df["track.id"].values
            return self._get_tracks_by_ids(ids)

        return pd.DataFrame()

    def get_track(self, track_id: str):
        return self.api_client.download(
            RequestParam(path=self._get_path(trackid=track_id)),
            decoder=_parse_track_df,
            post_process=True,
        )

    def _get_tracks_by_ids(self, ids: [str]):
        download_requests = [
            RequestParam(path=self._get_path(trackid=id)) for id in ids
        ]
        return self.api_client.download(download_requests, decoder=_parse_track_df)

    def _get_path(self, *, username=None, trackid=None):
        if username is None and trackid is None:
            return self.TRACKS_ENDPOINT
        if username:
            return self.USERTRACKS_ENDPOINT.format(username)
        if trackid:
            return self.TRACK_ENDPOINT.format(trackid)


def _parse_tracks_list_df(tracks_jsons, post_process: bool = False) -> pd.DataFrame:
    if not isinstance(tracks_jsons, list):
        tracks_jsons = [tracks_jsons]

    tracks_meta_df = pd.DataFrame()
    for tracks_json in tracks_jsons:
        if tracks_json:
            ec_data = json.loads(tracks_json)
            df = pd.json_normalize(ec_data, "tracks")
            df.rename(columns=__rename_track_columns, inplace=True)
            tracks_meta_df = pd.concat([tracks_meta_df, df])

    return tracks_meta_df


def _post_process_df(df: pd.DataFrame) -> pd.DataFrame:
    # Only keep the columns below
    columns_to_keep = [
        "x",
        "y",
        "time",
        "Speed.value",
        "GPS Accuracy.value",
        "GPS Speed.value",
        "track.begin",
        "track.end",
        "track.id",
        "track.length",
    ]
    # remove columns not in the df
    columns_to_keep = [col for col in columns_to_keep if col in df.columns]
    df = df[columns_to_keep]
    if "x" in df.columns:
        df["x"] = pd.to_numeric(df["x"])
    if "y" in df.columns:
        df["y"] = pd.to_numeric(df["y"])
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
    if "Speed.value" in df.columns:
        df["speed_value"] = pd.to_numeric(df["Speed.value"])
    if "GPS Accuracy.value" in df.columns:
        df["gps_accuracy_value"] = pd.to_numeric(df["GPS Accuracy.value"])
    if "GPS Speed.value" in df.columns:
        df["gps_speed_value"] = pd.to_numeric(df["GPS Speed.value"])
    if "track.begin" in df.columns:
        df["track_begin"] = pd.to_datetime(df["track.begin"])
    if "track.end" in df.columns:
        df["track_end"] = pd.to_datetime(df["track.end"])
    if "track.length" in df.columns:
        df["track_length"] = pd.to_numeric(df["track.length"])
    df["track_id"] = df["track.id"].astype(dtype="string")
    new_columns_to_keep = [
        "x",
        "y",
        "time",
        "speed_value",
        "gps_accuracy_value",
        "gps_speed_value",
        "track_begin",
        "track_end",
        "track_length",
        "track_id",
    ]
    # remove columns not in the df
    new_columns_to_keep = [col for col in new_columns_to_keep if col in df.columns]
    # only keep the new columns above
    return df[new_columns_to_keep]


def _parse_track_df(track_jsons, post_process: bool = False) -> pd.DataFrame:
    if not isinstance(track_jsons, list):
        track_jsons = [track_jsons]

    tracks_df = pd.DataFrame()
    for track_json in track_jsons:
        # read properties
        car_df = pd.json_normalize(json.loads(track_json)["properties"])
        car_df.columns = car_df.columns.str.replace("sensor.properties.", "sensor.")
        car_df.rename(columns=__rename_track_columns, inplace=True)

        # read geojson values
        track_df = gpd.read_file(track_json)
        track_df = track_df.join(pd.json_normalize(track_df["phenomenons"])).drop(
            ["phenomenons"], axis=1
        )
        track_df.insert(0, "x", track_df.geometry.x)
        track_df.insert(0, "y", track_df.geometry.y)
        track_df.drop("geometry", inplace=True, axis=1)
        # combine dataframes
        car_df = pd.concat([car_df] * len(track_df.index), ignore_index=True)
        track_df = track_df.join(car_df)
        if post_process:
            track_df = _post_process_df(track_df)
        tracks_df = pd.concat([tracks_df, track_df])
    return tracks_df


def __rename_track_columns(x):
    if not x.startswith("sensor"):
        return "track." + x
    return x
