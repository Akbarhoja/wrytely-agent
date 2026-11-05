"""One-course supervisor decisions. None grant drafting or channel authority."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PreparationExcerpt(BaseModel):
    """An original excerpt to review or act on personally, never generated coursework."""

    model_config = ConfigDict(extra="forbid")
    object_id: str = Field(min_length=36, max_length=36)
    quote: str = Field(min_length=10, max_length=1500)
    kind: Literal["review", "student_action"]


class CoursePreparation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    excerpts: list[PreparationExcerpt] = Field(min_length=1, max_length=8)
    questions: list[Annotated[str, Field(min_length=1, max_length=500)]] = Field(max_length=5)

    @model_validator(mode="after")
    def bounded_questions(self):
        if any(not q.strip() or len(q) > 500 for q in self.questions):
            raise ValueError("Preparation questions must be bounded and nonblank")
        return self


class CourseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["inspect", "offer", "wait", "prepare"]
    reason: str = Field(min_length=1, max_length=2000)
    object_id: str = Field(
        max_length=36,
        description=(
            "For inspect/offer/prepare copy the exact object_id UUID from sources, "
            "never a Canvas ID. "
            "Empty string for wait."
        ),
    )
    first_slot: int = Field(
        ge=0,
        le=512,
        description=(
            "Zero for wait, offer and inline inspection. "
            "Only document inspection may use a section offset."
        ),
    )
    message: str = Field(
        max_length=2000,
        description=(
            "Student-facing offer text only for action=offer. Empty string for inspect/wait. "
            "Also empty for prepare. "
            "Put internal explanations in reason."
        ),
    )
    next_check_seconds: int = Field(ge=60, le=86400)
    preparation: CoursePreparation | None = None

    @model_validator(mode="after")
    def coherent(self):
        from uuid import UUID

        if not self.reason.strip():
            raise ValueError("Reason required")
        if (self.action == "prepare") != (self.preparation is not None):
            raise ValueError("Preparation belongs only to prepare")
        if self.action == "wait":
            if self.object_id or self.message or self.first_slot:
                raise ValueError("Wait has no target")
        else:
            UUID(self.object_id)
            if self.action == "offer" and (not self.message.strip() or self.first_slot):
                raise ValueError("Offer requires a message and no section offset")
            if self.action == "inspect" and self.message:
                raise ValueError("Inspection cannot send a message")
            if self.action == "prepare" and (self.message or self.first_slot):
                raise ValueError("Preparation has no message or section offset")
        return self
