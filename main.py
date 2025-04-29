from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import openai
import os
import tempfile
import io
import json
import datetime
from fpdf import FPDF

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI()

ALLOWED_ORIGINS = [
    "https://quickestimate.site",
    "https://www.quickestimate.site",
    "http://localhost:5173"  # dev Vite
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI key
openai.api_key = os.getenv("OPENAI_API_KEY")

# ---------------------------
# Health‑check
# ---------------------------
@app.get("/ping")
async def ping():
    return {"ok": True}

# ---------------------------
# /transcribe-and-parse
# ---------------------------
@app.post("/transcribe-and-parse")
async def transcribe_and_parse(file: UploadFile = File(...)):
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="Only audio files are accepted")

    # save uploaded audio to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # 1. Whisper STT
    with open(tmp_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-large-v3", audio_file)

    text = transcript["text"]

    # 2. Parse with GPT
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

    raw_json = chat_response.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        # fallback: return raw string if parsing failed
        parsed = raw_json

    return {"transcript": text, "parsed": parsed}

# ---------------------------
# /generate-pdf
# ---------------------------
@app.post("/generate-pdf")
async def generate_pdf(data: dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Header
    pdf.cell(200, 10, txt="TradesMate Services", ln=True, align='C')
    pdf.ln(10)

    today = datetime.date.today()
    valid_until = today + datetime.timedelta(days=30)
    estimate_id = f"EST-{int(datetime.datetime.now().timestamp())}"

    pdf.cell(0, 10, f"Estimate #: {estimate_id}", ln=True)
    pdf.cell(0, 10, f"Date: {today.strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 10, f"Valid Until: {valid_until.strftime('%Y-%m-%d')}", ln=True)
    pdf.ln(10)

    # Client info
    pdf.cell(0, 10, f"Client Name: {data.get('Client Name', '')}", ln=True)
    pdf.cell(0, 10, f"Job Type: {data.get('Job Type', '')}", ln=True)
    pdf.ln(5)

    # Job description
    pdf.multi_cell(0, 10, f"Job Description: {data.get('Job Description', '')}")
    pdf.ln(5)

    # Items table
    items = data.get("Items", [])
    pdf.set_font("Arial", size=12, style="")
    pdf.cell(80, 10, "Item", border=1)
    pdf.cell(25, 10, "Qty", border=1, align="C")
    pdf.cell(35, 10, "Unit Price", border=1, align="C")
    pdf.cell(35, 10, "Total", border=1, align="C")
    pdf.ln()

    subtotal = 0
    for item in items:
        desc = str(item.get("Description", ""))[:40]  # truncate long text
        qty = item.get("Quantity", 0)
        price = item.get("Unit Price", 0)
        line_total = qty * price
        subtotal += line_total

        pdf.cell(80, 10, desc, border=1)
        pdf.cell(25, 10, str(qty), border=1, align="C")
        pdf.cell(35, 10, f"${price:.2f}", border=1, align="R")
        pdf.cell(35, 10, f"${line_total:.2f}", border=1, align="R")
        pdf.ln()

    tax = subtotal * 0.10
    total = subtotal + tax

    pdf.ln(5)
    pdf.cell(0, 10, f"Subtotal: ${subtotal:.2f}", ln=True)
    pdf.cell(0, 10, f"Tax (10%): ${tax:.2f}", ln=True)
    pdf.cell(0, 10, f"Total Estimate: ${total:.2f}", ln=True)

    notes = data.get("Notes")
    if notes:
        pdf.ln(10)
        pdf.multi_cell(0, 10, f"Notes: {notes}")

    pdf.ln(10)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 10, "Disclaimer: This estimate is valid for 30 days. Final invoice may vary based on actual work and materials.")

    pdf.ln(20)
    pdf.cell(0, 10, "Client Signature: ______________________", ln=True)
    pdf.cell(0, 10, "Date: ________________________________", ln=True)

    # Return PDF as bytes
    pdf_bytes = pdf.output(dest="S").encode("latin-1")
    return StreamingResponse(io.BytesIO(pdf_bytes),
                             media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=estimate.pdf"})
