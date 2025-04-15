import configparser
from functools import lru_cache
import os

import numpy as np
# import cv2

from pero_ocr.document_ocr.layout import PageLayout
from pero_ocr.document_ocr.page_parser import PageParser
# from pero_ocr.ocr_engine.pytorch_ocr_engine import PytorchEngineLineOCR


@lru_cache(maxsize=1)
def _load_pero_page_parser(config_path):
    config = configparser.ConfigParser()
    config_file = os.path.join(config_path, "config.ini")
    if not os.path.exists(config_file):
        raise ValueError(f"cannot read configuration file {config_file}")
    config.read(config_file)
    return PageParser(config, config_path)


class PERO_driver():
    def __init__(self, config_path: str) -> None:
        """
        Wrapper to PERO OCR.

        Args:
            config_path (str): Path to configuration dir.
                It must contain the following files:
                - ParseNet.pb
                - checkpoint_350000.pth
                - config.ini
                - ocr_engine.json
        """
        self.config_path = config_path
        self.page_parser = _load_pero_page_parser(config_path)

        # Reuse already initialized OCR engine
        self.ocr_engine = self.page_parser.ocr.ocr_engine


    @staticmethod
    def get_software_description():
        # ideally we would have some UID here which points to a single db with all parameters and weights to reproduce.
        return "Pero OCR v2021-11-23 github master branch, models: pero_eu_cz_print_newspapers_2020-10-07"


    def detect_and_recognize(self, image) -> list:
        """Process rectangular regions by detecting text regions and lines, then OCRing them.

        Args:
            image (np.ndarray): Full image to crop regions from
            bbox_list (list of tuples of int): bounding boxes of the regions

        Returns:
            list of Pero lines: List of complex line objects are produced by Pero
        """
        # This should run in a different thread / process / worker machine to avoid freezing the server
        if image.ndim == 2:
            # convert grayscale to color if needed
            image = np.tile(image[..., np.newaxis], (1, 1, 3))

        page_layout = PageLayout(id="00", page_size=(image.shape[0], image.shape[1]))

        # The real thing
        page_layout2 = self.page_parser.process_page(image, page_layout)

        line_lists = list(page_layout2.lines_iterator())
        return line_lists
