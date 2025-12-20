"""
Preload models during Docker build to avoid cold start delays.
This script downloads and caches:
1. YOLO model (yolov8n.pt) - cached in /tmp/ultralytics
2. EasyOCR model (English) - cached in /tmp/.cache
"""
import os
from ultralytics import YOLO
import easyocr

print("[PRELOAD] Starting model preload...")

# Preload YOLO model
print("[PRELOAD] Loading YOLO model (yolov8n.pt)...")
try:
    model = YOLO("yolov8n.pt")
    print("[PRELOAD] YOLO model loaded successfully")
except Exception as e:
    print(f"[PRELOAD] Error loading YOLO model: {e}")
    raise

# Preload EasyOCR reader (English)
print("[PRELOAD] Loading EasyOCR reader (English)...")
try:
    reader = easyocr.Reader(["en"], gpu=False)  # Use CPU during build
    print("[PRELOAD] EasyOCR reader loaded successfully")
except Exception as e:
    print(f"[PRELOAD] Error loading EasyOCR reader: {e}")
    raise

print("[PRELOAD] All models preloaded successfully!")

