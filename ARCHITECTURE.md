# ARCHITECTURE.md

This document describes the current state of the `loan-calc` codebase as found in this workspace. Every statement below is based on direct inspection of `cli.py`, `loan_calc/__init__.py`, and `loan_calc/calculator.py`. No behavior, function, or assumption has been invented. Where something is uncertain or looks like a bug, it is explicitly flagged as such rather than stated as confirmed fact.

## 1. Purpose

`loan-calc` is a small Python library and CLI for retail loan calculations. Based on the public functions present in `loan_calc/calculator.py`, it supports:

- EMI (Equated Monthly Instalment) computation
- Month-by-month amortisation schedules
- Outstanding balance lookup after N months
- Remaining-tenure calculation given a balance and instalment
- Prepayment savings estimation
- Comparison of multiple loan offers
- Loan eligibility estimation based on income/FOIR
- INR currency formatting
- CSV export of a schedule
- A human-readable summary combining several of the above

The README states the module "has no tests and no documentation" and that "users report that some numbers are wrong," which is consistent with the inconsistencies identified in Section 8.

## 2. Main modules and responsibilities

| File | Responsibility |
|---|---|
| `cli.py` | Command-line entry point. Uses `argparse` to accept `principal`, `rate`, `tenure`, and optional `--schedule`, `--prepay-month`, `--prepay-amount` flags. Calls `summary()`, optionally `amortisation_schedule()`, and optionally `prepayment_savings()`, printing results as JSON/dicts. |
| `loan_calc/__init__.py` | Contains only `from .calculator import *`. Re-exports every public (non-underscore-prefixed) name defined in `calculator.py` as part of the `loan_calc` package namespace. |
| `loan_calc/calculator.py` | Contains all business logic for the package: rate conversion, EMI, amortisation schedule, outstanding balance, remaining tenure, prepayment savings, offer comparison, eligibility, INR formatting, CSV export, and summary. This is the sole source of calculation logic in the project. |
| `tests/` | Empty except for a `.gitkeep` placeholder. No automated tests currently exist. |
| `requirements.txt` | Lists only `pytest>=8.0` and `pytest-cov>=5.0` — test-time dependencies. The runtime code uses only Python standard library modules (`math`, `datetime`, `argparse`, `json`). |

## 3. Public functions

All functions below are defined in `loan_calc/calculator.py`. `_monthly_rate` is prefixed with an underscore (private/internal) but is documented here because it is used by several public functions and directly affects their correctness.

### `_monthly_rate(annual_rate)` *(internal helper)*
- **Purpose:** Converts an annual interest rate expressed as a percentage into a monthly decimal rate.
- **Input:** `annual_rate` — numeric, annual rate as a percentage (e.g. `9` means 9%).
- **Output:** `float` — monthly decimal rate, rounded to 4 decimal places.
- **Behavior:** `round(annual_rate / 1200, 4)`. Division by 1200 combines "percent to decimal" (÷100) and "annual to monthly" (÷12).
- **Used by:** `emi`, `amortisation_schedule`, `eligible_amount`.

### `emi(principal, annual_rate, tenure_months)`
- **Purpose:** Computes the fixed monthly instalment for a loan.
- **Input:** `principal` (numeric, expected > 0), `annual_rate` (numeric, percentage), `tenure_months` (int, expected > 0).
- **Output:** `float`, EMI rounded to 2 decimal places.
- **Behavior:** Raises `ValueError` if `tenure_months <= 0` or `principal <= 0`. Computes `r = _monthly_rate(annual_rate)`. If `r == 0`, returns `principal / tenure_months` (simple division, confirmed 0%-interest handling). Otherwise computes the standard reducing-balance EMI formula: `EMI = P * r * (1+r)^n / ((1+r)^n - 1)`.
- **Calls:** `_monthly_rate`.
- **Called by:** `total_payment`, `amortisation_schedule`, `prepayment_savings`, `compare_offers`, `summary`.
- **Note:** `annual_rate` is not validated; a negative value is not rejected.

