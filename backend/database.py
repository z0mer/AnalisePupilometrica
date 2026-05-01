from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = (
    "postgresql+psycopg2://neondb_owner:npg_lyL4o5dAijeh"
    "@ep-shiny-cell-acjahhe8.sa-east-1.aws.neon.tech"
    "/neondb?sslmode=require"
)

engine = create_engine(
    DATABASE_URL,
    # Mantém 5 conexões abertas no pool; permite até 10 conexões extras em pico
    pool_size=5,
    max_overflow=10,
    # Descarta conexão se a fila de espera superar 30 s
    pool_timeout=30,
    # Emite um SELECT 1 antes de entregar uma conexão do pool —
    # evita erros silenciosos após idle timeout do NeonDB
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — injeta uma sessão de banco por request.

    Uso:
        @router.get("/pilotos")
        def listar(db: Session = Depends(get_db)):
            return db.query(Piloto).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables() -> None:
    """Cria todas as tabelas no banco (idempotente via checkfirst=True)."""
    from backend import models  # noqa: F401 — importa para registrar metadados

    Base.metadata.create_all(bind=engine, checkfirst=True)


def check_connection() -> bool:
    """Verifica se a conexão com o NeonDB está ativa. Útil em health-checks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
