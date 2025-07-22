from celery_app import make_celery
from flask import current_app

celery = make_celery()

@celery.task()
def ocr_task(img_bytes):
  # Implement the OCR logic here
  # This is a placeholder implementation
  #text = run_ocr(img_bytes)
  text = "Sample OCR result"
  return text