### `total_payment(principal, annual_rate, tenure_months)`
- **Purpose:** Computes the total amount paid across the full tenure.
- **Input:** same three core parameters as `emi`.
- **Output:** `float`, rounded to 2 decimals.
- **Behavior:** `round(emi(...) * tenure_months, 2)`.
- **Calls:** `emi`.
- **Called by:** `total_interest`, `summary`.

### `total_interest(principal, annual_rate, tenure_months)`
- **Purpose:** Computes total interest paid across the full tenure.
- **Output:** `float`, rounded to 2 decimals.
- **Behavior:** `round(total_payment(...) - principal, 2)`.
- **Calls:** `total_payment` → `emi`.
- **Called by:** `prepayment_savings`, `compare_offers`, `summary`.

### `amortisation_schedule(principal, annual_rate, tenure_months)`
- **Purpose:** Builds a month-by-month breakdown of the loan: EMI, interest portion, principal portion, and remaining balance.
- **Input:** same three core parameters.
- **Output:** `list[dict]`. Each dict has keys `month`, `emi`, `interest`, `principal`, `balance`.
- **Behavior:** Computes `r = _monthly_rate(annual_rate)` and the fixed `instalment = emi(...)`. Iterates `for month in range(1, tenure_months)`, computing `interest = round(balance * r, 2)` on the opening balance for that month, `principal_part = round(instalment - interest, 2)`, and updating `balance = round(balance - principal_part, 2)` (clamped to a minimum of `0.0` only in the stored row, not in the running `balance` variable used for the next iteration). There is an `if month == tenure_months:` branch intended to true-up the final instalment so the balance reaches exactly zero.
- **Calls:** `_monthly_rate`, `emi`.
- **Called by:** `outstanding_after`, `prepayment_savings`; also called directly from `cli.py` when `--schedule` is passed.
- **Confirmed behavior note:** See Section 6 and Section 8 — because `range(1, tenure_months)` is used (upper bound exclusive), the loop produces rows only for months `1` through `tenure_months - 1`. The `month == tenure_months` true-up branch can never execute, and the returned list has `tenure_months - 1` rows, not `tenure_months`.

### `outstanding_after(principal, annual_rate, tenure_months, months_paid)`
- **Purpose:** Returns the outstanding loan balance after a given number of EMIs have been paid.
- **Input:** core three params plus `months_paid` (int).
- **Output:** `float`.
- **Behavior:** If `months_paid <= 0`, returns `round(principal, 2)`. Otherwise builds the full schedule via `amortisation_schedule` and returns `sched[months_paid - 1]["balance"]`, unless `months_paid > len(sched)`, in which case it returns `0.0`.
- **Calls:** `amortisation_schedule`.
- **Note:** Because `len(sched) == tenure_months - 1` (see above), calling this with `months_paid == tenure_months` falls into the `> len(sched)` branch and returns `0.0` without ever computing a true-up value.

### `remaining_tenure(balance, annual_rate, instalment)`
- **Purpose:** Given an outstanding balance, an annual rate, and a fixed instalment amount, computes how many more months are needed to fully repay the balance.
- **Input:** `balance` (numeric), `annual_rate` (numeric, percentage), `instalment` (numeric).
- **Output:** `int` (ceiling of the computed month count). Returns `0` if `balance <= 0`.
- **Behavior:** Computes `r = annual_rate / 100` (note: this differs from the conversion used by `_monthly_rate`, which divides by 1200 — see Section 8). If `r == 0`, returns `ceil(balance / instalment)`. Raises `ValueError` if `instalment <= balance * r` (instalment does not even cover the computed interest, loan cannot amortize). Otherwise computes `n = -log(1 - balance*r/instalment) / log(1+r)` and returns `ceil(n)`.
- **Calls:** none internally (uses `math.log`, `math.ceil` only).
- **Called by:** `prepayment_savings`.

