"""Key-page selection for extraction."""

from app.extraction.page_select import FIRST, LAST, select_pages

FILLER = "The counsel relied on several judgments of the Hon'ble Supreme Court. " * 20


def order(n_pages: int, extra: dict[int, str] | None = None) -> dict[int, str]:
    pages = {i: f"Page {i}. {FILLER}" for i in range(1, n_pages + 1)}
    pages.update(extra or {})
    return pages


def test_short_order_is_sent_whole():
    pages = order(5)
    assert select_pages(pages) == pages


def test_long_order_sends_first_and_last_pages():
    chosen = select_pages(order(30))
    assert list(chosen) == [1, 2, 3, 28, 29, 30]
    assert FIRST == 3 and LAST == 3


def test_middle_pages_with_key_terms_are_added_by_score():
    pages = order(
        30,
        {
            14: "Amount paid by the complainant: Rs. 40,00,000. Due date of possession 01.01.2020. " + FILLER,
            17: "Interest at the prescribed rate i.e. 10.85% per annum. " + FILLER,
            20: "Only the word refund appears here. " + FILLER,
        },
    )
    chosen = select_pages(pages)
    assert {14, 17, 20} <= set(chosen)
    assert 10 not in chosen  # no key terms
    assert list(chosen) == sorted(chosen)


def test_budget_limits_extra_pages_but_never_cuts_a_page():
    pages = order(30, {i: "prescribed rate 10.85% " + FILLER for i in range(5, 26)})
    chosen = select_pages(pages, max_chars=12_000)
    assert {1, 2, 3, 28, 29, 30} <= set(chosen)
    extras = set(chosen) - {1, 2, 3, 28, 29, 30}
    assert 0 < len(extras) < 21
    assert all(chosen[n] == pages[n] for n in chosen)  # whole pages only


def test_empty_order():
    assert select_pages({}) == {}
