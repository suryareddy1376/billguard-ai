import requests
import logging

logger = logging.getLogger(__name__)

def extract_text_from_image(image_bytes: bytes) -> dict:
    """
    Takes raw image bytes, runs real Cloud OCR, returns extracted text.
    Returns:
       {"ok": True, "text": "...", "error": None}
    """
    try:
        logger.info("Sending image to Cloud OCR Engine...")
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": ("bill.png", image_bytes, "image/png")},
            data={
                "apikey": "helloworld", 
                "language": "eng", 
                "OCREngine": 1, # Switched to 1: Faster processing under heavy API load
                "scale": "true"
            },
            timeout=60
        )
        
        result = response.json()
        
        if result.get("IsErroredOnProcessing"):
            error_msg = result.get("ErrorMessage", ["Unknown OCR Error"])[0]
            logger.error(f"Cloud OCR failed: {error_msg}")
            return {"ok": False, "text": "", "error": error_msg}
            
        # Parse out all the text lines
        parsed_text = ""
        for item in result.get("ParsedResults", []):
            parsed_text += item.get("ParsedText", "") + "\n"
            
        logger.info("Cloud OCR extraction complete.")
        return {"ok": True, "text": parsed_text.strip(), "error": None}

    except Exception as e:
        logger.error(f"OCR connectivity failed: {e}")
        return {"ok": False, "text": "", "error": f"Cloud OCR extraction failed: {str(e)}"}
