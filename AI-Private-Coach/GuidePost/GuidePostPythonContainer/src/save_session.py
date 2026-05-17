import uuid
from src.database import SessionLocal
from src.database_models import User, Session
from datetime import datetime
    
def create_update_user(name, email, occupation, seniorityLevel):
    from src.main import SessionsReponse

    with SessionLocal() as db:
        # Check if user already exists
        user = db.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                name=name,
                email=email,
                occupation=occupation,
                seniorityLevel=seniorityLevel
            )
            db.add(user)
        else:
            user.last_login = datetime.utcnow()
        
        db.commit()
        db.refresh(user)
        
        sessions = db.query(Session).filter_by(user_id=user.id)
        sessions_data = []
        for session in sessions:
            sessions_data.append(SessionsReponse(report="", cri=session.cri, cei=session.cei, sentiment=session.sentiment, speaker_volatility=session.sentiment))

        return sessions_data, user.id
    
def create_session_data(userId, transcript, cri, cei, *, audio_id=None):
    # Use context manager to automatically close session
    with SessionLocal() as db:
        # Normalize userId to UUID (db column type is UUID)
        try:
            if isinstance(userId, str):
                userId = uuid.UUID(userId)
        except Exception:
            pass
        # Create session record
        session_record = Session(
            user_id=userId,
            audio_id=audio_id,
            audio_url="audio_url",
            transcript=transcript,
            cri=cri,
            cei=cei,
            sentiment=0,
            speaker_volatility=0
        )
        db.add(session_record)
        db.commit()       # Commit to get the session_record.id
        db.refresh(session_record)