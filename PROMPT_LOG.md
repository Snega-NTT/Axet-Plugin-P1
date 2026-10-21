# Prompt log

## Codebase explanation

**Prompt:** Review the public functions and propose docstrings and type hints.

**AI suggestion:** The initial proposal said `total_payment` did not need to document `ValueError` because it did not raise the exception directly.

**My review and correction:** This was incomplete. `total_payment` calls `emi`, and `emi` raises `ValueError` for a non-positive principal or tenure. That exception can propagate to callers of `total_payment`, so I updated the proposed documentation to mention it.

## Test design

**Prompt:** Propose pytest tests for loan calculations and edge cases.

**AI suggestion:** The test plan initially used a 1% relative tolerance when checking that total schedule principal matched the original principal.

**My review and correction:** A 1% tolerance would allow an error of ₹10,000 on a ₹10,00,000 loan and could hide the missing final schedule row. I changed this to `pytest.approx(principal, abs=1.0)` so the test exposed the schedule off-by-one bug.

## Bug diagnosis

**Prompt:** Diagnose the oversized-prepayment test failure.

**AI diagnosis reviewed:** The AI correctly identified that the full prepayment amount was included in total repayment even when it exceeded the remaining balance.

**Decision:** I capped the effective prepayment at the outstanding balance and used the capped value in both the remaining-balance and total-repayment calculations.
