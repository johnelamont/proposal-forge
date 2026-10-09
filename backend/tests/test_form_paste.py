from app.services.form_paste import extract_questions

FORM = """\
Submit a proposal
Terms
Your bid: $65.00/hr
Cover letter
Additional details
Questions
1. Describe your recent experience with similar projects
2. What is your availability?
Please include samples of your work as an attachment to your proposal.
Attachments
Add attachment
"""


def test_extracts_numbered_and_question_mark_lines():
    found = extract_questions(FORM, [])
    assert found == [
        "Describe your recent experience with similar projects",
        "What is your availability?",
        "Please include samples of your work as an attachment to your proposal.",
    ]


def test_known_questions_are_not_repeated():
    found = extract_questions(FORM, ["what is your availability?"])
    assert "What is your availability?" not in found
    assert len(found) == 2


def test_noise_lines_are_ignored():
    assert extract_questions("Cover letter\nYour bid\nTerms\n", []) == []
