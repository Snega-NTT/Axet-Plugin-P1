# loan-calc (Assignment P1)

A small Python module for retail loan calculations: EMI, amortisation schedule, prepayment savings, offer comparison and eligibility.

All identified calculation bugs have been fixed and are covered by a pytest test suite. See `ARCHITECTURE.md` for a description of the current implementation and `PROMPT_LOG.md` for a log of review decisions made during development.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Try it

```bash
python cli.py 1000000 9 240
python cli.py 1000000 9 240 --schedule
python cli.py 1000000 9 240 --prepay-month 24 --prepay-amount 200000
```

### Example output

```bash
$ python cli.py 1000000 9 240
```

```json
{
  "principal": "₹10,00,000.00",
  "rate": "9.0% p.a.",
  "tenure": "240 months",
  "emi": "₹8,997.26",
  "total_interest": "₹11,59,342.40",
  "total_payment": "₹21,59,342.40",
  "last_emi": "2046-10",
  "currency": "INR"
}
```

## Run tests

```bash
pytest -v
pytest --cov=loan_calc --cov-report=term-missing
```

Tests are located in the `tests/` folder (`tests/test_calculator.py`).

### Latest test results

```
34 passed in 0.13s
```

### Latest coverage results

```
Name                      Stmts   Miss  Cover   Missing
-------------------------------------------------------
loan_calc\__init__.py         1      0   100%
loan_calc\calculator.py     110      2    98%   374-375
-------------------------------------------------------
TOTAL                       111      2    98%
```
