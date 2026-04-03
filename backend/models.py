from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from database import Base


class BillJob(Base):
    """Tracks ingestion jobs from upload → completion."""
    __tablename__ = "bill_jobs"

    id = Column(String, primary_key=True)                        # UUID job_id
    user_id = Column(String, nullable=True, index=True)          # Optional scoping
    patient_id = Column(String, nullable=False)
    hospital_name = Column(String, nullable=True)
    status = Column(String, default="QUEUED")                    # QUEUED | PROCESSING | COMPLETE | FAILED | OCR_FAILED
    filename = Column(String, nullable=True)
    raw_payload = Column(Text, nullable=True)                     # stored original JSON/text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class LineItem(Base):
    """Canonical normalized line item from a bill."""
    __tablename__ = "line_items"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False, index=True)
    raw_description = Column(String, nullable=False)
    mapped_category = Column(String, nullable=True)              # RADIOLOGY | PHARMACY | ICU | ...
    procedure_code = Column(String, nullable=True)
    quantity = Column(Float, default=1)
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)
    date_of_service = Column(String, nullable=True)
    data_quality_flags = Column(JSON, default=list)              # ["PRICE_INFERRED", "OCR_LOW_CONFIDENCE"]


class FraudAnalysis(Base):
    """Per-job fraud analysis result."""
    __tablename__ = "fraud_analyses"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False, unique=True, index=True)
    fraud_score = Column(Float, default=0.0)                     # 0–100
    risk_label = Column(String, default="LOW")                   # LOW | MODERATE | HIGH | CRITICAL
    flagged_items = Column(JSON, default=list)                   # [{item_id, features, violations, explanations}]
    rule_violations = Column(JSON, default=list)
    anomaly_signals = Column(JSON, default=list)
    summary_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Immutable append-only audit trail."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, nullable=True)
    actor = Column(String, default="SYSTEM")                     # SYSTEM | PATIENT | ADMIN
    action = Column(String, nullable=False)                      # INGEST | SCORE | DISPUTE | EXPORT
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserAction(Base):
    """Patient choices on flagged items."""
    __tablename__ = "user_actions"

    id = Column(String, primary_key=True)
    job_id = Column(String, nullable=False)
    item_id = Column(String, nullable=True)                      # null = whole-bill action
    action_type = Column(String, nullable=False)                 # MARK_REVIEWED | DISPUTE | REQUEST_CLARIFICATION
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
