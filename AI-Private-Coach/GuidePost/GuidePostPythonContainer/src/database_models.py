import uuid
from sqlalchemy import Boolean, Column, String, Float, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True)
    name = Column(String)
    occupation = Column(String)
    seniorityLevel = Column(String)
    rankedSkills = Column(Text)  # JSON-encoded list[str]
    otherFocus = Column(Text)
    voiceRecorded = Column(Boolean)
    last_login = Column(DateTime, server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    audio_id = Column(Text)
    audio_url = Column(Text)
    transcript = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    cri = Column(Float)
    cei = Column(Float)
    sentiment = Column(Float)
    speaker_volatility = Column(Float)


class AudioJob(Base):
    __tablename__ = "audio_jobs"

    audio_id = Column(Text, primary_key=True)
    status = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    filename = Column(Text)

    # Where the raw audio is stored (S3 or local path)
    audio_s3_bucket = Column(Text)
    audio_s3_key = Column(Text)
    audio_local_path = Column(Text)

    # Optional voice reference used for diarization
    target_ref_s3_bucket = Column(Text)
    target_ref_s3_key = Column(Text)
    target_ref_local_path = Column(Text)

    # Inputs/outputs
    user_context = Column(Text)
    target_name = Column(Text)
    user_email = Column(Text)
    user_id = Column(Text)
    aligned_focus = Column(Text)

    transcript = Column(Text)
    segments_json = Column(Text)  # JSON-encoded list[dict]
    analysis = Column(Text)
    final_strategy = Column(Text)
    error_message = Column(Text)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    conversation_id = Column(Text, primary_key=True)
    audio_id = Column(Text, index=True)
    messages_json = Column(Text)  # JSON-encoded list[{role, content}]
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VoiceReference(Base):
    __tablename__ = "voice_references"

    target_name = Column(Text, primary_key=True)
    s3_bucket = Column(Text)
    s3_key = Column(Text)
    local_path = Column(Text)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class HomeSummary(Base):
    __tablename__ = "home_summaries"

    # Cache by target_name since the UI keys summaries by userName/targetName.
    target_name = Column(Text, primary_key=True)
    summary = Column(Text)
    computed_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Best-effort marker of the newest source transcript we used.
    source_updated_at = Column(Text)