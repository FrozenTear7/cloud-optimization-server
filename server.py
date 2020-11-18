from PIL import Image
import pytesseract
import sys
from pdf2image import convert_from_path
import os
from flask import Flask, request
from multiprocessing.pool import ThreadPool
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

host_address = "0.0.0.0"

if os.environ["DEV"] == "1":
    pytesseract.pytesseract.tesseract_cmd = (
        "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    )
    tessdata_dir_config = r'--tessdata-dir "C:\\Program Files\\Tesseract-OCR\\tessdata"'
    host_address = "127.0.0.1"
else:
    pytesseract.pytesseract.tesseract_cmd = "/app/.apt/usr/bin/tesseract"
    tessdata_dir_config = r'--tessdata-dir "/app/.apt/usr/bin/tesseract/tessdata"'

app = Flask(__name__)

uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)


@app.route("/ocr", methods=["POST"])
def ocrProcess():
    pdf_document = request.files["document"]
    pdf_document_path = os.path.join(uploads_dir, pdf_document.filename)
    pdf_document.save(pdf_document_path)
    pages = convert_from_path(pdf_document_path, 300)

    pool = ThreadPool(5)
    results = []

    for i, page in enumerate(pages):
        filename = f"{pdf_document_path}_page_{i}.jpg"
        page.save(filename, "JPEG")
        results.append(pool.apply_async(get_text_from_image, args=(filename,)))
        print(
            f"Started job {i}",
        )

    pool.close()
    pool.join()

    ocr_result = ""

    for result in results:
        ocr_result += result.get()

    os.remove(pdf_document_path)

    return ocr_result


def get_text_from_image(filename):
    result = str(
        (
            (
                pytesseract.image_to_string(
                    Image.open(filename), config=tessdata_dir_config
                )
            )
        )
    )
    os.remove(filename)
    return result


if __name__ == "__main__":
    port = os.environ["PORT"]
    app.run(host=host_address, port=port)
    print(f"Server started at port: {port}")
