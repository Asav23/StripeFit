"""Database engine and session helpers."""

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH, UPLOAD_DIR

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    SQLModel.metadata.create_all(engine)
    for sub in ("originals", "thumbs", "placeholders"):
        (UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)
    with Session(engine) as session:
        if session.get(models.User, 1) is None:
            session.add(models.User(id=1))
            session.commit()


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
