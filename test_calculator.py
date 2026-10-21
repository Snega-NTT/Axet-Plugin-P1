import math
from datetime import date

import pytest

from loan_calc.calculator import (
    emi,
    total_payment,
    total_interest,
    amortisation_schedule,
    outstanding_after,
    remaining_tenure,
    prepayment_savings,
    compare_offers,
    eligible_amount,
    format_inr,
    schedule_to_csv,
    summary,
)


# ---------------------------------------------------------------------------
# 1. EMI
# ---------------------------------------------------------------------------

def test_emi_normal_loan_matches_known_value():
    """A 20-year, 9% loan of 1,000,000 should have an EMI close to 8,997."""
    assert emi(1_000_000, 9, 240) == pytest.approx(8997, abs=1)


def test_emi_zero_interest_equals_simple_division():
    """At 0% interest, EMI must equal principal divided by tenure_months."""
    assert emi(1_200_000, 0, 24) == pytest.approx(50_000.0, abs=0.01)


def test_emi_one_month_tenure_equals_principal_plus_one_month_interest():
    """A 1-month loan should repay principal plus exactly one month's interest."""
    assert emi(100_000, 12, 1) == pytest.approx(101_000.0, abs=0.5)


def test_emi_very_large_principal_does_not_overflow():
    """EMI for a very large principal must remain finite and sensible."""
    result = emi(1_000_000_000_000, 8.5, 360)
    assert math.isfinite(result)
    assert result * 360 > 1_000_000_000_000


def test_emi_zero_principal_raises_value_error():
    with pytest.raises(ValueError):
        emi(0, 9, 12)


def test_emi_negative_principal_raises_value_error():
    with pytest.raises(ValueError):
        emi(-500, 9, 12)


def test_emi_zero_tenure_raises_value_error():
    with pytest.raises(ValueError):
        emi(100_000, 9, 0)


def test_emi_negative_tenure_raises_value_error():
    with pytest.raises(ValueError):
        emi(100_000, 9, -5)


def test_emi_precision_with_non_round_rate():
    """EXPECTED TO FAIL — EXPOSES DEFECT.

    The expected EMI is computed independently here using the full,
    unrounded monthly rate (annual_rate / 1200), without calling any
    production rounding helper. This exposes the precision loss caused
    by _monthly_rate's 4-decimal rounding.
    """
    principal = 500_000
    annual_rate = 8.75
    tenure_months = 120
    r_exact = annual_rate / 1200
    f = (1 + r_exact) ** tenure_months
    expected = round(principal * r_exact * f / (f - 1), 2)

    assert emi(principal, annual_rate, tenure_months) == pytest.approx(expected, abs=0.01)


# ---------------------------------------------------------------------------
# 2. Amortisation schedule
# ---------------------------------------------------------------------------

def test_amortisation_schedule_row_count_equals_tenure():
    """EXPECTED TO FAIL — EXPOSES DEFECT.

    A 240-month loan must produce exactly 240 schedule rows (one per
    repayment month).
    """
    rows = amortisation_schedule(1_000_000, 9, 240)
    assert len(rows) == 240


def test_amortisation_schedule_one_month_tenure_produces_one_row():
    """EXPECTED TO FAIL — EXPOSES DEFECT.

    A 1-month loan should still produce exactly one schedule row.
    """
    rows = amortisation_schedule(50_000, 10, 1)
    assert len(rows) == 1


def test_amortisation_schedule_rows_have_required_keys():
    rows = amortisation_schedule(500_000, 8, 60)
    for row in rows:
        assert set(row.keys()) == {"month", "emi", "interest", "principal", "balance"}


def test_amortisation_schedule_balance_decreases_monotonically():
    rows = amortisation_schedule(500_000, 8, 60)
    for i in range(len(rows) - 1):
        assert rows[i + 1]["balance"] <= rows[i]["balance"]


def test_amortisation_schedule_final_balance_is_approximately_zero():
    """EXPECTED TO FAIL — EXPOSES DEFECT.

    The final row of a fully amortising loan's schedule should show an
    outstanding balance of (approximately) zero.
    """
    rows = amortisation_schedule(1_000_000, 9, 240)
    assert rows[-1]["balance"] == pytest.approx(0.0, abs=1.0)


def test_amortisation_schedule_total_principal_repaid_equals_principal():
    """EXPECTED TO FAIL — EXPOSES DEFECT.

    The sum of all principal portions across the schedule must
    reconstruct the original loan amount to within a currency-unit
    tolerance.
    """
    rows = amortisation_schedule(1_000_000, 9, 240)
    total_principal = sum(row["principal"] for row in rows)
    assert total_principal == pytest.approx(1_000_000, abs=1.0)


def test_amortisation_schedule_zero_interest_has_no_interest_portion():
    rows = amortisation_schedule(1_200_000, 0, 24)
    for row in rows:
        assert row["interest"] == 0.0


# ---------------------------------------------------------------------------
# 3. Outstanding balance
# ---------------------------------------------------------------------------

def test_outstanding_after_zero_months_paid_equals_principal():
    assert outstanding_after(500_000, 10, 36, 0) == pytest.approx(500_000, abs=0.01)


def test_outstanding_after_some_months_paid_matches_schedule_balance():
    sched = amortisation_schedule(500_000, 10, 36)
    assert outstanding_after(500_000, 10, 36, 12) == sched[11]["balance"]


def test_outstanding_after_full_tenure_returns_zero():
    """Basic public-behavior check only.

    This does NOT prove amortisation is correct. The amortisation
    schedule is one row short of the full tenure (see the schedule
    row-count/final-balance/total-principal tests above, which are the
    authoritative tests for amortisation correctness). This test only
    confirms outstanding_after's own documented contract: once
    months_paid reaches tenure_months, it returns 0.0.
    """
    assert outstanding_after(500_000, 10, 36, 36) == 0.0


