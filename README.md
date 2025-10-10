## PipelineIdentidad-IA

API que procesa imágenes de documentos (DNI, licencia, pasaporte):
- OCR con Google Cloud Vision → texto
- LLM (OpenAI) → datos estructurados

### Endpoints
- POST /upload → job_id
- GET /status/{job_id} → estado
- GET /result/{job_id} → resultado
- GET /health → healthcheck

### Variables de entorno
- OPENAI_API_KEY (obligatoria)
- Local: GOOGLE_APPLICATION_CREDENTIALS = ruta a google-vision-credentials.json
- Railway: GOOGLE_CREDENTIALS_B64 = credenciales en base64

### Uso local (PowerShell)
```powershell
$env:OPENAI_API_KEY = "tu_api_key_openai"
Copy-Item google-vision-credentials-example.json google-vision-credentials.json
$env:GOOGLE_APPLICATION_CREDENTIALS = (Resolve-Path "google-vision-credentials.json").Path
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend simple en `frontend/` para probar.

### Notas
- `google-vision-credentials.json` está ignorado (no se sube)
- Usa `google-vision-credentials-example.json` como plantilla

### Nodos del pipeline (breve)
- image_processing: valida la imagen (formato/tamaño), extrae texto con Google Vision y lo guarda en `processing_data.raw_text`.
- llm: genera prompts y extrae campos con OpenAI; escribe en `extracted_data`.

### Datos extraídos (ejemplo)
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

### Respuesta de /result (forma mínima)
```json
{
	"extracted_data": { "...campos arriba...", "texto_extraido": "..." },
	"processing_metrics": { "ocr_confidence": 0, "processing_time": 1.3, "text_length": 586, "ocr_method": "Google Vision API" },
	"raw_result": { "...estado completo..." }
}
```