import requests
from typing import Optional
from models import CardDetection

class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def send_card(self, detection: CardDetection) -> Optional[dict]:
        """
        Sends a detected card to the backend.
        Returns backend response as dict, or None on failure.
        """
        try:
            response = requests.post(
                f"{self.base_url}/card",
                json={
                    "rank": detection.rank,
                    "suit": detection.suit,
                },
                timeout=3
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"[Middleware] Backend communication error: {e}")
            return None
