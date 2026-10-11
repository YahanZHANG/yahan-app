
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CollectedEvent:
    source_name: str
    external_id: str
    title: str
    original_url: str

    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    description: str = ""
    venue: str = ""
    city: str = ""
    canton: str = ""

    is_free: Optional[bool] = None

    warnings: list[str] = field(default_factory=list)
