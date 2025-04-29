# QuickEstimate Backend

This is the backend for QuickEstimate — an AI-powered estimate generator for skilled laborers.

## Features

- Voice to Text (using OpenAI Whisper API)
- Intelligent Parsing & Corrections (using ChatGPT API)
- Dynamic PDF Estimate Generation (using FPDF2)

## Endpoints

- `POST /transcribe-and-parse` - Upload audio file to get structured estimate data.
- `POST /generate-pdf` - Send structured data to generate downloadable PDF estimate.

## Deployment

- Hosted on Render.com
- Requires `OPENAI_API_KEY` as environment variable
