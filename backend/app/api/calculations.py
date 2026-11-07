"""HTTP layer for the calculator. Validates input, calls the pure functions, returns
money as strings so no precision is lost to JSON floats."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.calculator.interest import (
    CalculationError,
    InterestResult,
    Payment,
    add_months,
    delay_interest,
    refund_with_interest,
)

router = APIRouter(prefix="/api/v1/calculations", tags=["calculations"])

Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


class PaymentIn(BaseModel):
    paid_on: date
    amount: Money
    reference: str = ""


class InterestRequest(BaseModel):
    payments: list[PaymentIn] = Field(min_length=1, max_length=200)
    possession_promised: date
    extension_months: int = Field(0, ge=0, le=60)
    annual_rate_pct: Annotated[Decimal, Field(ge=0, le=50, max_digits=6, decimal_places=3)]
    as_of: date
    # Where the rate comes from (rule, circular, date). Echoed back so the figure is never shown unsourced.
    rate_source: str = Field("", max_length=500)


class RowOut(BaseModel):
    paid_on: date
    amount: str
    reference: str
    interest_from: date
    days: int
    interest: str


class ResultOut(BaseModel):
    rows: list[RowOut]
    principal: str
    interest: str
    total: str


class InterestResponse(BaseModel):
    possession_due: date
    annual_rate_pct: str
    rate_source: str
    method: str
    delay: ResultOut
    refund: ResultOut


def _out(result: InterestResult) -> ResultOut:
    return ResultOut(
        rows=[
            RowOut(
                paid_on=r.payment.paid_on,
                amount=str(r.payment.amount),
                reference=r.payment.reference,
                interest_from=r.interest_from,
                days=r.days,
                interest=str(r.interest),
            )
            for r in result.rows
        ],
        principal=str(result.principal),
        interest=str(result.interest),
        total=str(result.total),
    )


@router.post("/interest", response_model=InterestResponse)
def calculate_interest(req: InterestRequest) -> InterestResponse:
    payments = [Payment(p.paid_on, p.amount, p.reference) for p in req.payments]
    try:
        due = add_months(req.possession_promised, req.extension_months)
        delay = delay_interest(payments, due, req.as_of, req.annual_rate_pct)
        refund = refund_with_interest(payments, req.as_of, req.annual_rate_pct)
    except CalculationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return InterestResponse(
        possession_due=due,
        annual_rate_pct=str(req.annual_rate_pct),
        rate_source=req.rate_source,
        method="Simple interest per payment, 365-day year, each row rounded half-up to the paisa.",
        delay=_out(delay),
        refund=_out(refund),
    )
