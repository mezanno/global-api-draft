from typing import TypeAlias
from pydantic import BaseModel, TypeAdapter

class ImageRegion(BaseModel):
    xtl: float|int
    ytl: float|int
    xbr: float|int
    ybr: float|int
# Sample list of ImageRegion objects: 
# [{"xtl": 0.0, "ytl": 0.0, "xbr": 100.0, "ybr": 100.0}, {"xtl": 0.5, "ytl": 0.6, "xbr": 0.7, "ybr": 0.8}]
ImageRegionList: TypeAlias = list[ImageRegion]
ImageRegionListModel = TypeAdapter(ImageRegionList)

# OCRMode is a string that indicates the mode of OCR processing.
#  "block" will detect lines and transcribe them, "line" will directly transcribe lines
# OCRMode = Literal["block", "line"]


class LineTranscription(BaseModel):
    text: str
    confidence: float
    polygon: list[list[float]]
    line_id: int

class OCREngineInfo(BaseModel):
    name: str
    code_version: str
    model_version: str

class OCRResult(BaseModel):
    ocr_engine: OCREngineInfo
    lines: list[LineTranscription]