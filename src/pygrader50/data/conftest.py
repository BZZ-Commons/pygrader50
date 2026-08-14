"""Pytest hook copied into the student checkout before grading.

`pytest_assertrepr_compare` rewrites the representation of a failed comparison
so the grader can lift the expected and actual value out of the captured output
and show them in the feedback table.
"""


def pytest_assertrepr_compare(op, left, right):
    return [
        "Comparing values:",
        f"   expected: {right}",
        f"   actual  : {left}",
    ]
