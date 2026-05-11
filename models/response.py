from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class DiffItem(BaseModel):
	original: str = Field(..., description="Original Korean segment")
	corrected: str = Field(..., description="Corrected Korean segment")
	error_type: str = Field(..., description="Classification of the error")
	segment_index: int = Field(..., description="Index of the segment in the output")


class ProofreadResponse(BaseModel):
	corrected: str = Field(..., description="Full corrected output")
	was_modified: bool = Field(..., description="Whether any changes were made")
	korean_ratio: float = Field(
		default=0.0, description="Ratio of Korean characters in the input"
	)
	segments_proofread: int = Field(
		default=0, description="Number of segments sent to proofreader"
	)
	segments_skipped: int = Field(
		default=0, description="Number of segments skipped (non-Korean)"
	)
	provider_used: str = Field(
		default="", description="Which provider was actually used"
	)
	latency_ms: int = Field(
		default=0, description="Total processing latency in milliseconds"
	)
	diff: Optional[list[DiffItem]] = Field(
		default=None, description="List of changes made (if return_diff was true)"
	)
