from app.ml.claim_rule import relief_claim

HEAD = "C. Relief sought by the complainant:\nThe complainant has sought following relief(s):\n"


def test_refund_and_delay_wording_in_the_relief_section():
    assert relief_claim(HEAD + "Direct the respondent to refund the entire amount with interest.") == "refund"
    assert (
        relief_claim(HEAD + "Direct the respondent to pay delayed possession charges at the prescribed rate.")
        == "delayed_possession"
    )


def test_first_relief_wins_when_both_are_claimed():
    both = HEAD + "i. Hand over possession of the unit. ii. In the alternative, refund the amount."
    assert relief_claim(both) == "delayed_possession"


def test_refund_outside_the_relief_section_is_ignored():
    boilerplate = "The promoter is liable to refund the amount or pay interest under section 18. " * 3
    assert relief_claim(boilerplate) is None
    far = HEAD + "Set aside the cancellation letter." + (" x" * 600) + " refund"
    assert relief_claim(far) is None


def test_table_introduction_is_not_a_relief_section():
    intro = "total paid amount, and relief sought are given in the table below: Possession clause ... refund"
    assert relief_claim(intro) is None
