from sqlmodel import SQLModel, create_engine, Session, select, text
from app.core.config import settings
from app.models.models import User
from app.core.security import get_password_hash

# Create engine
engine = create_engine(settings.DATABASE_URL, echo=False)

def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    # Enable pgvector extension before creating tables
    with Session(engine) as session:
        session.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))
        session.commit()
    
    SQLModel.metadata.create_all(engine)
    create_initial_admin()

def create_initial_admin():
    """Create a default admin user if none exists."""
    with Session(engine) as session:
        statement = select(User).where(User.username == "admin")
        results = session.exec(statement)
        user = results.first()
        if not user:
            print("Creating initial admin user...")
            admin_user = User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                is_admin=True,
                is_active=True
            )
            session.add(admin_user)
            session.commit()
            print("Admin user created (admin/admin123).")
