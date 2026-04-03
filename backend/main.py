"""
FastAPI Main Application — API Gateway layer
All endpoints. Covers:
  POST /api/bills/upload       → Layer 1: ingest + queue
  GET  /api/bills/{job_id}/status → poll job status
  GET  /api/bills/{job_id}/analysis → get full fraud analysis
  GET  /api/bills/{job_id}/items    → get line items
  POST /api/bills/{job_id}/actions  → Layer 4: user actions (dispute/review)
  GET  /api/config/tariff           → Layer 5: view benchmark rates
  GET  /api/audit/{job_id}          → Layer 6: audit log
  GET  /api/demo/sample-bill        → returns a demo bill JSON for testing
"""
import asyncio
import uuid
import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from pathlib import Path

from database import get_db, init_db
from models import BillJob, LineItem, FraudAnalysis, AuditLog, UserAction
from layers.ingestion import create_job
from queue_worker import enqueue, worker_loop


# ─── Lifespan: DB init + worker start ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(worker_loop())
    print("[App] Database initialized. Worker started.")
    yield
    print("[App] Shutting down.")


app = FastAPI(
    title="Hospital Billing Fraud Detection API",
    version="1.0.0",
    description="AI-powered fraud and overcharge detection for hospital bills",
    lifespan=lifespan,
)

import os as _os
_ALLOWED_ORIGINS = _os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic schemas ─────────────────────────────────────────────────────────
class UserActionRequest(BaseModel):
    item_id: str | None = None
    action_type: str       # MARK_REVIEWED | DISPUTE | REQUEST_CLARIFICATION
    notes: str | None = None


# ─── DEMO BILL ────────────────────────────────────────────────────────────────
SAMPLE_BILL = {
    "patient_id": "DEMO-PATIENT-001",
    "hospital_name": "City General Hospital",
    "date_of_service": "2024-03-15",
    "line_items": [
        {"description": "MRI Brain Plain", "unit_price": 22000, "quantity": 1},
        {"description": "MRI Brain Plain", "unit_price": 22000, "quantity": 1},
        {"description": "CBC Blood Test", "unit_price": 800, "quantity": 1},
        {"description": "ICU Charges", "unit_price": 18000, "quantity": 3},
        {"description": "Room Charge (General Ward)", "unit_price": 4500, "quantity": 3},
        {"description": "Doctor Consultation Fee", "unit_price": 2500, "quantity": 1},
        {"description": "CT Scan Abdomen", "unit_price": 9500, "quantity": 1},
        {"description": "Paracetamol 500mg Tablet", "unit_price": 12, "quantity": 20},
        {"description": "Oxygen Charges", "unit_price": 1200, "quantity": 2},
        {"description": "Nursing Charges", "unit_price": 800, "quantity": 3},
        {"description": "Miscellaneous Hospital Fees", "unit_price": 8500, "quantity": 1},
        {"description": "ECG", "unit_price": 350, "quantity": 1},
    ]
}

FRAUD_BILL = {
    "patient_id": "DEMO-PATIENT-002",
    "hospital_name": "Metro Hospital",
    "date_of_service": "2024-03-20",
    "line_items": [
        {"description": "MRI Brain Plain", "unit_price": 45000, "quantity": 1},
        {"description": "MRI Brain Plain", "unit_price": 45000, "quantity": 1},
        {"description": "CT Scan Chest", "unit_price": 22000, "quantity": 1},
        {"description": "ICU Charges", "unit_price": 35000, "quantity": 5},
        {"description": "Room Charge (General Ward)", "unit_price": 12000, "quantity": 5},
        {"description": "General Anaesthesia", "unit_price": 40000, "quantity": 1},
        {"description": "Doctor Consultation Fee", "unit_price": 8000, "quantity": 4},
        {"description": "Blood Test CBC", "unit_price": 2500, "quantity": 3},
        {"description": "Urine Analysis", "unit_price": 1800, "quantity": 2},
        {"description": "Surgical Procedure", "unit_price": 150000, "quantity": 1},
        {"description": "Unnamed charges type A", "unit_price": 12000, "quantity": 1},
        {"description": "Unnamed charges type B", "unit_price": 9500, "quantity": 1},
    ]
}


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@app.get("/api/demo/sample-bill")
async def get_sample_bill(scenario: str = "moderate"):
    """Return a pre-built sample bill for testing. scenario=moderate|fraud"""
    bill = FRAUD_BILL if scenario == "fraud" else SAMPLE_BILL
    return {"bill": bill, "instructions": "POST this JSON to /api/bills/upload"}


