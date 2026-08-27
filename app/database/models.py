from datetime import datetime
import enum
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Enum, ForeignKey, Boolean, Text, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class VoteStatus(str, enum.Enum):
    PENDING_OTP = "PENDING_OTP"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"

class PayoutType(str, enum.Enum):
    CARD = "CARD"        # Uzcard / Humo 16 digits
    PHONE = "PHONE"      # Direct Paynet/Payme transfer

class TicketStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    PAID = "PAID"
    REJECTED = "REJECTED"
    HIGH_RISK = "HIGH_RISK"

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True, index=True)
    full_name = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    is_blocked = Column(Boolean, default=False)
    risk_score = Column(Integer, default=0)
    
    balance_uzs = Column(BigInteger, default=0)
    referrer_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=True, index=True)
    referral_count = Column(Integer, default=0)
    referral_earnings_uzs = Column(BigInteger, default=0)
    manual_votes_offset = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    votes = relationship("Vote", back_populates="user")
    tickets = relationship("PayoutTicket", back_populates="user")

class Group(Base):
    __tablename__ = "groups"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)

class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    voted_phone_number = Column(String(20), unique=True, nullable=False, index=True)
    openbudget_project_id = Column(String(100), nullable=False)
    openbudget_tx_id = Column(String(100), unique=True, nullable=True)
    status = Column(Enum(VoteStatus), default=VoteStatus.PENDING_OTP, nullable=False)
    bot_identifier = Column(String(50), default="bot1", index=True, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="votes")
    payout_ticket = relationship("PayoutTicket", back_populates="vote", uselist=False)

    __table_args__ = (
        UniqueConstraint("voted_phone_number", name="uq_voted_phone_number"),
    )

class PayoutTicket(Base):
    __tablename__ = "payout_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_code = Column(String(50), unique=True, nullable=False, index=True)
    telegram_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True)
    vote_id = Column(Integer, ForeignKey("votes.id"), nullable=True, unique=False)
    bot_identifier = Column(String(50), default="bot1", index=True, nullable=True)
    
    payout_type = Column(Enum(PayoutType), nullable=False)
    destination = Column(String(50), nullable=False, index=True)
    card_holder_name = Column(String(255), nullable=True)
    amount_uzs = Column(Integer, nullable=False)
    
    status = Column(Enum(TicketStatus), default=TicketStatus.PENDING, nullable=False, index=True)
    risk_reason = Column(Text, nullable=True)
    processed_by_admin_id = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="tickets")
    vote = relationship("Vote", back_populates="payout_ticket")

class SystemBudget(Base):
    __tablename__ = "system_budget"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_budget_uzs = Column(BigInteger, nullable=False, default=125000000)
    total_reserved_uzs = Column(BigInteger, nullable=False, default=0)
    total_paid_uzs = Column(BigInteger, nullable=False, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
