import json

import pytest

from research_agent.workflow_validation import parse_prepare_result


@pytest.mark.parametrize(
    "response",
    [
        json.dumps({
            "reference_codebases": ["repo"],
            "reference_paths": ["/workplace/repo"],
            "reference_papers": ["paper"],
        }),
        """Here is the result:
        ```json
        {"reference_codebases":["repo"],"reference_paths":["/workplace/repo"],"reference_papers":["paper"]}
        ```""",
        """Selected resources: {"reference_codebases":["repo"],"reference_paths":["/workplace/repo"],"reference_papers":["paper"]}""",
    ],
)
def test_parse_prepare_result_accepts_json_in_agent_response(response):
    result = parse_prepare_result(response)

    assert result == {
        "reference_codebases": ["repo"],
        "reference_paths": ["/workplace/repo"],
        "reference_papers": ["paper"],
    }


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "empty response"),
        ("I could not find any repositories.", "valid JSON object"),
        (
            '{"reference_codebases":["repo"],"reference_paths":["/repo"]}',
            "reference_papers",
        ),
        (
            '{"reference_codebases":[],"reference_paths":["/repo"],"reference_papers":["paper"]}',
            "reference_codebases",
        ),
        (
            '{"reference_codebases":"repo","reference_paths":["/repo"],"reference_papers":["paper"]}',
            "reference_codebases",
        ),
        (
            '{"reference_codebases":[" "],"reference_paths":["/repo"],"reference_papers":["paper"]}',
            "non-empty strings",
        ),
    ],
)
def test_parse_prepare_result_rejects_invalid_handoff(response, message):
    with pytest.raises(ValueError, match=message):
        parse_prepare_result(response)
