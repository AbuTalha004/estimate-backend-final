from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import openai
import os
import tempfile
import io
from fpdf import FPDF
import datetime

# Initialize FastAPI app
app = FastAPI()

# Allow CORS for all origins (frontend communication)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

# -------------------------------
# Endpoint 1: /transcribe-and-parse
# Transcribes voice + parses estimate fields
# -------------------------------
@app.post("/transcribe-and-parse")
async def transcribe_and_parse(file: UploadFile = File(...)):
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # 1. Send to Whisper (OpenAI Speech-to-Text)
    audio_file = open(tmp_path, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    text = transcript["text"]

    # 2. Parse transcript using ChatGPT
    prompt = """
    You are an expert Estimate Form Assistant for skilled laborers in the U.S.
    Extract the following fields:
    - Client Name
    - Job Type
    - Job Description
    - List of Items (Description, Quantity, Unit Price)
    - Notes (optional)

    If speaker uses correction keywords ("correction", "wait", "change", etc.), apply corrections.

    Output final corrected form in this JSON format:

    {
      "Client Name": "",
      "Job Type": "",
      "Job Description": "",
      "Items": [
        {"Description": "", "Quantity": 0, "Unit Price": 0}
      ],
      "Notes": ""
    }

    Provide only the JSON. Nothing else.
    """

    chat_response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Input text:\n{text}"}
        ],
        temperature=0
    )

    result_json = chat_response["choices"][0]["message"]["content"]

    return {"transcript": text, "parsed_data": result_json}

# -------------------------------
# Endpoint 2: /generate-pdf
# Accepts parsed data and returns generated PDF
# -------------------------------
@app.post("/generate-pdf")
async def generate_pdf(data: dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Company Info
    pdf.cell(200, 10, txt="TradesMate Services", ln=True, align='C')
    pdf.ln(10)

    # Estimate Info
    today = datetime.date.today()
    valid_until = today + datetime.timedelta(days=30)
    estimate_id = f"EST-{int(datetime.datetime.now().timestamp())}"

    pdf.cell(0, 10, f"Estimate #: {estimate_id}", ln=True)
    pdf.cell(0, 10, f"Date: {today.strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, f"Valid Until: {valid_until.strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(10)

    # Client Info
    pdf.cell(0, 10, f"Client Name: {data.get('Client Name', '')}", ln=True)
    pdf.cell(0, 10, f"Job Type: {data.get('Job Type', '')}", ln=True)
    pdf.ln(5)

    # Job Description
    pdf.multi_cell(0, 10, f"Job Description: {data.get('Job Description', '')}")
    pdf.ln(5)

    # Items Table
    items = data.get("Items", [])
    pdf.cell(60, 10, "Item", border=1)
    pdf.cell(30, 10, "Qty", border=1)
    pdf.cell(40, 10, "Unit Price", border=1)
    pdf.cell(40, 10, "Total", border=1)
    pdf.ln()

    subtotal = 0
    for item in items:
        desc = item.get("Description", "")
        qty = item.get("Quantity", 0)
        price = item.get("Unit Price", 0)
        line_total = qty * price
        subtotal += line_total

        pdf.cell(60, 10, str(desc), border=1)
        pdf.cell(30, 10, str(qty), border=1)
        pdf.cell(40, 10, f"${price:.2f}", border=1)
        pdf.cell(40, 10, f"${line_total:.2f}", border=1)
        pdf.ln()

    # Subtotal and Total
    tax = subtotal * 0.10  # 10% tax
    total = subtotal + tax

    pdf.ln(5)
    pdf.cell(0, 10, f"Subtotal: ${subtotal:.2f}", ln=True)
    pdf.cell(0, 10, f"Tax (10%): ${tax:.2f}", ln=True)
    pdf.cell(0, 10, f"Total Estimate: ${total:.2f}", ln=True)

    # Notes
    notes = data.get("Notes", "")
    if notes:
        pdf.ln(10)
        pdf.multi_cell(0, 10, f"Notes: {notes}")

    # Disclaimer
    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 10, "Disclaimer: This estimate is valid for 30 days. Final invoice may vary based on actual work and materials.")

    # Signature
    pdf.ln(20)
    pdf.cell(0, 10, "Client Signature: ______________________", ln=True)
    pdf.cell(0, 10, "Date: ________________________________", ln=True)

    # Output PDF
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)

    return StreamingResponse(pdf_output, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=estimate.pdf"})
