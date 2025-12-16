from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class CardDetection:
    rank: str
    suit: str
    confidence: float

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class ScanEvent:
    detection: Optional[CardDetection]
    source: str
    success: bool
    message: str

    def to_json(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "source": self.source,
            "detection": (
                self.detection.to_json() if self.detection else None
            )
        }