def test_outstanding_after_more_than_full_tenure_returns_zero():
    assert outstanding_after(500_000, 10, 36, 50) == 0.0


# ---------------------------------------------------------------------------
# 4. Remaining tenure
# ---------------------------------------------------------------------------

def test_remaining_tenure_normal_scenario():
    """SUSPECTED-DEFECT TEST.

    Expected result of 11 is derived independently: the annual rate of
    12% corresponds to a monthly rate of 12 / 1200 = 0.01. Using the
    repayment-period formula with r = 0.01 gives n ~= 10.59, which
    rounds up to 11. This value is hard-coded here, not derived by
    calling any production rate-conversion helper.
    """
    assert remaining_tenure(100_000, 12, 10_000) == 11


def test_remaining_tenure_zero_balance_returns_zero():
    assert remaining_tenure(0, 12, 10_000) == 0


def test_remaining_tenure_zero_interest_uses_simple_division():
    assert remaining_tenure(50_000, 0, 10_000) == 5


def test_remaining_tenure_instalment_too_small_raises_value_error():
    """Existing documented behavior: if the instalment does not even
    cover the computed interest on the balance, a ValueError is raised.
    """
    with pytest.raises(ValueError):
        remaining_tenure(100_000, 12, 100)


# ---------------------------------------------------------------------------
# 5. Prepayment savings
# ---------------------------------------------------------------------------

def test_prepayment_savings_normal_scenario():
    instalment = emi(1_000_000, 9, 240)
    sched = amortisation_schedule(1_000_000, 9, 240)
    balance_before = sched[23]["balance"]
    prepay_amount = 50_000
    result = prepayment_savings(1_000_000, 9, 240, 24, prepay_amount)

    assert result["emi"] == pytest.approx(instalment, abs=0.01)
    assert result["new_tenure"] < 240
    assert result["months_saved"] > 0
    assert result["interest_paid_before_prepayment"] >= 0
    # sanity: balance before prepayment must exceed the prepayment amount
    assert balance_before > prepay_amount


def test_prepayment_savings_oversized_prepayment_ends_loan_at_prepay_month():
    """An overpayment greater than the outstanding balance should only
    settle the remaining balance -- it must not create a negative loan
    balance, a negative tenure, or be treated as extra valid loan
    payments beyond what is owed.
    """
    result = prepayment_savings(100_000, 12, 12, 1, 1_000_000)

    assert result["new_tenure"] == 1
    assert result["months_saved"] == 11
    assert result["interest_saved"] >= 0


# ---------------------------------------------------------------------------
# 6. compare_offers
# ---------------------------------------------------------------------------

def test_compare_offers_sorted_by_ascending_total_cost():
    offers = [
        {"bank": "A", "rate": 10, "tenure": 24, "processing_fee_pct": 1},
        {"bank": "B", "rate": 9, "tenure": 24, "processing_fee_pct": 0.5},
    ]
    result = compare_offers(500_000, offers)

    assert [r["bank"] for r in result] == ["B", "A"]
    assert result[0]["total_cost"] <= result[1]["total_cost"]


# ---------------------------------------------------------------------------
# 7. eligible_amount
# ---------------------------------------------------------------------------

def test_eligible_amount_no_repayment_capacity_returns_zero():
    # monthly_income * foir - existing_emis <= 0
    assert eligible_amount(20_000, 20_000, 10, 60) == 0.0


def test_eligible_amount_zero_interest_uses_simple_multiplication():
    # available = 50_000*0.5 - 10_000 = 15_000
    assert eligible_amount(50_000, 10_000, 0, 24) == pytest.approx(15_000 * 24, abs=0.01)


# ---------------------------------------------------------------------------
# 8. format_inr
# ---------------------------------------------------------------------------

def test_format_inr_normal_amount():
    assert format_inr(1234.5) == "₹1,234.50"


def test_format_inr_lakh_crore_grouping():
    assert format_inr(1234567.89) == "₹12,34,567.89"


def test_format_inr_negative_amount():
    assert format_inr(-1234567.89) == "-₹12,34,567.89"


# ---------------------------------------------------------------------------
# 9. schedule_to_csv
# ---------------------------------------------------------------------------

def test_schedule_to_csv_writes_header_and_rows(tmp_path):
    rows = amortisation_schedule(100_000, 10, 12)
    csv_path = tmp_path / "schedule.csv"

    schedule_to_csv(rows, csv_path)

    content = csv_path.read_text()
    lines = content.strip().split("\n")

    assert lines[0] == "month,emi,interest,principal,balance"
    assert len(lines) == 1 + len(rows)

    first_data_line = lines[1].split(",")
    assert first_data_line[0] == str(rows[0]["month"])
    assert first_data_line[1] == str(rows[0]["emi"])
    assert first_data_line[2] == str(rows[0]["interest"])
    assert first_data_line[3] == str(rows[0]["principal"])
    assert first_data_line[4] == str(rows[0]["balance"])


# ---------------------------------------------------------------------------
# 10. summary
# ---------------------------------------------------------------------------

def test_summary_returns_expected_formatted_values():
    fixed_start = date(2024, 1, 15)
    result = summary(1_000_000, 9, 240, start=fixed_start)

    assert result["principal"] == "₹10,00,000.00"
    assert result["rate"] == "9% p.a."
    assert result["tenure"] == "240 months"
    assert result["emi"] == format_inr(emi(1_000_000, 9, 240))
    assert result["currency"] == "INR"
    assert result["last_emi"] == "2044-01"
