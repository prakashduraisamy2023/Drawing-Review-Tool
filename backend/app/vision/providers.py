"""Future trainable object-detection provider boundary.

No trainable model is bundled or invoked by the Level-3 PoC.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.vision.models import VisualObject
from backend.app.vision.page_renderer import RenderedPage


class ObjectDetectionProvider(ABC):
    name: str
    model_version: str

    @abstractmethod
    def detect(self, page: RenderedPage) -> list[VisualObject]:
        raise NotImplementedError
