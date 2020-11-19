from PIL import Image
import pytesseract
import sys
from pdf2image import convert_from_path
import os
from flask import Flask, request
from dotenv import load_dotenv
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import enum
import uuid

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
    tessdata_dir_config = (
        r'--tessdata-dir "./.apt/usr/share/tesseract-ocr/4.00/tessdata"'
    )

app = Flask(__name__)

uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(uploads_dir, exist_ok=True)

global job_counter
job_counter = 0
job_results = {}


class JobStatus(enum.Enum):
    InProgress = 0
    Done = 1


class JobResult:
    def __init__(self):
        self.status = JobStatus.InProgress

    def set_result(self, result):
        self.result = result
        self.status = JobStatus.Done


@app.route("/ocr", methods=["POST"])
def ocrProcess():
    pdf_document = request.files["document"]
    pdf_document_path = os.path.join(uploads_dir, f"{uuid.uuid4()}.pdf")
    pdf_document.save(pdf_document_path)

    global job_counter
    job_id = job_counter
    job_results[job_id] = JobResult()
    job_counter += 1
    th = threading.Thread(
        target=process_pdf,
        args=(
            job_id,
            pdf_document_path,
        ),
    )
    th.start()
    print(
        f"Started job {job_id}",
    )

    return {"job_id": job_id}


def process_pdf(job_id, pdf_document_path):
    pages = convert_from_path(
        pdf_document_path,
        thread_count=int(os.environ["THREADS"]),
        use_pdftocairo=True,
    )

    ocr_result = ""

    with ThreadPoolExecutor(max_workers=int(os.environ["THREADS"])) as executor:
        results = executor.map(
            lambda args: get_text_from_image(*args),
            (
                (i, job_id, len(pages), pdf_document_path, page)
                for i, page in enumerate(pages)
            ),
        )

        for result in results:
            ocr_result += result

    os.remove(pdf_document_path)
    job_results[job_id].result = ocr_result
    job_results[job_id].status = JobStatus.Done
    print(f"Job {job_id} done")


def get_text_from_image(i, job_id, total_pages, pdf_document_path, page):
    print(
        f"Started processing image {i + 1} / {total_pages} of job {job_id}",
    )
    filename = f"{pdf_document_path[:-4]}-{i + 1}.jpg"
    page.save(filename, "JPEG")
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


@app.route("/ocr/<job_id>", methods=["GET"])
def getOcrResult(job_id):
    try:
        job_result = job_results[int(job_id)]
    except KeyError:
        return {"error": "No job with that id"}

    if job_result.status == JobStatus.InProgress:
        return {"status": "IN_PROGRESS"}
    else:
        result = job_result.result
        # job_results.pop(int(job_id))
        return {"result": result, "status": "DONE"}


if __name__ == "__main__":
    port = os.environ["PORT"]
    app.run(host=host_address, port=port)
    print(f"Server started at port: {port}")
