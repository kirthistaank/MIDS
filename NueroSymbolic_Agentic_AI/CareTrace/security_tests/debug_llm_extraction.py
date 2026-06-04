#!/usr/bin/env python3
"""Debug what the LLM actually extracts from test inputs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from caretrace.config import Settings
from caretrace.agents.interpretation import interpret_user_message
from caretrace.state import default_case


test_cases = [
    "My child has a fever. Temperature: 102°F, alert and playing, breathing normally, drinking fluids, wet diapers in last 8 hours.",
    "My child has a fever. Temperature: 104°F, alert, normal breathing, drinking fluids, wet diapers.",
    "My child has a fever. Temperature: 102°F, seems sleepy/not responding, normal breathing, drinking fluids, wet diapers.",
]

settings = Settings.from_env()
print(f"Using mock LLM: {settings.use_mock_llm}")
print(f"OpenAI API key present: {bool(settings.openai_api_key)}")
print(f"Skip Neo4j: {settings.skip_neo4j}")
print()

for i, text in enumerate(test_cases, 1):
    print(f"Test {i}: {text[:70]}...")
    case = interpret_user_message(settings, default_case(), text)

    print(f"  temp_f: {case.get('temp_f')}")
    print(f"  alertness: {case.get('alertness')}")
    print(f"  breathing: {case.get('breathing')}")
    print(f"  fluid_intake: {case.get('fluid_intake')}")
    print(f"  urine_last_8h: {case.get('urine_last_8h')}")
    print()
