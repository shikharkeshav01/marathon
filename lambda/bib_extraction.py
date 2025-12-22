import os
import cv2
import re
import numpy as np
import easyocr
from ultralytics import YOLO


def preprocess_for_ocr(image_bgr):
    # gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    # # Contrast Limited Adaptive Histogram Equalization
    # clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    # eq = clahe.apply(gray)
    # # Mild denoise without killing edges
    # den = cv2.bilateralFilter(eq, d=7, sigmaColor=50, sigmaSpace=50)
    # # Adaptive threshold to get crisp digits
    # thr = cv2.adaptiveThreshold(den, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 35, 10)
    # # Ensure Tesseract sees dark text on light background; invert if mostly dark
    # if float(np.mean(thr)) < 127.0:
    #     thr = cv2.bitwise_not(thr)
    # return thr

    rep = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    return rep

def detect_and_tabulate_bibs_easyocr(
    image_bytes,
    image_name="input.jpg",
    conf_threshold=0.5,
    ocr_conf_threshold=0.6,
    min_len=2,
    max_len=5
):
    """
    Instead of separating and saving images, maintain a table with bib number and the photos in which they appear.
    Returns a sorted list of detected bib numbers at the end of processing.
    - conf_threshold: YOLO person detection confidence threshold
    - ocr_conf_threshold: EasyOCR confidence threshold in [0, 1]
    - min_len/max_len: min/max length of bib number string to keep
    """

    # Model load - YOLO will use cached model from /tmp/ultralytics if available
    # or download it automatically. The model is preloaded during Docker build.
    model = YOLO("yolov8n.pt")
    person_class_id = 0

    # EasyOCR reader (English, CPU/GPU auto)
    reader = easyocr.Reader(["en"], gpu=True)

    np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes.")

    print(f"[IMG] {image_name}")

    # Detect persons only
    results = model.predict(
        source=img, classes=[person_class_id], conf=conf_threshold, iou=0.5, verbose=False
    )
    bibs = set()

    if len(results) > 0 and results[0].boxes is not None:
        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else boxes.xyxy
        confs = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else boxes.conf
        print(f"[DETECT] persons={len(xyxy)} (conf>={conf_threshold})")

        for (x1, y1, x2, y2), det_conf in zip(xyxy, confs):
            x1, y1, x2, y2 = map(int, [x1, y1, x2, y2])
            x1 = max(0, x1); y1 = max(0, y1); x2 = min(img.shape[1], x2); y2 = min(img.shape[0], y2)
            if x2 <= x1 or y2 <= y1:
                continue

            crop = img[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            print(f"  [BOX] ({x1},{y1},{x2},{y2}) conf={float(det_conf):.2f}")

            # Reuse same preprocessing from the original cell if available
            try:
                prep = preprocess_for_ocr(crop)
            except NameError:
                # Fallback simple grayscale if preprocess_for_ocr is not defined
                prep = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)

            # EasyOCR expects BGR/RGB or grayscale; detail=1 returns (bbox, text, conf)
            ocr_results = reader.readtext(
                prep, detail=1, paragraph=False, slope_ths=0.1, height_ths=0.5
            )
            for bbox, text, conf in ocr_results:
                text_clean = re.sub(r"[^0-9]", "", (text or "").strip())
                if not text_clean:
                    continue
                if not (min_len <= len(text_clean) <= max_len):
                    continue
                if conf < ocr_conf_threshold:
                    continue
                bibs.add(text_clean)
                print(f"    [BIB] {text_clean} (OCR conf={conf:.2f})")

    if not bibs:
        bibs = []
    print(f"[SUMMARY] {image_name}: {sorted(list(bibs))}")

    return sorted(bibs)

# Example usage:
# with open("/Users/phoenixa/Documents/projects/marathon/Edited/example.jpg", "rb") as f:
#     photo_bytes = f.read()
# bib_numbers = detect_and_tabulate_bibs_easyocr(photo_bytes, image_name="example.jpg")
# print(f"Detected bib numbers: {bib_numbers}")

