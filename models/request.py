from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ProofreadMode(str, Enum):
	AUTO = "auto"
	FORCE = "force"


class ProofreadTone(str, Enum):
	CASUAL = "casual"
	FORMAL = "formal"


class ProofreadProvider(str, Enum):
	GEMINI = "gemini"
	OPENAI = "openai"


class ProofreadRequest(BaseModel):
	text: str = Field(..., description="Raw LLM output to proofread")
	mode: ProofreadMode = Field(
		default=ProofreadMode.AUTO,
		description="auto = detect language first; force = always proofread",
	)
	tone: ProofreadTone = Field(
		default=ProofreadTone.CASUAL,
		description="Desired Korean register: casual or formal",
	)
	provider: ProofreadProvider = Field(
		default=ProofreadProvider.GEMINI,
		description="Which proofreading LLM to use",
	)
	return_diff: bool = Field(
		default=False,
		description="If true, return a list of changes made alongside corrected output",
	)
	context: str = Field(
		default="",
		description="Optional original user prompt for context",
	)