### `prepayment_savings(principal, annual_rate, tenure_months, prepay_month, prepay_amount)`
- **Purpose:** Estimates savings from making a lump-sum prepayment at a given month while keeping the EMI unchanged. Per its own docstring: "Keep the same EMI after a lump-sum prepayment and shorten the tenure."
- **Input:** core three params, plus `prepay_month` (int, month index of prepayment), `prepay_amount` (numeric).
- **Output:** `dict` with keys `emi`, `months_saved`, `new_tenure`, `interest_saved`, `interest_paid_before_prepayment`.
- **Behavior:** Computes `instalment = emi(...)` and `sched = amortisation_schedule(...)`. Reads `balance = sched[prepay_month - 1]["balance"]`. Computes `new_balance = balance - prepay_amount`. If `new_balance <= 0`, sets `months_left = 0`; otherwise calls `remaining_tenure(new_balance, annual_rate, instalment)`. Computes `original_left = tenure_months - prepay_month`, sums interest already paid via `sum(row["interest"] for row in sched[:prepay_month])`, computes `original_interest = total_interest(...)`, then `new_total = instalment * prepay_month + prepay_amount + instalment * months_left` and `new_interest = new_total - principal`, returning `interest_saved = original_interest - new_interest`.
- **Calls:** `emi`, `amortisation_schedule`, `remaining_tenure`, `total_interest`.
- **Called by:** `cli.py` when both `--prepay-month` and `--prepay-amount` are supplied.
- **Note:** No validation that `prepay_month` is within `[1, tenure_months]` or that `prepay_amount > 0`. A `prepay_month` of `0` would index `sched[-1]` (Python negative indexing), silently returning the last available row instead of raising an error.

### `compare_offers(principal, offers)`
- **Purpose:** Compares multiple loan offers and ranks them by total cost.
- **Input:** `principal` (numeric); `offers` — list of dicts, each expected to contain `bank`, `rate`, `tenure`, and optionally `processing_fee_pct`.
- **Output:** `list[dict]`, each with `bank`, `emi`, `total_interest`, `processing_fee`, `total_cost`, sorted ascending by `total_cost`.
- **Behavior:** For each offer, computes `e = emi(principal, o["rate"], o["tenure"])`, `ti = total_interest(...)`, `fee = o.get("processing_fee_pct", 0) * principal / 100`, `total_cost = ti + fee`. Sorts result list by `total_cost`.
- **Calls:** `emi`, `total_interest`.
- **Note:** No key validation; a missing `"bank"` or `"rate"` key in an offer dict will raise an unhandled `KeyError`.

### `eligible_amount(monthly_income, existing_emis, annual_rate, tenure_months, foir=0.5)`
- **Purpose:** Estimates the maximum loan principal a borrower is eligible for.
- **Input:** `monthly_income` (numeric), `existing_emis` (numeric), `annual_rate` (numeric, percentage), `tenure_months` (int), `foir` (float, default `0.5`).
- **Output:** `float`, eligible principal rounded to 2 decimals, or `0.0`.
- **Behavior:** `available = monthly_income * foir - existing_emis`. If `available <= 0`, returns `0.0`. Computes `r = _monthly_rate(annual_rate)`. If `r == 0`, returns `round(available * tenure_months, 2)`. Otherwise returns the present-value-of-annuity formula: `available * ((1+r)^n - 1) / (r * (1+r)^n)`.
- **Calls:** `_monthly_rate`.

### `format_inr(amount)`
- **Purpose:** Formats a numeric amount into Indian-style currency string with ₹ symbol and lakh/crore digit grouping.
- **Input:** `amount` (numeric, may be negative).
- **Output:** `str`, e.g. `₹10,00,000.00`.
- **Behavior:** Separates sign, rounds to 2 decimals, splits whole/fraction parts, groups the whole part's digits in the Indian numbering style (last 3 digits, then groups of 2).
- **Calls:** none internally.
- **Called by:** `summary`.

