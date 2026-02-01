"""OCR for images and handwritten notes."""

import io
from typing import Optional

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None


def extract_text_from_image(data: bytes) -> tuple[str, Optional[float]]:
    """
    Extract text from image bytes using Tesseract OCR.
    Returns (text, confidence). Confidence is average from Tesseract if available.
    """
    if Image is None or pytesseract is None:
        return "", None
    image = Image.open(io.BytesIO(data)).convert("RGB")
    try:
        data_dict = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        texts = []
        confidences = []
        for i, conf in enumerate(data_dict["conf"]):
            if int(conf) > -1:
                texts.append(data_dict["text"][i])
                confidences.append(float(conf))
        text = " ".join(texts).strip()
        confidence = sum(confidences) / len(confidences) / 100.0 if confidences else None
        return text, confidence
    except Exception:
        return pytesseract.image_to_string(image).strip(), None
