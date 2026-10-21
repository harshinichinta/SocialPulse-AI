"""FastAPI entry point for SocialPulse AI."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

load_dotenv()

from backend.app import database
from backend.app.services.analytics import (
    analyze_frame,
    detect_trends,
    discover_topics,
    evaluate_sentiment,
    forecast_series,
    load_csv_dataset,
    load_json_dataset,
    load_labeled_csv,
    sentiment_prediction,
)
from backend.app.services.demo_data import build_demo_analysis

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("socialpulse")
MAX_UPLOAD_BYTES = int(os.getenv("SOCIALPULSE_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_ROWS = int(os.getenv("SOCIALPULSE_MAX_ROWS", "5000"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    database.initialize()
    yield


app = FastAPI(
    title="SocialPulse AI API",
    description="Explainable, local-first social media text analytics API.",
    version="1.0.0",
    lifespan=lifespan,
)
origins = os.getenv(
    "SOCIALPULSE_ALLOWED_ORIGINS",
    "http://localhost:8501,http://127.0.0.1:8501,http://localhost:5173,http://127.0.0.1:5173",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SentimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class TextBatchRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=5000)
    sentiments: list[str] | None = Field(default=None, max_length=5000)

    @field_validator("texts")
    @classmethod
    def validate_text_sizes(cls, texts: list[str]) -> list[str]:
        if any(len(text) > 10_000 for text in texts):
            raise ValueError("Each text must be 10,000 characters or fewer.")
        if sum(map(len, texts)) > 100_000:
            raise ValueError("Combined text input cannot exceed 100,000 characters.")
        return texts

    @model_validator(mode="after")
    def validate_sentiment_alignment(self) -> "TextBatchRequest":
        if self.sentiments is not None and len(self.sentiments) != len(self.texts):
            raise ValueError("Sentiments must align one-to-one with texts.")
        if self.sentiments is not None and any(
            sentiment not in {"positive", "neutral", "negative"}
            for sentiment in self.sentiments
        ):
            raise ValueError("Sentiments must be positive, neutral, or negative.")
        return self


class TrendRequest(BaseModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=5000)
    window_days: int = Field(default=7, ge=1, le=90)
    min_mentions: int = Field(default=2, ge=1, le=100_000)
    previous_minimum: int = Field(default=3, ge=1, le=100_000)

    @field_validator("records")
    @classmethod
    def validate_record_text_sizes(cls, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        lengths = [len(str(record.get("text") or "")) for record in records]
        if any(length > 10_000 for length in lengths):
            raise ValueError("Each record text must be 10,000 characters or fewer.")
        if sum(lengths) > 100_000:
            raise ValueError("Combined record text cannot exceed 100,000 characters.")
        return records


class ForecastPoint(BaseModel):
    date: str
    count: float = Field(ge=0)


class ForecastRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    points: list[ForecastPoint] = Field(min_length=3, max_length=1000)
    horizon: int = Field(default=7, ge=1, le=30)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local single-machine processing"}


@app.get("/demo/dashboard")
def demo_dashboard() -> dict[str, Any]:
    return build_demo_analysis()


@app.get("/demo/sources")
def demo_sources() -> dict[str, Any]:
    return {
        "mode": "demo",
        "refresh_policy": "manual",
        "scheduler_active": False,
        "sources": [
            {
                "name": "SocialPulse synthetic demo",
                "type": "bundled generated data",
                "status": "available",
                "connection_verified": True,
                "live": False,
                "description": "Synthetic records generated locally for demonstration; not public opinion.",
            },
            {
                "name": "Social-media live APIs",
                "type": "external API",
                "status": "not configured",
                "connection_verified": False,
                "live": False,
                "description": "No live platform connector or credentials are configured.",
            },
            {
                "name": "Hadoop / Hive",
                "type": "distributed processing",
                "status": "external installation required",
                "connection_verified": False,
                "live": False,
                "description": "Cluster is not connected by this local dashboard.",
            },
        ],
    }


@app.post("/predict/sentiment")
def predict_sentiment(request: SentimentRequest) -> dict[str, Any]:
    return sentiment_prediction(request.text)


@app.post("/analyze/dataset")
async def analyze_dataset(
    file: UploadFile = File(...),
    text_column: str | None = Form(default=None),
    timestamp_column: str | None = Form(default=None),
    platform_column: str | None = Form(default=None),
    brand_column: str | None = Form(default=None),
) -> dict[str, Any]:
    return await _analyze_import_file(
        file, text_column, timestamp_column, platform_column, brand_column,
        accepted_extensions={".csv"},
    )


@app.post("/analyze/import")
async def analyze_import(
    file: UploadFile = File(...),
    text_column: str | None = Form(default=None),
    timestamp_column: str | None = Form(default=None),
    platform_column: str | None = Form(default=None),
    brand_column: str | None = Form(default=None),
) -> dict[str, Any]:
    return await _analyze_import_file(
        file, text_column, timestamp_column, platform_column, brand_column,
        accepted_extensions={".csv", ".json"},
    )


async def _analyze_import_file(
    file: UploadFile,
    text_column: str | None,
    timestamp_column: str | None,
    platform_column: str | None,
    brand_column: str | None,
    accepted_extensions: set[str],
) -> dict[str, Any]:
    extension = os.path.splitext(file.filename or "")[1].lower()
    if extension not in accepted_extensions:
        allowed = ", ".join(sorted(accepted_extensions))
        raise HTTPException(status_code=400, detail=f"Upload a file with one of these extensions: {allowed}.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Dataset exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
        )
    try:
        loader = load_json_dataset if extension == ".json" else load_csv_dataset
        frame, stats = loader(
            content,
            text_column=text_column,
            timestamp_column=timestamp_column,
            platform_column=platform_column,
            brand_column=brand_column,
            max_rows=MAX_ROWS,
        )
        result = analyze_frame(frame, stats)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["source"] = {
        "name": file.filename or "Imported dataset",
        "type": "imported",
        "status": "loaded",
        "is_live": False,
    }
    analysis_id = database.save_analysis(result["summary"], result["analysis_mode"])
    result["analysis_id"] = analysis_id
    logger.info("Dataset analyzed: id=%s rows=%s type=%s", analysis_id, stats["rows_analyzed"], extension)
    return result


@app.post("/analyze/topics")
def analyze_topics(request: TextBatchRequest) -> dict[str, Any]:
    return discover_topics(request.texts, sentiments=request.sentiments)


@app.post("/evaluate/sentiment")
async def evaluate_sentiment_endpoint(
    file: UploadFile = File(...),
    text_column: str = Form(..., min_length=1, max_length=100),
    label_column: str = Form(..., min_length=1, max_length=100),
) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a labeled CSV file.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Labeled CSV exceeds the upload limit.")
    try:
        texts, labels = load_labeled_csv(content, text_column, label_column, max_rows=MAX_ROWS)
        return evaluate_sentiment(texts, labels)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/analyze/trends")
def analyze_trends(request: TrendRequest) -> dict[str, Any]:
    return detect_trends(
        request.records, request.window_days, request.min_mentions, request.previous_minimum
    )


@app.post("/forecast")
def forecast(request: ForecastRequest) -> dict[str, Any]:
    try:
        result = forecast_series([point.model_dump() for point in request.points], request.horizon)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["topic"] = request.topic
    return result


@app.get("/analytics/summary")
def analytics_summary() -> dict[str, Any]:
    return {**database.summary(), "analysis_mode": "local single-machine processing"}


@app.get("/analytics/history")
def analytics_history(limit: int = 50) -> dict[str, Any]:
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200.")
    return {"items": database.history(limit=limit)}
