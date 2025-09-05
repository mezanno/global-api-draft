from typing import List
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from PIL import Image
import requests
from io import BytesIO

from surya.common.polygon import PolygonBox
from surya.foundation import FoundationPredictor
from surya.layout import LayoutPredictor, LayoutResult, LayoutBox
from surya.recognition import RecognitionPredictor, OCRResult, TextLine
from surya.detection import DetectionPredictor
from fastapi.middleware.cors import CORSMiddleware
from surya.table_rec import TableRecPredictor, TableResult, TableCell, TableCol, TableRow
from sympy.strategies.core import switch

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise tous les domaines (en dev)
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes (GET, POST, etc.)
    allow_headers=["*"],  # Autorise tous les headers
)

# Initialise une fois les predictiors
foundation_predictor = FoundationPredictor()
recognition_predictor = RecognitionPredictor(foundation_predictor)
detection_predictor = DetectionPredictor()
layout_predictor = LayoutPredictor()
table_rec_predictor = TableRecPredictor()

class Region(BaseModel):
    xtl: float
    ytl: float
    xbr: float
    ybr: float

class ImageUrlRequest(BaseModel):
    url: str
    regions: List[Region]

def shift_layout_result(pred: LayoutResult, dx: float, dy: float) -> LayoutResult:
    new_pred = pred.model_copy()

    # on clone chaque box et on la décale
    new_boxes: list[LayoutBox] = []
    for box in pred.bboxes:
        b = box.model_copy()     # clone de LayoutBox
        b.shift(dx, dy)          # ta méthode PolygonBox
        new_boxes.append(b)

    new_pred.bboxes = new_boxes
    return new_pred

def shift_ocr_result(pred:OCRResult, dx: float, dy: float) -> OCRResult:
    new_pred = pred.model_copy()
    for line in new_pred.text_lines:
        line.shift(dx, dy)
        for char in line.chars:
            char.shift(dx, dy)

    new_pred.image_bbox = [
        new_pred.image_bbox[0] + dx,
        new_pred.image_bbox[1] + dy,
        new_pred.image_bbox[2] + dx,
        new_pred.image_bbox[3] + dy,
    ]
    return new_pred

def shift_table_result(pred: TableResult, dx: float, dy: float) -> TableResult:
    new_pred = pred.model_copy()

    for cell in new_pred.cells:
        cell.shift(dx, dy)

    for ucell in new_pred.unmerged_cells:
        ucell.shift(dx, dy)

    for col in new_pred.cols:
        col.shift(dx, dy)

    for row in new_pred.rows:
        row.shift(dx, dy)

    new_pred.image_bbox = [
        new_pred.image_bbox[0] + dx,
        new_pred.image_bbox[1] + dy,
        new_pred.image_bbox[2] + dx,
        new_pred.image_bbox[3] + dy,
    ]
    return new_pred

def merge_layout_results(results: list[LayoutResult]) -> LayoutResult:
    all_boxes: list[LayoutBox] = []
    # image_bbox = enveloppe de tous les image_bbox (après décalage)
    minx = float("inf"); miny = float("inf"); maxx = float("-inf"); maxy = float("-inf")
    sliced_any = False

    for r in results:
        all_boxes.extend(r.bboxes)
        if r.image_bbox and len(r.image_bbox) == 4:
            x1, y1, x2, y2 = r.image_bbox
            minx = min(minx, x1); miny = min(miny, y1)
            maxx = max(maxx, x2); maxy = max(maxy, y2)
        sliced_any = sliced_any or r.sliced

    merged_bbox = [minx, miny, maxx, maxy] if minx != float("inf") else [0, 0, 0, 0]
    return LayoutResult(bboxes=all_boxes, image_bbox=merged_bbox, sliced=sliced_any)