### `schedule_to_csv(rows, path)`
- **Purpose:** Writes an amortisation schedule to a CSV file.
- **Input:** `rows` (list of dicts as returned by `amortisation_schedule`), `path` (str, file path).
- **Output:** `None` (writes to disk).
- **Behavior:** Opens `path` for writing, writes a header line `month,emi,interest,principal,balance`, then one line per row.
- **Calls:** none internally. Not called elsewhere in the codebase (no caller found in `cli.py` or `calculator.py`); it is only used if a consumer of the library calls it directly.

### `summary(principal, annual_rate, tenure_months, start=None)`
- **Purpose:** Produces a human-readable summary dict of a loan.
- **Input:** `principal`, `annual_rate`, `tenure_months` (core params); `start` (optional `date`, defaults to `date.today()`).
- **Output:** `dict` with keys `principal`, `rate`, `tenure`, `emi`, `total_interest`, `total_payment`, `last_emi`, `currency` — all monetary values formatted via `format_inr`.
- **Behavior:** Computes `e = emi(...)`, derives `end_year`/`end_month` by adding `tenure_months` to `start`, and formats the loan details and amounts for display.
- **Calls:** `emi`, `total_interest`, `total_payment`, `format_inr`.
- **Called by:** `cli.py` (always printed first).

## 4. Calculation flow

Based on `cli.py`:

1. `cli.py` parses `principal` (float), `rate` (float, annual %), `tenure` (int, months) as positional args, plus optional flags `--schedule`, `--prepay-month`, `--prepay-amount`.
2. It always calls `summary(a.principal, a.rate, a.tenure)` and prints the result as JSON. `summary` internally calls `emi`, `total_interest`, `total_payment`, each of which (except `format_inr`) ultimately depends on `_monthly_rate` for interest-rate conversion.
3. If `--schedule` is passed, `cli.py` calls `amortisation_schedule(a.principal, a.rate, a.tenure)` directly and prints each row dict. This schedule, per Section 3/6, is missing its final row due to the `range(1, tenure_months)` loop bound.
4. If both `--prepay-month` and `--prepay-amount` are passed (truthy, i.e. non-zero), `cli.py` calls `prepayment_savings(a.principal, a.rate, a.tenure, a.prepay_month, a.prepay_amount)` and prints the resulting dict as JSON. This function internally calls `emi`, `amortisation_schedule`, `remaining_tenure`, and `total_interest`.
5. `compare_offers` and `eligible_amount` are not invoked anywhere in `cli.py`; they are library-only functions with no CLI exposure in the current codebase.

## 5. EMI calculation assumptions

