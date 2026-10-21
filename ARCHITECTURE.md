# ARCHITECTURE.md

This document describes the current implementation of the `loan-calc` codebase, based on the current contents of `cli.py`, `loan_calc/__init__.py`, `loan_calc/calculator.py`, and `tests/test_calculator.py`.

## 1. Purpose

`loan-calc` is a small Python library and CLI for retail loan calculations. It provides:

- EMI (Equated Monthly Instalment) computation
- Total payment and total interest calculation
- Month-by-month amortisation schedules
- Outstanding balance lookup after a given number of months
- Remaining-tenure calculation given a balance and instalment
- Prepayment savings estimation
- Comparison of multiple loan offers
- Loan eligibility estimation based on income and FOIR
- INR currency formatting
- CSV export of an amortisation schedule
- A human-readable loan summary

## 2. Main modules

| File | Role |
|---|---|
| `loan_calc/calculator.py` | Contains all business logic: rate conversion, EMI, amortisation schedule, outstanding balance, remaining tenure, prepayment savings, offer comparison, eligibility, INR formatting, CSV export, and summary. |
| `loan_calc/__init__.py` | Re-exports everything from `calculator.py` via `from .calculator import *`, so functions are accessible as `loan_calc.emi`, `loan_calc.amortisation_schedule`, etc. |
| `cli.py` | Command-line entry point. Parses `principal`, `rate`, `tenure`, and optional `--schedule`, `--prepay-month`, `--prepay-amount` flags, then prints a `summary()`, optionally an `amortisation_schedule()`, and optionally a `prepayment_savings()` result. |
| `tests/test_calculator.py` | A pytest suite covering EMI calculations, amortisation schedule behavior, outstanding balance, remaining tenure, prepayment savings (including an oversized-prepayment case), offer comparison, eligibility, currency formatting, CSV export, and the loan summary. |

## 3. Core calculation flow

- **Rate conversion:** An annual percentage rate is converted to a monthly decimal rate with `annual_rate / 1200` (this combines dividing by 100 to convert percent to decimal, and dividing by 12 to convert annual to monthly).
- **EMI:** Computed using the standard reducing-balance formula `EMI = P * r * (1+r)^n / ((1+r)^n - 1)`, where `r` is the monthly rate and `n` is the tenure in months. When the monthly rate is `0` (e.g. a 0% annual rate), the EMI is simply `principal / tenure_months`.
- **Amortisation schedule:** Iterates once for every month from `1` to `tenure_months` inclusive, producing exactly one row per repayment month. On the final month, the principal portion is set equal to the remaining balance (rather than the regular instalment-minus-interest calculation), so the balance is cleared to zero on the last row.
- **Outstanding balance / prepayment / eligibility:** These build on top of `emi` and `amortisation_schedule`, reusing the same rate-conversion and EMI logic.

## 4. Public functions

All functions below are defined in `loan_calc/calculator.py`. The internal helper `_monthly_rate` is not part of the public API and is not listed here.

- **`emi(principal, annual_rate, tenure_months)`** — Computes the fixed monthly instalment for a loan, with a simple division fallback at 0% interest.
- **`total_payment(principal, annual_rate, tenure_months)`** — Computes the total amount repaid over the full tenure (EMI × tenure_months).
- **`total_interest(principal, annual_rate, tenure_months)`** — Computes total interest paid (total payment minus principal).
- **`amortisation_schedule(principal, annual_rate, tenure_months)`** — Builds a month-by-month breakdown (month, EMI, interest, principal, balance), with one row per month and the final balance cleared to zero.
- **`outstanding_after(principal, annual_rate, tenure_months, months_paid)`** — Returns the outstanding balance after a given number of months paid, based on the amortisation schedule.
- **`remaining_tenure(balance, annual_rate, instalment)`** — Computes how many more months are needed to repay a balance at a fixed instalment, using the same monthly rate convention as `emi`.
- **`prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount)`** — Estimates the effect of a lump-sum prepayment on tenure and interest while keeping the EMI unchanged.
- **`compare_offers(principal, offers)`** — Compares a list of loan offers (each with bank, rate, tenure, and optional processing fee) and ranks them by total cost.
- **`eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5)`** — Estimates the maximum loan principal a borrower is eligible for, based on available monthly repayment capacity.
- **`format_inr(amount)`** — Formats a numeric amount as an Indian-style currency string (₹, lakh/crore grouping, 2 decimal places).
- **`schedule_to_csv(rows, path)`** — Writes an amortisation schedule to a CSV file.
- **`summary(principal, annual_rate, tenure_months, start=None)`** — Produces a human-readable summary dict of a loan, including formatted EMI, total interest, total payment, and the final instalment's year-month.

## 5. Prepayment behavior

- A normal prepayment (less than or equal to the outstanding balance at the prepayment month) keeps the EMI unchanged and calculates a shortened remaining tenure based on the reduced balance.
- If the supplied prepayment amount is greater than the outstanding balance at the prepayment month, the effective amount applied to the loan is capped at that outstanding balance. The loan is treated as fully settled at the prepayment month, and the capped amount (not the raw, larger supplied amount) is used in the remaining-balance and total-repayment calculations.
- `prepay_month` and `prepay_amount` are not independently validated for range or sign; a `prepay_month` outside the generated schedule's range, or a non-positive `prepay_amount`, is not explicitly checked and may raise an `IndexError` rather than a descriptive validation error.

## 6. Assumptions and current limitations

- Monetary values are represented as Python `float`s and are rounded (typically to 2 decimal places) at the relevant calculation or output points.
- `emi` checks that `principal` and `tenure_months` are both positive and raises `ValueError` if not; this validation is relied upon by every other function that calls `emi` internally.
- Broader input validation — such as rejecting a negative `annual_rate`, validating that `prepay_month` falls within the loan's tenure, or validating offer dictionaries passed to `compare_offers` — is not currently implemented.
- `compare_offers` expects each offer dictionary to contain `"bank"`, `"rate"`, and `"tenure"` keys; a missing key will raise a `KeyError` rather than a descriptive error.

## 7. Test coverage

The pytest suite in `tests/test_calculator.py` covers:

- Standard EMI calculations, including a 0% interest case, a one-month tenure, and a very large principal.
- Existing `ValueError` behavior for non-positive principal and tenure.
- Amortisation schedule row count, required row fields, monotonically decreasing balance, a zero final balance, total principal reconciliation, and zero-interest behavior.
- Outstanding balance before any payments, after partial payments, at the full tenure, and beyond the full tenure.
- Remaining-tenure calculation for a normal scenario, a zero balance, zero interest, and an instalment too small to repay the loan.
- Prepayment savings for a normal scenario and for a prepayment larger than the outstanding balance.
- Offer comparison sorting by total cost.
- Eligible-amount calculation, including the no-capacity and zero-interest cases.
- INR currency formatting for normal, lakh/crore-grouped, and negative amounts.
- CSV export of an amortisation schedule.
- The loan summary's formatted output fields.
