import easyocr
import os
import json
from rapidfuzz import process, fuzz

# Cache for easyocr reader
_reader = None

def get_reader():
    global _reader
    if _reader is None:
        # Initializing reader for English (you can add more languages if needed)
        # Using cpu=True to ensure it works on systems without GPU
        _reader = easyocr.Reader(['en'], gpu=False)
    return _reader

def extract_text_from_image(image_path):
    """Extract all text from the given image path."""
    try:
        reader = get_reader()
        results = reader.readtext(image_path)
        # Combine all detected text snippets into one string
        full_text = " ".join([text for (bbox, text, prob) in results])
        return full_text
    except Exception as e:
        print(f"OCR Error: {e}")
        return ""

def match_medicine_name(extracted_text, medicine_list):
    """
    Match the extracted text against a list of known medicines.
    Returns the best match and the confidence score.
    """
    if not extracted_text or not medicine_list:
        return None, 0
    
    # We look for the best match within the extracted text
    # This helps if the box has other text like 'Tablets', '500mg'
    best_match = None
    best_score = 0
    
    # Clean extracted text for better matching
    clean_text = extracted_text.upper().replace("_", " ")
    
    for med in medicine_list:
        med_upper = med.upper().replace("_", " ")
        # Token-set ratio is good for finding a string within another string
        score = fuzz.partial_ratio(med_upper, clean_text)
        
        if score > best_score:
            best_score = score
            best_match = med
            
    return best_match, float(best_score)

def get_ocr_prediction(image_path, labels_file):
    """
    Highest level utility to get the best medicine match from an image.
    """
    if not os.path.exists(labels_file):
        return None, 0
        
    with open(labels_file, 'r') as f:
        labels_map = json.load(f)
    
    # Filter out Fake and Unknown
    medicine_list = [v for k, v in labels_map.items() if v not in ['Fake', 'Unknown']]
    
    text = extract_text_from_image(image_path)
    if not text:
        return None, 0
        
    match, score = match_medicine_name(text, medicine_list)
    return match, score
