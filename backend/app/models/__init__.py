"""Export all SQLAlchemy models so Alembic autogenerate and metadata.create_all discover them."""

from app.models.entities import (
    Activity,
    Customer,
    KnowledgeBaseDoc,
    Lead,
    LLMUsage,
    Product,
    User,
)

__all__ = [
    "User",
    "Customer",
    "Lead",
    "Activity",
    "Product",
    "LLMUsage",
    "KnowledgeBaseDoc",
]
