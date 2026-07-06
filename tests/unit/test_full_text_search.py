from __future__ import annotations

from private_rag.search.service import field_weight_configuration, normalize_fts_query


def test_normalize_fts_query_quotes_exact_identifiers_and_ands_terms() -> None:
    assert normalize_fts_query("LiFePO4 UV-Vis") == 'LiFePO4 AND "UV-Vis"'
    assert normalize_fts_query('"epoxy acrylate" claims') == '"epoxy acrylate" AND claims'


def test_field_weight_configuration_prioritizes_titles_headings_and_patent_fields() -> None:
    weights = field_weight_configuration()

    assert weights["title"] > weights["body"]
    assert weights["headings"] > weights["body"]
    assert weights["claims"] > weights["body"]
    assert weights["examples"] > weights["body"]
    assert set(weights) == {
        "title",
        "headings",
        "body",
        "captions",
        "tables",
        "claims",
        "examples",
    }