def merge_ocr_results(results: list[OCRResult]) -> OCRResult:
    all_lines: list[TextLine] = []
    minx = float("inf"); miny = float("inf"); maxx = float("-inf"); maxy = float("-inf")

    for r in results:
        all_lines.extend(r.text_lines)
        if r.image_bbox and len(r.image_bbox) == 4:
            x1, y1, x2, y2 = r.image_bbox
            minx = min(minx, x1); miny = min(miny, y1)
            maxx = max(maxx, x2); maxy = max(maxy, y2)

    merged_bbox = [minx, miny, maxx, maxy] if minx != float("inf") else [0, 0, 0, 0]
    return OCRResult(text_lines=all_lines, image_bbox=merged_bbox)

def merge_table_results(results: list[TableResult]) -> TableResult:
    all_cells: list[TableCell] = []
    all_ucells: list[TableCell] = []
    all_cols: list[TableCol] = []
    all_rows: list[TableRow] = []
    minx = float("inf"); miny = float("inf"); maxx = float("-inf"); maxy = float("-inf")

    for r in results:
        all_cells.extend(r.cells)
        all_cols.extend(r.cols)
        all_rows.extend(r.rows)
        all_ucells.extend(r.unmerged_cells)
        if r.image_bbox and len(r.image_bbox) == 4:
            x1, y1, x2, y2 = r.image_bbox
            minx = min(minx, x1); miny = min(miny, y1)
            maxx = max(maxx, x2); maxy = max(maxy, y2)

    merged_bbox = [minx, miny, maxx, maxy] if minx != float("inf") else [0, 0, 0, 0]
    return TableResult(cells=all_cells,rows=all_rows,cols=all_cols, unmerged_cells=all_ucells, image_bbox=merged_bbox)

@app.post("/ocr")
async def predict_image(request: ImageUrlRequest):
    return process(request, 'ocr')

@app.post("/layout")
async def predict_layout(request: ImageUrlRequest):
    return process(request, 'layout')

@app.post("/table")
async def predict_table(request: ImageUrlRequest):
    return process(request, 'table')

def process(request: ImageUrlRequest, type):
    try:
        # Téléchargement de l'image depuis l'URL
        response = requests.get(request.url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Impossible de charger l'image: {str(e)}")

    regions: List[Region]
    if not request.regions:
        width, height = image.size
        regions = [Region(xtl=0, ytl=0, xbr=width, ybr=height)]
    else:
        regions = request.regions

    print('regions ', regions)
    match type:
        case 'layout':
            all_predictions: list[LayoutResult] = []
            for region in regions:
                cropped = image.crop((region.xtl, region.ytl, region.xbr, region.ybr))
                predictions = layout_predictor([cropped])
                adjusted_preds = [
                    shift_layout_result(pred, region.xtl, region.ytl) for pred in predictions
                ]
                all_predictions.extend(adjusted_preds)
            merged = merge_layout_results(all_predictions)
            return {"predictions": [merged]}
        case 'table':
            all_predictions: list[TableResult] = []
            for region in regions:
                cropped = image.crop((region.xtl, region.ytl, region.xbr, region.ybr))
                predictions = table_rec_predictor([cropped])
                adjusted_preds = [
                    shift_table_result(pred, region.xtl, region.ytl) for pred in predictions
                ]
                all_predictions.extend(adjusted_preds)
            merged = merge_table_results(all_predictions)
            return {"predictions": [merged]}
        case _:
            all_predictions: list[OCRResult] = []
            for region in regions:
                cropped = image.crop((region.xtl, region.ytl, region.xbr, region.ybr))
                predictions = recognition_predictor([cropped], det_predictor=detection_predictor)
                adjusted_preds = [
                    shift_ocr_result(pred, region.xtl, region.ytl) for pred in predictions
                ]
                all_predictions.extend(adjusted_preds)
            merged = merge_ocr_results(all_predictions)
            return {"predictions": [merged]}



# Pour lancer le serveur (localhost:8000) :
# ~/venv/surya/bin/uvicorn surya_server:app --reload
# !! Nécessite la création d'un venv python où l'on installera : python3 -m pip install surya-ocr fastapi uvicorn pillow requests
# Ainsi que : sudo apt install uvicorn

