from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base
import config

_engine = None
_Session = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{config.DB_PATH}", echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()
