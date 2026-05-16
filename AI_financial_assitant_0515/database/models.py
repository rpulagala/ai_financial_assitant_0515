from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class LocalAuthority(Base):
    __tablename__ = "local_authorities"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    siret = Column(String(14))
    type = Column(String(50), default="municipality")
    tenant_id = Column(String(50), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    year = Column(Integer)
    status = Column(String(20), default="open")


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    file_name = Column(String(500))
    file_type = Column(String(20))
    data_type = Column(String(50))
    imported_at = Column(DateTime, default=datetime.utcnow)
    row_count = Column(Integer, default=0)
    quality_score = Column(Float, default=0)
    status = Column(String(20), default="completed")
    warnings = Column(Text)


class BudgetLine(Base):
    __tablename__ = "budget_lines"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"))
    section = Column(String(20))  # FONCTIONNEMENT / INVESTISSEMENT
    chapter = Column(String(20))
    article = Column(String(30))
    service = Column(String(100))
    label = Column(String(500))
    voted_amount = Column(Float, default=0)
    opened_credits = Column(Float, default=0)
    committed_amount = Column(Float, default=0)
    mandated_amount = Column(Float, default=0)
    paid_amount = Column(Float, default=0)
    available_amount = Column(Float, default=0)


class Commitment(Base):
    __tablename__ = "commitments"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"))
    commitment_number = Column(String(50))
    date = Column(Date)
    supplier_name = Column(String(200))
    service = Column(String(100))
    chapter = Column(String(20))
    article = Column(String(30))
    object = Column(String(500))
    committed_amount = Column(Float)
    mandated_amount = Column(Float, default=0)
    remaining_amount = Column(Float)
    contract_reference = Column(String(100))
    status = Column(String(20), default="open")


class Mandate(Base):
    __tablename__ = "mandates"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"))
    mandate_number = Column(String(50))
    date = Column(Date)
    supplier_name = Column(String(200))
    amount = Column(Float)
    chapter = Column(String(20))
    article = Column(String(30))
    service = Column(String(100))
    status = Column(String(20), default="validated")
    rejection_reason = Column(String(500))


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    import_batch_id = Column(Integer, ForeignKey("import_batches.id"))
    name = Column(String(200))
    siret = Column(String(14))
    internal_reference = Column(String(50))
    normalized_name = Column(String(200))
    total_mandated = Column(Float, default=0)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    alert_type = Column(String(100))
    severity = Column(String(20))  # low, medium, high, critical
    rule_id = Column(String(100))
    entity_type = Column(String(50))
    entity_id = Column(Integer, nullable=True)
    title = Column(String(500))
    explanation = Column(Text)
    calculation_details = Column(Text)
    recommendation = Column(Text)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    id = Column(Integer, primary_key=True)
    local_authority_id = Column(Integer, ForeignKey("local_authorities.id"))
    session_id = Column(String(50))
    question = Column(Text)
    intent = Column(String(100))
    answer = Column(Text)
    confidence_level = Column(String(20))
    timestamp = Column(DateTime, default=datetime.utcnow)
