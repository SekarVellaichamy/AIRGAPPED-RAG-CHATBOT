from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: Optional[str] = None
    hashed_password: str
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    sessions: List["ChatSession"] = Relationship(back_populates="user")

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="New Chat")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="sessions")
    
    messages: List["Message"] = Relationship(back_populates="session")

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="chatsession.id")
    role: str # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    session: ChatSession = Relationship(back_populates="messages")
    
    citations: Optional[str] = None

class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_type: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    chunks: List["DocumentChunk"] = Relationship(back_populates="document")

class DocumentChunk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="document.id")
    content: str
    page_number: Optional[int] = None
    # Use pgvector's Vector type. Using 768 for nomic-embed-text
    embedding: List[float] = Field(sa_column=Column(Vector(768)))
    
    document: Document = Relationship(back_populates="chunks")
    
    # Hierarchical Chunking fields
    parent_id: Optional[int] = Field(default=None, sa_column=Column(ForeignKey("documentchunk.id", ondelete="CASCADE")))
    is_summary: bool = Field(default=False)
    
    # Self-referential relationship
    # parent: Optional["DocumentChunk"] = Relationship(back_populates="children", sa_relationship_kwargs={"remote_side": "DocumentChunk.id"})
    # children: List["DocumentChunk"] = Relationship(back_populates="parent")
