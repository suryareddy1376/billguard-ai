"""
Layer 1 — Ingestion
Validates incoming bill payload, creates the job record, pushes to async queue.
Returns job_id immediately (non-blocking).
"""
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from models import BillJob, AuditLog


async def create_job(
    db: AsyncSession,
    patient_id: str,
    hospital_name: str,
    raw_payload: str,
    filename: str | None = None,
    user_id: str | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    job = BillJob(
        id=job_id,
        user_id=user_id,
        patient_id=patient_id,
        hospital_name=hospital_name,
        status="QUEUED",
        filename=filename,
        raw_payload=raw_payload,
    )
    db.add(job)
    db.add(AuditLog(job_id=job_id, actor="SYSTEM", action="INGEST",
                    detail=f"Job created. Patient={patient_id}, File={filename}"))
    await db.commit()
    return job_id


async def update_job_status(db: AsyncSession, job_id: str, status: str, detail: str = ""):
    from sqlalchemy import update
    from models import BillJob
    await db.execute(
        update(BillJob).where(BillJob.id == job_id).values(status=status, updated_at=datetime.utcnow())
    )
    db.add(AuditLog(job_id=job_id, actor="SYSTEM", action=f"STATUS_{status}", detail=detail))
    await db.commit()
