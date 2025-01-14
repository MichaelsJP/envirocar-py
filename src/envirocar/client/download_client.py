import concurrent.futures
import logging
import warnings
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from typing import Dict
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth

from ..exceptions import HttpFailedException
from .client_config import ECConfig
from .request_param import RequestParam
from .utils import handle_error_status

LOG = logging.getLogger(__name__)


class DownloadClient:
    def __init__(self, *, config=None):
        self.config = config or ECConfig()

    def download(
        self, download_requests, decoder=None, post_process: bool = False
    ) -> pd.DataFrame:
        if isinstance(download_requests, RequestParam):
            download_requests = [download_requests]
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.number_of_processes
            ) as executor:
                download_list = list(
                    tqdm(
                        executor.map(self._download, download_requests),
                        total=len(download_requests),
                    )
                )
        except Exception as e:
            print("Error in download: ", e)
            download_list = []
        result_list = []
        for result in download_list:
            try:
                decoded_data = result.decode("utf-8")
                result_list.append(decoded_data)
            except HttpFailedException as e:
                warnings.warn(str(e))
                result_list.append(None)

        if decoder:
            return decoder(result_list, post_process=post_process)
        return pd.DataFrame(result_list)

    @handle_error_status
    def download_links(self, download_request: RequestParam) -> Dict:
        url = urljoin(self.config.ec_base_url, download_request.path)

        # set BasicAuth parameters
        auth = None
        if self.config.ec_username and self.config.ec_password:
            auth = HTTPBasicAuth(self.config.ec_username, self.config.ec_password)

        response = requests.request(
            download_request.method,
            url=url,
            auth=auth,
            headers=download_request.headers,
            params=download_request.params,
        )

        response.raise_for_status()
        LOG.info("Successfully downloaded %s", url)
        return response.links

    @handle_error_status
    def _download(self, download_request: RequestParam):
        url = urljoin(self.config.ec_base_url, download_request.path)

        # set BasicAuth parameters
        auth = None
        if self.config.ec_username and self.config.ec_password:
            auth = HTTPBasicAuth(self.config.ec_username, self.config.ec_password)

        response = requests.request(
            download_request.method,
            url=url,
            auth=auth,
            headers=download_request.headers,
            params=download_request.params,
        )

        response.raise_for_status()
        LOG.info("Successfully downloaded %s", url)
        return response.content

    @handle_error_status
    def _download_and_save(
        self, download_request: RequestParam, output_folder: Path
    ) -> Path:
        content = self._download(download_request)
        file_path = output_folder / download_request.path
        with open(file_path, "wb") as file:
            file.write(content)
        return file_path
