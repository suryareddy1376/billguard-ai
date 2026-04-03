"""
Async Queue Worker — orchestrates the full 6-layer pipeline.
Simulates Kafka consumer: picks up QUEUED jobs, runs all layers in sequence.
Runs as a background task inside the FastAPI process (hackathon mode).
In production: replace with a standalone Kafka consumer service.
"""
import asyncio
import uuid
import json

from database import AsyncSessionLocal
from models import LineItem, FraudAnalysis
from layers.ingestion import update_job_status
from layers.normalization import normalize_bill
from layers.feature_engine import compute_features
from layers.rules_engine import run_rules_engine
from layers.anomaly_detector import run_anomaly_detection
from layers.score_aggregator import aggregate_score
from layers.explanation import generate_item_explanations, generate_summary_explanation

# In-process job queue (replace with Kafka in production)
job_queue: asyncio.Queue = asyncio.Queue()


async def enqueue(job_id: str, raw_payload: str):
    """Push a job onto the in-process queue."""
    await job_queue.put((job_id, raw_payload))


async def worker_loop():
    """
    Continuously processes jobs from the queue.
    One worker loop per process; scale horizontally in production.
    """
    print("[Worker] Started. Waiting for jobs...")
    while True:
        try:
            job_id, raw_payload = await job_queue.get()
            print(f"[Worker] Processing job: {job_id}")
            try:
                await process_job(job_id, raw_payload)
            except Exception as e:
                print(f"[Worker] ERROR on job {job_id}: {e}")
                async with AsyncSessionLocal() as db:
                    await update_job_status(db, job_id, "FAILED", detail=str(e))
            finally:
                job_queue.task_done()
        except Exception as e:
            print(f"[Worker] Queue error: {e}")
            await asyncio.sleep(1)


async def process_job(job_id: str, raw_payload: str):
    """
    Runs the full detection pipeline for a single bill job.
    Layer 2 → Layer 3A → 3B → 3C → 3D → 3E → persist results.
    """
    async with AsyncSessionLocal() as db:
        # Mark as processing
        await update_job_status(db, job_id, "PROCESSING")

        # ── Layer 2: Normalize ──────────────────────────────────────────────
        normalized = normalize_bill(raw_payload)
        if not normalized["ok"]:
            await update_job_status(db, job_id, "FAILED", detail=normalized.get("error"))
            return

        line_items = normalized["line_items"]

        # Persist canonical line items
        for item in line_items:
            db.add(LineItem(
                id=item["item_id"],
                job_id=job_id,
                raw_description=item["raw_description"],
                mapped_category=item["mapped_category"],
                procedure_code=item["procedure_code"],
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                total_price=item["total_price"],
                date_of_service=item["date_of_service"],
                data_quality_flags=item["data_quality_flags"],
            ))
        await db.commit()

        # ── Layer 3A: Feature Extraction ────────────────────────────────────
        items_with_features = []
        for item in line_items:
            features = compute_features(item, line_items)
            items_with_features.append({"item": item, "features": features})

        # ── Layer 3B: Rules Engine ───────────────────────────────────────────
        rule_violations = run_rules_engine(normalized)

        # ── Layer 3C: Statistical Anomaly Detection ──────────────────────────
        anomaly_signals = run_anomaly_detection(items_with_features)

        # ── Layer 3D: Score Aggregation ──────────────────────────────────────
        score_result = aggregate_score(rule_violations, anomaly_signals, items_with_features)

        # ── Layer 3E: Explanation Generation ────────────────────────────────
        # Build per-item flagged report
        flagged_items = []
        all_flagged_item_ids = (
            {v["item_id"] for v in rule_violations} |
            {s["item_id"] for s in anomaly_signals}
        )

        for entry in items_with_features:
            item = entry["item"]
            features = entry["features"]
            item_id = item["item_id"]
            if item_id not in all_flagged_item_ids:
                continue
            explanations = generate_item_explanations(
                item, features, rule_violations, anomaly_signals
            )
            item_violations = [v for v in rule_violations if v.get("item_id") == item_id]
            item_signals = [s for s in anomaly_signals if s.get("item_id") == item_id]
            # Severity: worst among violations/signals
            severities = [v["severity"] for v in item_violations] + [s["severity"] for s in item_signals]
            severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
            worst = max(severities, key=lambda s: severity_order.get(s, 0)) if severities else "LOW"

            flagged_items.append({
                "item_id": item_id,
                "raw_description": item["raw_description"],
                "mapped_category": item["mapped_category"],
                "unit_price": item["unit_price"],
                "quantity": item["quantity"],
                "total_price": item["total_price"],
                "benchmark_p50": features.get("benchmark_p50"),
                "benchmark_p25": features.get("benchmark_p25"),
                "benchmark_p75": features.get("benchmark_p75"),
                "benchmark_source": features.get("benchmark_source"),
                "price_deviation_percentage": features.get("price_deviation_percentage"),
                "unit_price_outlier_z": features.get("unit_price_outlier_z"),
                "duplicate_count": features.get("duplicate_count"),
                "service_frequency": features.get("service_frequency"),
                "severity": worst,
                "explanations": explanations,
                "rule_violations": [v["rule_id"] for v in item_violations],
                "anomaly_signals": [s["signal_type"] for s in item_signals],
            })

        # Calculate UNKNOWN ratio for OCR quality caveat
        unknown_count = sum(1 for item in line_items if item["mapped_category"] == "UNKNOWN")
        unknown_ratio = unknown_count / len(line_items) if line_items else 0.0

        summary = generate_summary_explanation(
            fraud_score=score_result["fraud_score"],
            risk_label=score_result["risk_label"],
            total_overcharge=score_result["total_overcharge_estimate"],
            flagged_count=len(flagged_items),
            total_count=len(line_items),
            unknown_ratio=unknown_ratio,
            confidence=score_result.get("confidence", 1.0),
        )

        # Persist FraudAnalysis record
        analysis = FraudAnalysis(
            id=str(uuid.uuid4()),
            job_id=job_id,
            fraud_score=score_result["fraud_score"],
            risk_label=score_result["risk_label"],
            flagged_items=flagged_items,
            rule_violations=rule_violations,
            anomaly_signals=anomaly_signals,
            summary_explanation=summary,
        )
        db.add(analysis)
        await update_job_status(db, job_id, "COMPLETE",
                                detail=f"Score={score_result['fraud_score']}, Risk={score_result['risk_label']}")
        await db.commit()
        print(f"[Worker] Completed job {job_id} → score={score_result['fraud_score']}, risk={score_result['risk_label']}")
