# SmartID-AI

API that processes document images (ID card, driver's license, passport):
- OCR with Google Cloud Vision → text
- LLM (OpenAI) → structured data

## Endpoints

- **POST /upload** → job_id
- **GET /status/{job_id}** → status
- **GET /result/{job_id}** → result
- **GET /health** → healthcheck

## Environment Variables

- **OPENAI_API_KEY** (required)
- **Local**: GOOGLE_APPLICATION_CREDENTIALS = path to google-vision-credentials.json
- **Railway**: GOOGLE_CREDENTIALS_B64 = credentials in base64

## Local Usage (PowerShell)

```powershell
$env:OPENAI_API_KEY = "your_openai_api_key"
Copy-Item google-vision-credentials-example.json google-vision-credentials.json
$env:GOOGLE_APPLICATION_CREDENTIALS = (Resolve-Path "google-vision-credentials.json").Path
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Simple frontend in `frontend/` for testing.

## Notes

- `google-vision-credentials.json` is ignored (not uploaded)
- Use `google-vision-credentials-example.json` as template

## Pipeline Nodes (brief)

- **image_processing**: validates image (format/size), extracts text with Google Vision and saves it in `processing_data.raw_text`.
- **llm**: generates prompts and extracts fields with OpenAI; writes to `extracted_data`.

## Extracted Data (example)

```json
{
	"apellido_paterno": "PEREZ",
	"apellido_materno": "GARCIA",
	"nombres": "JUAN CARLOS",
	"fecha_emision": "12/05/2023",
	"fecha_caducidad": "12/05/2028",
	"tipo_documento": "DNI",
	"numero_documento": "12345678"
}
```

## /result Response (minimal form)

```json
{
	"extracted_data": { "...fields above...", "texto_extraido": "..." },
	"processing_metrics": { "ocr_confidence": 0, "processing_time": 1.3, "text_length": 586, "ocr_method": "Google Vision API" },
	"raw_result": { "...complete state..." }
}
```

## Tech Stack

- **Backend**: FastAPI, Uvicorn
- **OCR**: Google Cloud Vision API
- **LLM**: OpenAI (GPT models)
- **Orchestration**: LangGraph pipeline
- **Image Processing**: Pillow (PIL)
- **Validation**: Pydantic

## Quick Start

1. **Clone repository**
```bash
git clone <repository_url>
cd PipelineIdentidad-IA
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure credentials**
- Set `OPENAI_API_KEY` environment variable
- Copy and configure `google-vision-credentials.json`

4. **Run server**
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

5. **Test with frontend**
- Open `frontend/index.html` in browser
- Upload an ID document image

## API Examples

### Upload Document
```bash
curl -X POST "http://localhost:8000/upload" \
  -F "file=@dni.jpg"
```

Response:
```json
{
  "job_id": "abc123",
  "status": "PENDING",
  "message": "Document uploaded successfully"
}
```

### Check Status
```bash
curl "http://localhost:8000/status/abc123"
```

### Get Results
```bash
curl "http://localhost:8000/result/abc123"
```

## Supported Document Types

- **DNI** (Peruvian National ID)
- **Driver's License**
- **Passport**

## Features

- ✅ Async processing with job queue
- ✅ Image validation (format, size)
- ✅ High-accuracy OCR with Google Vision
- ✅ Intelligent field extraction with LLM
- ✅ Processing metrics and confidence scores
- ✅ Simple web interface for testing
- ✅ Docker support for deployment

## Limitations

- Supported image formats: JPEG, PNG
- Maximum image size: configurable (default 10 MB)
- Requires valid Google Cloud Vision credentials
- Requires OpenAI API credits

## Deployment

### Docker
```bash
docker build -t identity-pipeline:latest .
docker run -e OPENAI_API_KEY=sk-xxx \
  -e GOOGLE_CREDENTIALS_B64=base64_encoded_json \
  -p 8000:8000 identity-pipeline:latest
```

### Railway
- Set `OPENAI_API_KEY` environment variable
- Set `GOOGLE_CREDENTIALS_B64` with base64-encoded Google credentials
- Deploy from repository

## Security Notes

- Never commit `google-vision-credentials.json`
- Keep API keys secure in environment variables
- Use HTTPS in production
- Implement rate limiting for public deployments

## Author

**Leon Achata**
- GitHub: [@LeonAchata](https://github.com/LeonAchata)

---

**AI-Powered Identity Document Processing Pipeline**
