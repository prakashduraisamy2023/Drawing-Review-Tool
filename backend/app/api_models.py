"""HTTP response contracts for drawing resources."""

from pydantic import BaseModel, ConfigDict

from backend.app.models.drawing import DrawingDocument


class DrawingUploadResponse(BaseModel):
    id: str
    drawing: DrawingDocument

    model_config = ConfigDict(extra="forbid")
