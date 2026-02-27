from __future__ import annotations

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analysis_service import analyze_documents
from schemas import AnalyzeRequest

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(request: AnalyzeRequest | None = Body(default=None)) -> dict:
    payload = request or AnalyzeRequest()
    report = analyze_documents(payload)
    return {"report": report.model_dump()}
