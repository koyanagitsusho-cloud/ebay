"""
モデルパッケージ
Alembicがautogenerateでモデルを検出するために全モデルをここでインポートする。
"""

from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.job import ApiCallLog, AuditLog, Job, JobLog, Setting
from app.models.listing import (
    Approval,
    EbayOffer,
    GeneratedContent,
    ListingDraft,
    ListingRule,
    ListingTemplate,
)
from app.models.product import InventoryItem, Product
from app.models.research import ResearchCandidate, ResearchScore
from app.models.user import User

__all__ = [
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "Product",
    "InventoryItem",
    "ResearchCandidate",
    "ResearchScore",
    "ListingDraft",
    "GeneratedContent",
    "ListingTemplate",
    "ListingRule",
    "Approval",
    "EbayOffer",
    "Job",
    "JobLog",
    "AuditLog",
    "ApiCallLog",
    "Setting",
]