- **Annual-to-monthly conversion (confirmed):** `_monthly_rate(annual_rate)` computes `round(annual_rate / 1200, 4)`. This is equivalent to `(annual_rate / 100) / 12`, i.e., percent-to-decimal divided by 12 months, with the result rounded to 4 decimal places.
- **Formula for an interest-bearing loan (confirmed):** `EMI = P * r * (1+r)^n / ((1+r)^n - 1)`, the standard reducing-balance EMI formula, where `r` is the monthly rate from `_monthly_rate` and `n = tenure_months`.
- **0% interest handling (confirmed):** When `r == 0`, `emi()` returns `principal / tenure_months` exactly (simple division, no interest), rounded to 2 decimals.
- **Verification for principal = 1,000,000, annual_rate = 9, tenure_months = 240 (confirmed by manual calculation of the code's own formula):**
  - `r = round(9 / 1200, 4) = round(0.0075, 4) = 0.0075` (exact, no precision loss for this specific rate).
  - `f = (1.0075)^240 ≈ 6.0092`.
  - `EMI = 1,000,000 * 0.0075 * 6.0092 / (6.0092 - 1) ≈ 45069 / 5.0092 ≈ 8997.19` (approximate; actual value depends on full floating-point precision of `(1.0075)**240`, which was not executed in this review — flagged as **uncertain/needs runtime verification**, not confirmed by execution). The commonly known EMI for ₹10,00,000 at 9% for 20 years is approximately ₹8,997, which is consistent with this formula, but the exact code output (to 2 decimal places) should be confirmed by actually running `emi(1000000, 9, 240)` since this was not executed as part of this review.

## 6. Amortisation schedule behavior

- **When interest is calculated (confirmed):** For each loop iteration, `interest = round(balance * r, 2)` is computed on the **opening balance** for that month — i.e., the balance carried over from the end of the previous month (or the original principal for month 1).
- **How principal repayment is calculated (confirmed):** `principal_part = round(instalment - interest, 2)`, i.e., the fixed EMI amount minus that month's interest portion.
- **How the balance changes (confirmed):** `balance = round(balance - principal_part, 2)` after each month, carried into the next iteration.
- **Confirmed bug:** The loop is `for month in range(1, tenure_months):`, which in Python iterates values `1, 2, ..., tenure_months - 1` — it never reaches `month == tenure_months`. As a direct consequence:
  - The function returns `tenure_months - 1` rows instead of `tenure_months` rows.
  - The `if month == tenure_months:` branch, which is clearly intended to force the last principal portion to equal the remaining balance (ensuring the loan fully amortizes to zero), is dead code and never executes.
  - The schedule as currently returned does not include a final row where `balance` is guaranteed to reach `0.0` via the true-up logic; it only reaches a value close to zero through the ordinary (non-trued-up) iterative calculation, and even that row is for month `tenure_months - 1`, not the actual last month.

## 7. Prepayment behavior

- `prepayment_savings` reads the balance at `prepay_month` from the amortisation schedule (`sched[prepay_month - 1]["balance"]`) and subtracts `prepay_amount` to get `new_balance`.
- **Confirmed handling when prepayment is greater than or equal to the outstanding balance:** The code checks `if new_balance <= 0:` and, in that case, explicitly sets `months_left = 0` — meaning the loan is treated as fully paid off immediately, with no further instalments needed. This path does **not** call `remaining_tenure` at all, so the `ValueError` inside `remaining_tenure` (for an instalment too small to cover interest) cannot be triggered in this scenario.
- The function does not return or report any "overpayment" or "refund" amount when `prepay_amount` exceeds `balance` — the excess amount beyond what was owed is simply absorbed into the calculation (i.e., `new_balance` can be a negative number, but it is only used in the `<= 0` comparison, not reported back to the caller). There is no explicit field in the output dict indicating how much, if any, was "overpaid."
- **Uncertain/needs verification:** Whether this silent absorption of excess prepayment (rather than flagging/returning it) is the intended business behavior is not stated anywhere in the code or docstring, and should be clarified/tested.

## 8. Edge cases and risks

The following are **confirmed by direct code inspection** (not speculation):

1. **`amortisation_schedule` off-by-one loop bound.** `for month in range(1, tenure_months):` excludes the final month. This is the most significant and clearly verifiable defect in the codebase, and it propagates into `outstanding_after` and `prepayment_savings`, both of which build on `amortisation_schedule`.
2. **Rate-conversion inconsistency between `_monthly_rate` and `remaining_tenure`.** `_monthly_rate` divides `annual_rate` by `1200` (percent → monthly decimal). `remaining_tenure` instead computes `r = annual_rate / 100` (percent → annual decimal) and then plugs this directly into a formula that expects a **monthly** rate (`n = -log(1 - balance*r/instalment) / log(1+r)`). This is a confirmed inconsistency in how the same "rate" concept is converted in two different functions within the same module. Whether this is an intentional difference or a bug cannot be fully confirmed from static reading alone, but the two functions clearly use incompatible conventions for what `r` represents, and `remaining_tenure` is called by `prepayment_savings` with the original `annual_rate`, the same value fed to `_monthly_rate`-based functions elsewhere — strongly suggesting a genuine defect rather than an intentional design choice.
3. **`_monthly_rate` rounds to 4 decimal places.** For rates that don't divide evenly by 1200 (most rates other than round numbers like 9%, 12%, 6%, etc.), this rounding introduces a small but real precision loss that compounds across long tenures (e.g., 240+ months). This is a confirmed characteristic of the code, though the real-world materiality of the resulting error has not been measured in this review.
4. **No validation of negative or zero `annual_rate`.** `emi()` validates `principal` and `tenure_months` but not `annual_rate`. A negative rate would flow through the formula without any guard.
5. **`compare_offers` has no key validation.** Offer dicts missing `"bank"`, `"rate"`, or `"tenure"` will raise an unhandled `KeyError` rather than a descriptive error.
6. **`prepayment_savings` has no bounds-checking on `prepay_month`.** A value of `0` or negative silently uses Python's negative-indexing behavior (e.g., `sched[-1]`) instead of raising a clear error; a `prepay_month` greater than `tenure_months` (or greater than the schedule's actual length, which is `tenure_months - 1` per item 1) would raise an `IndexError`.
7. **`schedule_to_csv` appears to be unused** within the codebase itself (no call site found in `cli.py` or `calculator.py`); it is presumably intended for external callers of the library.
8. **Floating-point rounding accumulation.** Both `amortisation_schedule` (balance updates every iteration) and `total_payment`/`total_interest` (multiplying an already-rounded EMI by tenure) perform repeated `round()` operations rather than a single final rounding, which can cause small cumulative drift versus a theoretically "exact" calculation. This is confirmed by reading the code; the magnitude of the drift has not been measured by execution in this review.