@app.post("/api/bills/upload")
async def upload_bill(
    patient_id: str = Form(...),
    hospital_name: str = Form(default="Unknown Hospital"),
    user_id: str = Form(None),
    bill_json: str = Form(None),
    file: UploadFile = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Layer 1 — Ingestion.
    Accepts bill as JSON string (bill_json) or image file upload.
    Returns job_id immediately (non-blocking).
    """
    raw_payload = None

    if not bill_json and not file:
        raise HTTPException(status_code=400, detail="Must provide either bill_json or an image file.")

    if file:
        content = await file.read()
        if file.content_type in ("application/json", "text/plain"):
            raw_payload = content.decode("utf-8")
        else:
            # We process the image entirely in memory via the OCR engine, so we
            # do not need to persist the raw bytes to a Supabase bucket.

            # Process with OCR engine
            from layers.ocr_engine import extract_text_from_image
            ocr_result = extract_text_from_image(content)
            if not ocr_result["ok"]:
                raise HTTPException(
                    status_code=415,
                    detail=f"OCR failed: {ocr_result['error']}"
                )
            raw_payload = ocr_result["text"]
            
    elif bill_json:
        try:
            json.loads(bill_json)  # validate it's parseable
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in bill_json field")
        raw_payload = bill_json

    # Inject patient_id and hospital_name into payload if it's JSON
    try:
        parsed = json.loads(raw_payload)
        parsed.setdefault("patient_id", patient_id)
        parsed.setdefault("hospital_name", hospital_name)
        raw_payload = json.dumps(parsed)
    except Exception:
        # If it's pure OCR text, the nlp normalization handles it later
        pass

    job_id = await create_job(db, patient_id, hospital_name, raw_payload,
                               filename=file.filename if file else None,
                               user_id=user_id)
    await enqueue(job_id, raw_payload)

    return {
        "job_id": job_id,
        "status": "QUEUED",
        "message": "Bill received. Processing has started. Poll /api/bills/{job_id}/status for updates.",
        "poll_url": f"/api/bills/{job_id}/status",
        "processed_via": "OCR" if file and file.content_type not in ("application/json", "text/plain") else "JSON"
    }


@app.get("/api/bills/history")
async def get_bill_history(user_id: str = None, db: AsyncSession = Depends(get_db)):
    """Returns all past bill analyses with aggregate statistics for the history dashboard."""
    from sqlalchemy import func as sqlfunc, desc

    # Get all completed jobs with their analyses
    query = (select(BillJob, FraudAnalysis)
             .outerjoin(FraudAnalysis, BillJob.id == FraudAnalysis.job_id)
             .where(BillJob.status == "COMPLETE"))

    if user_id:
        query = query.where(BillJob.user_id == user_id)

    query = query.order_by(desc(BillJob.created_at))
    result = await db.execute(query)
    rows = result.all()

    bills = []
    total_overcharge = 0
    scores = []

    for job, analysis in rows:
        score = analysis.fraud_score if analysis else 0
        risk = analysis.risk_label if analysis else "UNKNOWN"
        flagged_count = len(analysis.flagged_items or []) if analysis else 0

        # Calculate overcharge for this bill
        bill_overcharge = 0
        flagged_items = analysis.flagged_items or [] if analysis else []
        for item in flagged_items:
            up = item.get("unit_price") or 0
            p75 = item.get("benchmark_p75") or 0
            qty = item.get("quantity", 1) or 1
            if up > p75:
                bill_overcharge += (up - p75) * qty

        total_overcharge += bill_overcharge
        scores.append(score)

        # Get line item count
        items_result = await db.execute(
            select(sqlfunc.count()).select_from(LineItem).where(LineItem.job_id == job.id)
        )
        item_count = items_result.scalar() or 0

        bills.append({
            "job_id": job.id,
            "patient_id": job.patient_id,
            "hospital_name": job.hospital_name,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "fraud_score": score,
            "risk_label": risk,
            "flagged_count": flagged_count,
            "total_items": item_count,
            "overcharge_estimate": round(bill_overcharge, 2),
        })

    # Aggregate stats
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    risk_counts = {"LOW": 0, "MODERATE": 0, "HIGH": 0, "CRITICAL": 0}
    for b in bills:
        if b["risk_label"] in risk_counts:
            risk_counts[b["risk_label"]] += 1

    return {
        "total_bills": len(bills),
        "total_overcharge_detected": round(total_overcharge, 2),
        "average_fraud_score": avg_score,
        "risk_distribution": risk_counts,
        "bills": bills,
    }


@app.get("/api/bills/{job_id}/status")
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    """Poll ingestion job status."""
    result = await db.execute(select(BillJob).where(BillJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    response = {
        "job_id": job_id,
        "status": job.status,
        "patient_id": job.patient_id,
        "hospital_name": job.hospital_name,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }

    if job.status == "COMPLETE":
        response["analysis_url"] = f"/api/bills/{job_id}/analysis"

    return response


@app.get("/api/bills/{job_id}/analysis")
async def get_analysis(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Layer 4 — Full fraud analysis result for the patient dashboard.
    Returns fraud_score, risk_label, flagged items, explanations, overcharge estimate.
    """
    result = await db.execute(select(FraudAnalysis).where(FraudAnalysis.job_id == job_id))
    analysis = result.scalar_one_or_none()
    if not analysis:
        # Check if job exists and its status
        job_result = await db.execute(select(BillJob).where(BillJob.id == job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        raise HTTPException(
            status_code=202,
            detail=f"Job status is '{job.status}'. Analysis not ready yet."
        )

    return {
        "job_id": job_id,
        "fraud_score": analysis.fraud_score,
        "risk_label": analysis.risk_label,
        "summary_explanation": analysis.summary_explanation,
        "flagged_items": analysis.flagged_items,
        "rule_violations_count": len(analysis.rule_violations or []),
        "anomaly_signals_count": len(analysis.anomaly_signals or []),
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }


@app.get("/api/bills/{job_id}/items")
async def get_line_items(job_id: str, db: AsyncSession = Depends(get_db)):
    """Returns all normalized line items for a bill."""
    result = await db.execute(select(LineItem).where(LineItem.job_id == job_id))
    items = result.scalars().all()
    return {
        "job_id": job_id,
        "total_items": len(items),
        "items": [
            {
                "item_id": i.id,
                "raw_description": i.raw_description,
                "mapped_category": i.mapped_category,
                "procedure_code": i.procedure_code,
                "quantity": i.quantity,
                "unit_price": i.unit_price,
                "total_price": i.total_price,
                "date_of_service": i.date_of_service,
                "data_quality_flags": i.data_quality_flags,
            }
            for i in items
        ],
    }


@app.post("/api/bills/{job_id}/actions")
async def submit_user_action(
    job_id: str,
    action: UserActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Layer 4 — User-confirmed actions. Patient chooses what to do with flagged items.
    NO automatic escalation. All actions are recorded for audit and feedback loop.
    """
    valid_actions = {"MARK_REVIEWED", "DISPUTE", "REQUEST_CLARIFICATION"}
    if action.action_type not in valid_actions:
        raise HTTPException(status_code=400, detail=f"action_type must be one of {valid_actions}")

    user_action = UserAction(
        id=str(uuid.uuid4()),
        job_id=job_id,
        item_id=action.item_id,
        action_type=action.action_type,
        notes=action.notes,
    )
    db.add(user_action)
    db.add(AuditLog(
        job_id=job_id,
        actor="PATIENT",
        action=action.action_type,
        detail=f"item_id={action.item_id}, notes={action.notes}",
    ))
    await db.commit()

    messages = {
        "DISPUTE": "Dispute recorded. Download your report to submit to your insurer or hospital.",
        "MARK_REVIEWED": "Item marked as reviewed. No further action taken.",
        "REQUEST_CLARIFICATION": "Clarification request logged. Contact the hospital billing department with your bill ID.",
    }
    return {"status": "ok", "message": messages[action.action_type], "action_id": user_action.id}


@app.get("/api/bills/{job_id}/report")
async def get_report(job_id: str, db: AsyncSession = Depends(get_db)):
    """Layer 4 — Export-ready dispute report with all flagged items and benchmarks."""
    result = await db.execute(select(FraudAnalysis).where(FraudAnalysis.job_id == job_id))
    analysis = result.scalar_one_or_none()
    job_result = await db.execute(select(BillJob).where(BillJob.id == job_id))
    job = job_result.scalar_one_or_none()
    if not analysis or not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    actions_result = await db.execute(select(UserAction).where(UserAction.job_id == job_id))
    actions = actions_result.scalars().all()

    disputed_ids = {a.item_id for a in actions if a.action_type == "DISPUTE"}
    disputed_items = [i for i in (analysis.flagged_items or []) if i["item_id"] in disputed_ids]

    return {
        "report_id": f"RPT-{job_id[:8].upper()}",
        "generated_at": datetime.utcnow().isoformat(),
        "patient_id": job.patient_id,
        "hospital_name": job.hospital_name,
        "fraud_score": analysis.fraud_score,
        "risk_label": analysis.risk_label,
        "summary": analysis.summary_explanation,
        "total_flagged": len(analysis.flagged_items or []),
        "disputed_items": disputed_items,
        "all_flagged_items": analysis.flagged_items,
        "disclaimer": (
            "This report is generated by an automated billing analysis system. "
            "It is advisory only. All disputes must be reviewed by a qualified professional."
        ),
    }


@app.get("/api/config/tariff")
async def get_tariff():
    """Layer 5 — View benchmark tariff data."""
    tariff_path = Path(__file__).parent / "tariff" / "cghs_rates.json"
    with open(tariff_path, encoding="utf-8") as f:
        tariff = json.load(f)
        
    tariff_list = []
    for code, details in tariff.items():
        if code != "UNKNOWN":
            tariff_list.append({"code": code, **details})
            
    tariff_list.sort(key=lambda x: x.get("name", ""))
    return {"tariff": tariff_list}


@app.get("/api/audit/{job_id}")
async def get_audit_log(job_id: str, db: AsyncSession = Depends(get_db)):
    """Layer 6 — Immutable audit log for a given job."""
    result = await db.execute(
        select(AuditLog).where(AuditLog.job_id == job_id).order_by(AuditLog.created_at)
    )
    logs = result.scalars().all()
    return {
        "job_id": job_id,
        "audit_entries": [
            {
                "id": log.id,
                "actor": log.actor,
                "action": log.action,
                "detail": log.detail,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


@app.get("/api/bills/{job_id}/complaint-letter")
async def get_complaint_letter(job_id: str, db: AsyncSession = Depends(get_db)):
    """Generate a formal complaint letter for disputing overcharged bills."""
    result = await db.execute(select(FraudAnalysis).where(FraudAnalysis.job_id == job_id))
    analysis = result.scalar_one_or_none()
    job_result = await db.execute(select(BillJob).where(BillJob.id == job_id))
    job = job_result.scalar_one_or_none()
    if not analysis or not job:
        raise HTTPException(status_code=404, detail="Analysis not found")

    flagged = analysis.flagged_items or []
    # Use p75 (75th percentile) as the overcharge benchmark — consistent with score_aggregator
    overcharged_items = [
        i for i in flagged
        if (i.get("unit_price") is not None
            and i.get("benchmark_p75") is not None
            and i["unit_price"] > i["benchmark_p75"])
    ]

    # Build the items table for the letter
    items_table = []
    total_overcharge = 0
    for item in overcharged_items:
        p75 = item["benchmark_p75"]
        diff = item["unit_price"] - p75
        qty = item.get("quantity", 1) or 1
        total_overcharge += diff * qty
        items_table.append({
            "description": item["raw_description"],
            "charged": item["unit_price"],
            "benchmark": p75,
            "benchmark_source": item.get("benchmark_source", "CGHS 2024"),
            "difference": round(diff, 2),
            "quantity": qty,
            "deviation_pct": round(item.get("price_deviation_percentage", 0), 1),
        })

    today = datetime.utcnow().strftime("%d %B %Y")
    report_id = f"RPT-{job_id[:8].upper()}"

    letter = {
        "report_id": report_id,
        "generated_date": today,
        "patient_id": job.patient_id,
        "hospital_name": job.hospital_name or "the Hospital",
        "fraud_score": analysis.fraud_score,
        "risk_label": analysis.risk_label,
        "total_flagged": len(flagged),
        "total_overcharged_items": len(overcharged_items),
        "total_overcharge_estimate": round(total_overcharge, 2),
        "items": items_table,
        "letter_body": _generate_letter_text(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            report_id=report_id,
            items=items_table,
            total_overcharge=total_overcharge,
            fraud_score=analysis.fraud_score,
        ),
        "letter_body_hindi": _generate_letter_hindi(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "letter_body_marathi": _generate_letter_marathi(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "letter_body_tamil": _generate_letter_tamil(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "letter_body_telugu": _generate_letter_telugu(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "letter_body_bengali": _generate_letter_bengali(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "letter_body_kannada": _generate_letter_kannada(
            patient_id=job.patient_id,
            hospital_name=job.hospital_name or "the Hospital",
            date=today,
            items=items_table,
            total_overcharge=total_overcharge,
        ),
        "helplines": [
            {"name": "National Consumer Helpline", "number": "1800-11-4000", "url": "https://consumerhelpline.gov.in/"},
            {"name": "Insurance Ombudsman", "number": "155255", "url": "https://cioins.co.in/"},
            {"name": "State Medical Council", "url": "https://www.nmc.org.in/information-desk/indian-medical-register/"},
            {"name": "IRDAI (Insurance Complaints)", "number": "155255", "url": "https://igms.irda.gov.in/"},
        ],
        "legal_references": [
            "Consumer Protection Act, 2019 — Section 2(6): Deficiency in service includes charging excess amount",
            "Clinical Establishments Act, 2010 — Mandates transparent pricing and rate display",
            "CGHS (Central Government Health Scheme) Rate Cards — Benchmark pricing for medical procedures",
            "Indian Medical Council (Professional Conduct) Regulations, 2002 — Clause 1.1.3: No overcharging",
        ],
    }

    return letter


def _generate_letter_text(patient_id, hospital_name, date, report_id, items, total_overcharge, fraud_score):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      Charged: Rs. {item['charged']:,.0f} | "
            f"CGHS Fair Upper Bound (p75): Rs. {item['benchmark']:,.0f} | "
            f"Excess: Rs. {item['difference']:,.0f} ({item['deviation_pct']}% above median)\n\n"
        )

    return f"""To,
The Medical Superintendent / Billing Department
{hospital_name}

Date: {date}

Subject: Formal Complaint Regarding Overcharged Medical Bill
Reference: BillGuard Analysis Report {report_id}

Dear Sir/Madam,

I, bearing Patient ID {patient_id}, am writing to formally dispute certain charges on my medical bill issued by {hospital_name}. An independent automated analysis of my itemized bill against the Central Government Health Scheme (CGHS) 2024 benchmark rates has revealed significant discrepancies in the following items:

{items_text}
Total Estimated Overcharge: Rs. {total_overcharge:,.0f}
BillGuard Fraud Risk Score: {fraud_score}/100

I hereby request:

1. A detailed itemized breakdown of all charges with justification for prices exceeding CGHS benchmark rates.
2. A revised bill reflecting fair market rates for the above-mentioned procedures.
3. A written response within 15 days of receipt of this letter, as mandated under the Consumer Protection Act, 2019.

Please note that under Section 2(6) of the Consumer Protection Act, 2019, charging excess amounts constitutes "deficiency in service." I reserve the right to escalate this matter to the National Consumer Disputes Redressal Commission and/or the State Medical Council if a satisfactory resolution is not provided within the stipulated timeframe.

I also reserve the right to file a complaint with the Insurance Regulatory and Development Authority of India (IRDAI) if these charges were submitted to my insurance provider.

This complaint is supported by an automated billing analysis report (ID: {report_id}) which benchmarks each line item against nationally recognized CGHS 2024 rate cards.

I look forward to a prompt and fair resolution.

Yours sincerely,
[Patient Name]
Patient ID: {patient_id}
Date: {date}

Encl: BillGuard AI Analysis Report ({report_id})"""


def _generate_letter_hindi(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      लिया गया: Rs. {item['charged']:,.0f} | "
            f"CGHS दर: Rs. {item['benchmark']:,.0f} | "
            f"अतिरिक्त: Rs. {item['difference']:,.0f}\n\n"
        )

    return f"""सेवा में,
चिकित्सा अधीक्षक / बिलिंग विभाग
{hospital_name}

दिनांक: {date}

विषय: चिकित्सा बिल में अधिक शुल्क के संबंध में औपचारिक शिकायत

महोदय/महोदया,

मैं, रोगी आईडी {patient_id}, अपने चिकित्सा बिल में कुछ शुल्कों को लेकर औपचारिक रूप से विवाद दर्ज करना चाहता/चाहती हूं। केंद्र सरकार स्वास्थ्य योजना (CGHS) 2024 बेंचमार्क दरों के खिलाफ मेरे बिल के स्वतंत्र विश्लेषण से निम्नलिखित विसंगतियां सामने आई हैं:

{items_text}
कुल अनुमानित अधिक शुल्क: Rs. {total_overcharge:,.0f}

मैं अनुरोध करता/करती हूं कि उपरोक्त शुल्कों का विस्तृत विवरण और उचित बाजार दरों के अनुसार संशोधित बिल 15 दिनों के भीतर प्रदान किया जाए।

उपभोक्ता संरक्षण अधिनियम, 2019 की धारा 2(6) के तहत, अधिक शुल्क लेना "सेवा में कमी" माना जाता है।

भवदीय,
[रोगी का नाम]
रोगी आईडी: {patient_id}"""

def _generate_letter_marathi(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      आकारलेली रक्कम: Rs. {item['charged']:,.0f} | "
            f"CGHS योग्य दर: Rs. {item['benchmark']:,.0f} | "
            f"अतिरिक्त रक्कम: Rs. {item['difference']:,.0f}\n\n"
        )
    return f"""प्रति,
वैद्यकीय अधीक्षक / बिलिंग विभाग
{hospital_name}

दिनांक: {date}

विषय: वैद्यकीय बिलातील अतिरिक्त शुल्काबाबत अधिकृत तक्रार

महोदय/महोदया,

मी, रुग्ण आयडी {patient_id}, {hospital_name} द्वारे जारी केलेल्या माझ्या वैद्यकीय बिलातील काही युनिट्सबाबत अधिकृतपणे आक्षेप नोंदवत आहे. केंद्र सरकार आरोग्य योजना (CGHS) 2024 च्या मानकांविरुद्ध माझ्या बिलाच्या स्वतंत्र विश्लेषणातून खालील तफावत समोर आली आहे:

{items_text}
एकूण अंदाजित अतिरिक्त शुल्क: Rs. {total_overcharge:,.0f}

मी विनंती करतो/करते की वरील प्रक्रियांसाठी वाजवी बाजारभावानुसार सुधारीत बिल १५ दिवसांच्या आत द्यावे. ग्राहक संरक्षण कायदा, २०१९ च्या कलम २(६) नुसार अतिरिक्त रक्कम आकारणे ही "सेवेतील कमतरता" मानली जाते.

आपला नम्र,
[रुग्णाचे नाव]
रुग्ण आयडी: {patient_id}"""

def _generate_letter_tamil(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      வசூலிக்கப்பட்ட தொகை: Rs. {item['charged']:,.0f} | "
            f"CGHS நியாயமான கட்டணம்: Rs. {item['benchmark']:,.0f} | "
            f"கூடுதல் தொகை: Rs. {item['difference']:,.0f}\n\n"
        )
    return f"""பெறுநர்,
மருத்துவ கண்காணிப்பாளர் / பில்லிங் துறை
{hospital_name}

தேதி: {date}

பொருள்: மருத்துவ கட்டணத்தில் அதிக கட்டணம் வசூலித்தது குறித்த புகார்

ஐயா / அம்மா,

நோயாளி ஐடி {patient_id} கொண்ட நான், {hospital_name} வழங்கிய எனது மருத்துவ கட்டணத்தில் உள்ள சில கட்டணங்கள் குறித்து முறையாக புகார் அளிக்கிறேன். மத்திய அரசு சுகாதாரத் திட்டத்தின் (CGHS) 2024 கட்டண வரம்புகளுக்கு எதிராக எனது பில்லின் சுயாதீன பகுப்பாய்வில் பின்வரும் முரண்பாடுகள் கண்டறியப்பட்டுள்ளன:

{items_text}
மொத்த கூட்டப்பட்ட கட்டணம்: Rs. {total_overcharge:,.0f}

நியாயமான கட்டணங்கள் அடங்கிய திருத்தப்பட்ட பில்லை 15 நாட்களுக்குள் வழங்குமாறு கேட்டுக்கொள்கிறேன். நுகர்வோர் பாதுகாப்புச் சட்டம், 2019 இன் பிரிவு 2(6) இன் கீழ், அதிக கட்டணம் வசூலிப்பது "சேவையில் குறைபாடு" ஆகும்.

தங்கள் உண்மையுள்ள,
[நோயாளியின் பெயர்]
நோயாளி ஐடி: {patient_id}"""

def _generate_letter_telugu(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      వసూలు చేసిన మొత్తం: Rs. {item['charged']:,.0f} | "
            f"CGHS న్యాయమైన ధర: Rs. {item['benchmark']:,.0f} | "
            f"అదనపు మొత్తం: Rs. {item['difference']:,.0f}\n\n"
        )
    return f"""గౌరవనీయులైన,
మెడికల్ సూపరింటెండెంట్ / బిల్లింగ్ విభాగం
{hospital_name}

తేదీ: {date}

విషయం: మెడికల్ బిల్లులో అధిక చార్జీలపై ఫిర్యాదు

అయ్యా/అమ్మ,

పేషెంట్ ఐడీ {patient_id} కలిగిన నేను, {hospital_name} జారీ చేసిన నా మెడికల్ బిల్లులోని కొన్ని చార్జీలపై అధికారికంగా ఫిర్యాదు చేస్తున్నాను. కేంద్ర ప్రభుత్వ ఆరోగ్య పథకం (CGHS) 2024 ప్రమాణాలకు వ్యతిరేకంగా నా బిల్లును విశ్లేషించగా ఈ క్రింది వ్యత్యాసాలు వెల్లడయ్యాయి:

{items_text}
మొత్తం అదనపు ఛార్జీ: Rs. {total_overcharge:,.0f}

దయచేసి 15 రోజుల్లోగా సరైన మార్కెట్ ధరలతో సవరించిన బిల్లును అందించాల్సిందిగా కోరుతున్నాను. వినియోగదారుల రక్షణ చట్టం, 2019 లోని సెక్షన్ 2(6) ప్రకారం, అధిక మొత్తం వసూలు చేయడం "సేవలో లోపం" కిందకు వస్తుంది.

భవదీయులు,
[పేషెంట్ పేరు]
పేషెంట్ ఐడీ: {patient_id}"""

def _generate_letter_bengali(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      চার্জ করা হয়েছে: Rs. {item['charged']:,.0f} | "
            f"CGHS নির্ধারিত হার: Rs. {item['benchmark']:,.0f} | "
            f"অতিরিক্ত মূল্য: Rs. {item['difference']:,.0f}\n\n"
        )
    return f"""প্রতি,
মেডিকেল সুপারিনটেনডেন্ট / বিলিং বিভাগ
{hospital_name}

তারিখ: {date}

বিষয়: মেডিকেল বিলে অতিরিক্ত চার্জের আনুষ্ঠানিক অভিযোগ

মহাশয়/মহাশয়া,

আমি, রোগীর আইডি {patient_id}, {hospital_name} কর্তৃক জারি করা আমার মেডিকেল বিলে অতিরিক্ত চার্জের বিষয়ে আনুষ্ঠানিকভাবে অভিযোগ জানাচ্ছি। সেন্ট্রাল গভর্নমেন্ট হেলথ স্কিম (CGHS) ২০২৪ বেঞ্চমার্ক হারের বিপরীতে আমার বিলটির স্বাধীন বিশ্লেষণের মাধ্যমে নিম্নলিখিত অতিরিক্ত চার্জগুলি পাওয়া গেছে:

{items_text}
মোট আনুমানিক অতিরিক্ত চার্জ: Rs. {total_overcharge:,.0f}

আমি অনুরোধ করছি যে ন্যায্য বাজার মূল্যের ভিত্তিতে ১৫ দিনের মধ্যে একটি সংশোধিত বিল প্রদান করা হোক। ভোক্তা সংরক্ষণ আইন, ২০১৯ এর ধারা ২(৬) অনুসারে, অতিরিক্ত অর্থ আদায় করা "পরিষেবায় ঘাটতি" হিসেবে বিবেচিত হয়।

বিনীত,
[রোগীর নাম]
রোগীর আইডি: {patient_id}"""

def _generate_letter_kannada(patient_id, hospital_name, date, items, total_overcharge):
    items_text = ""
    for i, item in enumerate(items, 1):
        items_text += (
            f"   {i}. {item['description']}\n"
            f"      ವಿಧಿಸಲಾದ ಶುಲ್ಕ: Rs. {item['charged']:,.0f} | "
            f"CGHS ದರ: Rs. {item['benchmark']:,.0f} | "
            f"ಹೆಚ್ಚುವರಿ ಶುಲ್ಕ: Rs. {item['difference']:,.0f}\n\n"
        )
    return f"""ಗೆ,
ವೈದ್ಯಕೀಯ ಅಧೀಕ್ಷಕರು / ಬಿಲ್ಲಿಂಗ್ ವಿಭಾಗ
{hospital_name}

ದಿನಾಂಕ: {date}

ವಿಷಯ: ವೈದ್ಯಕೀಯ ಬಿಲ್‌ನಲ್ಲಿ ಹೆಚ್ಚುವರಿ ಶುಲ್ಕದ ಬಗ್ಗೆ ದೂರು

ಮಾನ್ಯರೆ,

ರೋಗಿಯ ಐಡಿ {patient_id} ಹೊಂದಿರುವ ನಾನು, {hospital_name} ನೀಡಿದ ನನ್ನ ವೈದ್ಯಕೀಯ ಬಿಲ್‌ನಲ್ಲಿರುವ ಕೆಲವು ಶುಲ್ಕಗಳ ಬಗ್ಗೆ ಅಧಿಕೃತವಾಗಿ ದೂರು ನೀಡುತ್ತಿದ್ದೇನೆ. ಕೇಂದ್ರ ಸರ್ಕಾರದ ಆರೋಗ್ಯ ಯೋಜನೆ (CGHS) 2024 ರ ಮಾನದಂಡದ ವಿರುದ್ಧ ನನ್ನ ಬಿಲ್‌ನ ವಿಶ್ಲೇಷಣೆಯಲ್ಲಿ ಈ ಕೆಳಗಿನ ವ್ಯತ್ಯಾಸಗಳು ಕಂಡುಬಂದಿವೆ:

{items_text}
ಒಟ್ಟು ಅಂದಾಜು ಹೆಚ್ಚುವರಿ ಶುಲ್ಕ: Rs. {total_overcharge:,.0f}

ನ್ಯಾಯಯುತ ಮಾರುಕಟ್ಟೆ ದರಗಳೊಂದಿಗೆ ಪರಿಷ್ಕೃತ ಬಿಲ್ ಅನ್ನು 15 ದಿನಗಳಲ್ಲಿ ನೀಡಬೇಕೆಂದು ನಾನು ವಿನಂತಿಸುತ್ತೇನೆ. ಗ್ರಾಹಕ ಸಂರಕ್ಷಣಾ ಕಾಯ್ದೆ 2019 ರ ಸೆಕ್ಷನ್ 2(6) ರ ಪ್ರಕಾರ, ಹೆಚ್ಚಿನ ಹಣವನ್ನು ವಿಧಿಸುವುದು "ಸೇವೆಯ ಕೊರತೆ" ಎಂದು ಪರಿಗಣಿಸಲಾಗಿದೆ.

ವಂದನೆಗಳೊಂದಿಗೆ,
[ರೋಗಿಯ ಹೆಸರು]
ರೋಗಿಯ ಐಡಿ: {patient_id}"""



@app.get("/health")
async def health():
    return {"status": "ok", "service": "hospital-billing-fraud-detection", "version": "1.0.0"}
