"""Typed messages passed between agents. Every hand-off is one of these models."""

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["available", "taken", "unknown"]


class Candidate(BaseModel):
    domain: str = Field(description="Full domain in lowercase, for example 'brewly.com'.")
    guideline: str = Field(description="Which naming guideline this name follows.")
    reasoning: str = Field(description="One sentence on why the name fits the business.")


class CandidateList(BaseModel):
    """Output of the naming agent."""

    candidates: list[Candidate]


class Quote(BaseModel):
    """One provider's answer for one domain."""

    domain: str
    provider: str
    status: Status
    price: float | None = Field(default=None, description="First-year registration price.")
    renewal_price: float | None = None
    currency: str = "USD"
    premium: bool | None = None
    note: str = ""


class ProviderReport(BaseModel):
    """Output of a provider agent, sent back over A2A."""

    provider: str
    quotes: list[Quote]


class Verdict(BaseModel):
    domain: str
    keep: bool = Field(description="False if the domain should not be on the final list.")
    reason: str = Field(description="One sentence explaining the decision.")
    flags: list[str] = Field(default_factory=list, description="Warnings the buyer should see.")


class VerdictList(BaseModel):
    """Output of the judge. It decides and explains; it never restates prices."""

    verdicts: list[Verdict]


class RankedDomain(BaseModel):
    domain: str
    provider: str | None
    price: float | None
    renewal_price: float | None
    currency: str
    other_prices: dict[str, float]
    name_reasoning: str
    judge_reason: str
    flags: list[str]


class DroppedDomain(BaseModel):
    domain: str
    reason: str


class FinalList(BaseModel):
    """Final result: purchasable domains ordered by price, cheapest first."""

    ranked: list[RankedDomain]
    dropped: list[DroppedDomain]
