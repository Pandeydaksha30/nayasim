"""Follow-up questions, chosen by plain rules from what the verified facts leave open.

No model is involved: each question has a fixed wording, a reason shown to the buyer, fixed
answer options, and a rule saying when it applies. Answers are stored in case_answers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

Facts = dict[str, list[str]]  # fact key -> values (payments can repeat)


@dataclass(frozen=True)
class Question:
    id: str
    question: str
    why: str
    options: tuple[str, ...]
    applies: Callable[[Facts], bool]


QUESTIONS: tuple[Question, ...] = (
    Question(
        "agreement_missing",
        "We could not find the promised possession date. Do you have the builder-buyer agreement?",
        "The promised date is the starting point for every delay calculation.",
        ("I will upload it", "I do not have it"),
        lambda f: "possession_promised" not in f,
    ),
    Question(
        "offer_of_possession",
        "Have you received a written offer of possession?",
        "If an offer was made, delay interest usually stops at that date, not today.",
        ("No", "Yes, with an occupancy certificate", "Yes, without an occupancy certificate"),
        lambda f: "offer_of_possession_date" not in f,
    ),
    Question(
        "payments_complete",
        "Are the payments listed here all the payments you made to the builder?",
        "Interest is worked out payment by payment; a missing receipt lowers the amount.",
        ("Yes, that is all", "No, some are missing"),
        lambda f: "payment" in f,
    ),
    Question(
        "payments_missing",
        "We found no payment receipts. Do you have receipts or bank statement entries?",
        "Without proof of payment no interest or refund can be calculated.",
        ("I will upload them", "I do not have them"),
        lambda f: "payment" not in f,
    ),
    Question(
        "missed_instalments",
        "Did you miss or pay late any instalment the builder demanded?",
        "Builders often argue the buyer defaulted first; late payments can reduce the award.",
        ("No, all paid on time", "Yes, one or more were late", "Not sure"),
        lambda f: True,
    ),
    Question(
        "relief",
        "Do you want to keep the flat, or withdraw and take a refund?",
        "This decides the relief: interest for every month of delay, or a refund with interest.",
        ("Keep the flat and claim delay interest", "Withdraw and claim a refund", "Undecided: show both"),
        lambda f: True,
    ),
    Question(
        "escalation_paid",
        "Have you paid the extra charge the builder demanded?",
        "Paying without protest can be read as accepting the builder's new terms.",
        ("No", "Yes, under protest in writing", "Yes, without protest"),
        lambda f: "escalation_demand" in f,
    ),
)

BY_ID = {q.id: q for q in QUESTIONS}


def questions_for(facts: Facts) -> list[Question]:
    return [q for q in QUESTIONS if q.applies(facts)]


def validate_answer(question_id: str, answer: str) -> None:
    q = BY_ID.get(question_id)
    if q is None:
        raise KeyError(f"Unknown question {question_id!r}.")
    if answer not in q.options:
        raise ValueError(f"Answer must be one of: {', '.join(q.options)}")
