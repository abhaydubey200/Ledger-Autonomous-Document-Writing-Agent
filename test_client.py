"""
Runs the two required test inputs against a live /agent endpoint and
prints the results. Start the server first:

    uvicorn main:app --reload

then in another terminal:

    python test_client.py
"""

import json
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

TEST_1_STANDARD = (
    "Create a project plan for launching a new mobile banking app for a "
    "fintech startup, including timeline, milestones, and team roles."
)

TEST_2_COMPLEX_AMBIGUOUS = (
    "We need something for the client meeting tomorrow about our Q3 "
    "performance. Budget is tight, not totally sure if it should be a "
    "report or a proposal for more funding, just put together whatever "
    "you think covers it best."
)


def call_agent(request_text: str):
    body = json.dumps({"request": request_text}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/agent",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def run(label: str, request_text: str):
    print(f"\n{'=' * 70}\nTEST: {label}\nREQUEST: {request_text}\n{'-' * 70}")
    result = call_agent(request_text)
    print(f"document_type : {result['document_type']}")
    print(f"llm_mode      : {result['llm_mode']}")
    print(f"assumptions   : {result['assumptions']}")
    print("plan:")
    for step in result["plan"]:
        print(f"  {step['step_id']}. {step['name']} - {step['description']}")
    print("execution_log:")
    for line in result["execution_log"]:
        print(f"  - {line}")
    print(f"download_url  : {BASE_URL}{result['download_url']}")
    return result


if __name__ == "__main__":
    run("1) Standard business request", TEST_1_STANDARD)
    run("2) Complex / ambiguous request", TEST_2_COMPLEX_AMBIGUOUS)
