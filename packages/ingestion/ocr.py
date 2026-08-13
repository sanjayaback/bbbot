from io import BytesIO


def ocr_pixmap(pixmap, tesseract_cmd: str = "") -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("OCR requested but pytesseract/Pillow are not installed") from exc
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd=tesseract_cmd
    image=Image.open(BytesIO(pixmap.tobytes("png")))
    return pytesseract.image_to_string(image, lang="eng+nep").strip()
