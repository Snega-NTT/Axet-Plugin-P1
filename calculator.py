import math
from datetime import date
from pathlib import Path


DEFAULT_CURRENCY = "INR"


def _monthly_rate(annual_rate):
    return annual_rate / 1200


def emi(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the fixed monthly instalment (EMI) for a reducing-balance loan.

    Parameters
    ----------
    principal : float
        Loan amount (must be greater than 0).
    annual_rate : float
        Annual interest rate expressed as a percentage (e.g. 9 for 9% p.a.).
    tenure_months : int
        Loan tenure in months (must be greater than 0).

    Returns
    -------
    float
        The monthly instalment amount, rounded to 2 decimal places.

    Notes
    -----
    When the interest rate is zero, the EMI is principal divided by
    tenure_months, with no interest component.

    Raises
    ------
    ValueError
        If `tenure_months` is less than or equal to 0, or if `principal` is
        less than or equal to 0.
    """
    if tenure_months <= 0:
        raise ValueError("tenure must be positive")
    if principal <= 0:
        raise ValueError("principal must be positive")
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(principal / tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(principal * r * f / (f - 1), 2)


def total_payment(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate the total amount repaid over the full loan tenure.

    Parameters
    ----------
    principal : float
        Loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Loan tenure in months.

    Returns
    -------
    float
        Total of all EMI payments (EMI multiplied by tenure_months),
        rounded to 2 decimal places.

    Raises
    ------
    ValueError
        Propagated from `emi` if `principal` or `tenure_months` is invalid.
    """
    return round(emi(principal, annual_rate, tenure_months) * tenure_months, 2)


def total_interest(principal: float, annual_rate: float, tenure_months: int) -> float:
    """Calculate total interest paid over the full loan tenure.

    Parameters
    ----------
    principal : float
        Loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Loan tenure in months.

    Returns
    -------
    float
        Total interest paid (total payment minus principal), rounded to
        2 decimal places.

    Raises
    ------
    ValueError
        Propagated from `total_payment`/`emi` if `principal` or
        `tenure_months` is invalid.
    """
    return round(total_payment(principal, annual_rate, tenure_months) - principal, 2)


def amortisation_schedule(
    principal: float, annual_rate: float, tenure_months: int
) -> list[dict[str, int | float]]:
    """Build a month-by-month amortisation schedule for a loan.

    Parameters
    ----------
    principal : float
        Loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Loan tenure in months.

    Returns
    -------
    list[dict[str, int | float]]
        A list of row dictionaries, each containing:
        - "month" (int): the month number.
        - "emi" (float): the instalment amount for that month.
        - "interest" (float): the interest portion of that month's instalment.
        - "principal" (float): the principal portion of that month's instalment.
        - "balance" (float): the outstanding balance after that month's payment.

    Raises
    ------
    ValueError
        Propagated from `emi` if `principal` or `tenure_months` is invalid.
    """
    r = _monthly_rate(annual_rate)
    instalment = emi(principal, annual_rate, tenure_months)
    balance = principal
    rows = []
    for month in range(1, tenure_months + 1):
        interest = round(balance * r, 2)
        principal_part = round(instalment - interest, 2)
        if month == tenure_months:
            principal_part = round(balance, 2)
            instalment_amt = round(principal_part + interest, 2)
        else:
            instalment_amt = instalment
        balance = round(balance - principal_part, 2)
        rows.append({
            "month": month,
            "emi": instalment_amt,
            "interest": interest,
            "principal": principal_part,
            "balance": max(balance, 0.0),
        })
    return rows


def outstanding_after(
    principal: float, annual_rate: float, tenure_months: int, months_paid: int
) -> float:
    """Return the outstanding loan balance after a given number of months paid.

    Parameters
    ----------
    principal : float
        Loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Loan tenure in months.
    months_paid : int
        Number of EMIs already paid.

    Returns
    -------
    float
        The outstanding balance: the original principal if `months_paid`
        is 0 or less, the balance from the amortisation schedule at the
        given month, or 0.0 if `months_paid` exceeds the schedule length.

    Raises
    ------
    ValueError
        Propagated from `amortisation_schedule`/`emi` if `principal` or
        `tenure_months` is invalid.
    """
    if months_paid <= 0:
        return round(principal, 2)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    if months_paid > len(sched):
        return 0.0
    return sched[months_paid - 1]["balance"]


def remaining_tenure(balance: float, annual_rate: float, instalment: float) -> int:
    """Calculate the number of months needed to repay a balance at a fixed instalment.

    Parameters
    ----------
    balance : float
        Outstanding balance to be repaid.
    annual_rate : float
        Annual interest rate as a percentage.
    instalment : float
        Fixed monthly instalment amount.

    Returns
    -------
    int
        The number of months required to repay `balance`, rounded up to
        the nearest whole month. Returns 0 if `balance` is 0 or less.

    Raises
    ------
    ValueError
        If instalment is not large enough to repay the balance.
    """
    r = _monthly_rate(annual_rate)
    if balance <= 0:
        return 0
    if r == 0:
        return math.ceil(balance / instalment)
    if instalment <= balance * r:
        raise ValueError("instalment too small to repay the loan")
    n = -math.log(1 - balance * r / instalment) / math.log(1 + r)
    return math.ceil(n)


def prepayment_savings(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    prepay_month: int,
    prepay_amount: float,
) -> dict[str, float | int]:
    """Estimate the effect of a lump-sum prepayment while keeping the EMI unchanged.

    Parameters
    ----------
    principal : float
        Original loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Original loan tenure in months.
    prepay_month : int
        The month number at which the lump-sum prepayment is made.
    prepay_amount : float
        The lump-sum amount applied toward the outstanding balance.

    Returns
    -------
    dict[str, float | int]
        A dictionary containing:
        - "emi" (float): the unchanged monthly instalment.
        - "months_saved" (int): months saved compared to the original tenure.
        - "new_tenure" (int): the new total tenure after prepayment.
        - "interest_saved" (float): interest saved compared to the original loan.
        - "interest_paid_before_prepayment" (float): interest paid up to
          `prepay_month`.

    Raises
    ------
    ValueError
        Propagated from `emi` if `principal` or `tenure_months` is
        non-positive, or from `remaining_tenure` if the instalment cannot
        repay the reduced balance.
    IndexError
        May occur when prepay_month indexes beyond the generated amortisation
        schedule.
    """
    instalment = emi(principal, annual_rate, tenure_months)
    sched = amortisation_schedule(principal, annual_rate, tenure_months)
    balance = sched[prepay_month - 1]["balance"]
    effective_prepay = min(prepay_amount, balance)
    new_balance = balance - effective_prepay
    if new_balance <= 0:
        months_left = 0
    else:
        months_left = remaining_tenure(new_balance, annual_rate, instalment)
    original_left = tenure_months - prepay_month
    interest_paid_so_far = sum(row["interest"] for row in sched[:prepay_month])
    original_interest = total_interest(principal, annual_rate, tenure_months)
    new_total = instalment * prepay_month + effective_prepay + instalment * months_left
    new_interest = new_total - principal
    return {
        "emi": instalment,
        "months_saved": original_left - months_left,
        "new_tenure": prepay_month + months_left,
        "interest_saved": round(original_interest - new_interest, 2),
        "interest_paid_before_prepayment": round(interest_paid_so_far, 2),
    }


def compare_offers(
    principal: float, offers: list[dict[str, str | float | int]]
) -> list[dict[str, str | float]]:
    """Compare multiple loan offers and rank them by total cost.

    Parameters
    ----------
    principal : float
        Loan amount to use for all offers.
    offers : list[dict[str, str | float | int]]
        A list of offer dictionaries, each expected to contain "bank" (str),
        "rate" (float, annual percentage), "tenure" (int, months), and
        optionally "processing_fee_pct" (float).

    Returns
    -------
    list[dict[str, str | float]]
        A list of result dictionaries, each containing "bank" (str), "emi"
        (float), "total_interest" (float), "processing_fee" (float), and
        "total_cost" (float), sorted in ascending order by "total_cost".

    Raises
    ------
    ValueError
        Propagated from `emi` if an offer's `tenure` or `principal` is
        non-positive.
    KeyError
        If an offer dictionary is missing a required key such as "bank",
        "rate", or "tenure".
    """
    out = []
    for o in offers:
        e = emi(principal, o["rate"], o["tenure"])
        ti = total_interest(principal, o["rate"], o["tenure"])
        fee = o.get("processing_fee_pct", 0) * principal / 100
        out.append({
            "bank": o["bank"],
            "emi": e,
            "total_interest": ti,
            "processing_fee": round(fee, 2),
            "total_cost": round(ti + fee, 2),
        })
    out.sort(key=lambda x: x["total_cost"])
    return out


def eligible_amount(
    monthly_income: float,
    existing_emis: float,
    annual_rate: float,
    tenure_months: int,
    foir: float = 0.5,
) -> float:
    """Estimate the maximum loan principal a borrower is eligible for.

    Parameters
    ----------
    monthly_income : float
        Borrower's gross monthly income.
    existing_emis : float
        Sum of the borrower's existing EMI obligations.
    annual_rate : float
        Annual interest rate as a percentage for the proposed loan.
    tenure_months : int
        Proposed loan tenure in months.
    foir : float, optional
        Fixed Obligation to Income Ratio, by default 0.5.

    Returns
    -------
    float
        The eligible principal amount, rounded to 2 decimal places, or
        0.0 if the borrower has no remaining repayment capacity.
    """
    available = monthly_income * foir - existing_emis
    if available <= 0:
        return 0.0
    r = _monthly_rate(annual_rate)
    if r == 0:
        return round(available * tenure_months, 2)
    f = (1 + r) ** tenure_months
    return round(available * (f - 1) / (r * f), 2)


def format_inr(amount: float) -> str:
    """Format a numeric amount as an Indian-style currency string.

    Parameters
    ----------
    amount : float
        The amount to format. May be negative.

    Returns
    -------
    str
        The amount formatted with a "₹" symbol, Indian-style digit
        grouping (lakh/crore), and 2 decimal places. Negative amounts
        are prefixed with "-".
    """
    neg = amount < 0
    amount = abs(round(amount, 2))
    whole, frac = f"{amount:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + "₹" + whole + "." + frac


def schedule_to_csv(rows: list[dict[str, int | float]], path: str | Path) -> None:
    """Write an amortisation schedule to a CSV file.

    Parameters
    ----------
    rows : list[dict[str, int | float]]
        Schedule rows as returned by `amortisation_schedule`, each
        containing "month", "emi", "interest", "principal", and "balance".
    path : str | Path
        Destination file path.

    Returns
    -------
    None
    """
    with open(path, "w") as fh:
        fh.write("month,emi,interest,principal,balance\n")
        for r in rows:
            fh.write(f'{r["month"]},{r["emi"]},{r["interest"]},{r["principal"]},{r["balance"]}\n')


def summary(
    principal: float,
    annual_rate: float,
    tenure_months: int,
    start: date | None = None,
) -> dict[str, str]:
    """Produce a human-readable summary of a loan.

    Parameters
    ----------
    principal : float
        Loan amount.
    annual_rate : float
        Annual interest rate as a percentage.
    tenure_months : int
        Loan tenure in months.
    start : date | None, optional
        The date the loan begins; defaults to today's date if not provided.

    Returns
    -------
    dict[str, str]
        A dictionary of formatted strings containing:
        - "principal": the loan amount formatted as INR currency.
        - "rate": the annual rate formatted as "{rate}% p.a.".
        - "tenure": the tenure formatted as "{tenure_months} months".
        - "emi": the EMI formatted as INR currency.
        - "total_interest": total interest formatted as INR currency.
        - "total_payment": total payment formatted as INR currency.
        - "last_emi": the year and month of the final instalment, as
          "YYYY-MM".
        - "currency": the currency code, "INR".

    Raises
    ------
    ValueError
        Propagated from `emi` if `principal` or `tenure_months` is
        non-positive.
    """
    start = start or date.today()
    e = emi(principal, annual_rate, tenure_months)
    end_year = start.year + (start.month - 1 + tenure_months) // 12
    end_month = (start.month - 1 + tenure_months) % 12 + 1
    return {
        "principal": format_inr(principal),
        "rate": f"{annual_rate}% p.a.",
        "tenure": f"{tenure_months} months",
        "emi": format_inr(e),
        "total_interest": format_inr(total_interest(principal, annual_rate, tenure_months)),
        "total_payment": format_inr(total_payment(principal, annual_rate, tenure_months)),
        "last_emi": f"{end_year}-{end_month:02d}",
        "currency": DEFAULT_CURRENCY,
    }
