"""Actual browser producer output accepted by unchanged Python document validators."""

import json
import subprocess
from pathlib import Path

import pytest
from test_canvas_document_wire import VECTORS, arguments

from shared.canvas_document_wire import validate_canvas_document
from shared.document_sections import validate_document_sections

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = """
import {prepareDocumentParts} from './extension/canvas/document-parts.mjs';
let input='';
for await (const chunk of process.stdin) input+=chunk;
const requests=JSON.parse(input);
console.log(JSON.stringify(await Promise.all(requests.map(prepareDocumentParts))));
"""


def produce(requests):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", SCRIPT],
        input=json.dumps(requests, ensure_ascii=True),
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def produced_vectors():
    return produce(
        [
            {"text": v["raw_text"]} if v["raw_pages"] is None else {"pages": v["raw_pages"]}
            for v in VECTORS
        ]
    )


@pytest.mark.parametrize("index,vector", list(enumerate(VECTORS)), ids=[v["name"] for v in VECTORS])
def test_unchanged_root_vectors_accept_actual_browser_parts(index, vector, produced_vectors):
    output = produced_vectors[index]
    data = arguments(vector)
    data.update(manifest=output["manifest"], parts=output["parts"])
    data["metadata"].update(
        total_characters=output["total_characters"], total_pages=output["total_pages"]
    )
    actual = validate_canvas_document(**data)
    assert actual.canonical_bytes == vector["canonical_utf8"].encode("utf-8")
    assert actual.document_digest == vector["sha256"]
    assert output["unrepresented_pages"] == list(actual.sections.unrepresented_pages)


@pytest.mark.parametrize(
    "input_data",
    [
        {"text": "e\u0301\r\n📚" * 30000},
        {"pages": ["", "📚" * 24001, "", "Cafe\u0301\r\n", ""]},
        {"text": "📚" * 200000},
        {"text": "x" * 512, "sectionCharacters": 1},
    ],
)
def test_long_browser_sections_pass_existing_codepoint_and_hash_validation(input_data):
    output = produce([input_data])[0]
    sections = validate_document_sections(
        output["manifest"],
        output["parts"],
        total_characters=output["total_characters"],
        total_pages=output["total_pages"],
    )
    assert output["unrepresented_pages"] == list(sections.unrepresented_pages)
    assert len("".join(s.text for s in sections.sections)) == output["total_characters"]