## Manual review notes

The following behaviors are documented above based on static code reading only. They were **not verified by actually running the code** in this review, and should be confirmed with pytest tests before relying on them:

- **0% interest (`annual_rate = 0`):** Confirm `emi()` returns exactly `principal / tenure_months` and that `amortisation_schedule()` produces consistent all-principal, no-interest rows (noting the off-by-one row-count issue still applies). Also confirm `remaining_tenure()` and `eligible_amount()` behave correctly at `r == 0`.
- **1-month tenure (`tenure_months = 1`):** Confirm `emi()` behaves sensibly (entire principal + one month interest due in a single instalment), and specifically check `amortisation_schedule(principal, rate, 1)` — since `range(1, 1)` is an **empty range**, this will almost certainly return an **empty list** (`[]`), which should be verified as a real, reproducible behavior and tested explicitly, since it has direct downstream effects on `outstanding_after` and `prepayment_savings` when `tenure_months = 1`.
- **Annual-to-monthly interest conversion:** Verify `_monthly_rate` outputs via direct unit tests for several rates (including ones that don't divide evenly into 1200, e.g. 8.35%, 10.5%) to quantify the real impact of the 4-decimal rounding.
- **Very large principal values:** Confirm no overflow, precision loss, or formatting issues in `emi`, `amortisation_schedule`, and especially `format_inr` (Indian digit grouping logic) for very large numbers (e.g., crores/hundreds of crores).
- **Prepayment larger than the outstanding balance:** Confirm the actual numeric output of `prepayment_savings` when `prepay_amount > balance` at `prepay_month` — specifically verify `months_left == 0`, `new_tenure == prepay_month`, and whether `interest_saved` is computed sensibly despite `new_balance` being negative in the intermediate calculation (see Section 7).
- **Rate-convention mismatch in `remaining_tenure` vs. `_monthly_rate`:** Write a test that computes `remaining_tenure` results using the same rate as an equivalent `emi`-based schedule, to numerically confirm whether the two functions diverge as the static analysis in Section 8, item 2 suggests.
