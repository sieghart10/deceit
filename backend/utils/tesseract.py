import cv2
import pytesseract as pyt

def image_to_text(img):
    # img = cv2.imread(f"text_img.png")
    pyt.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    text = pyt.image_to_string(img)
    return text