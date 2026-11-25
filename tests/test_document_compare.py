from src.document_compare.document_comparator import DocumentComparatorLLM


def test_comparison_reports_page_status_and_exact_text_changes():
    comparator = DocumentComparatorLLM()

    result = comparator.compare_documents(
        combined_docs="",
        reference_text=(
            "--- Page 1 ---\n"
            "  Product   name \n"
            "Old price: 10\n"
            "--- Page 2 ---\n"
            "Terms remain the same"
        ),
        actual_text=(
            "--- Page 1 ---\n"
            "Product name\n"
            "New price: 12\n"
            "--- Page 3 ---\n"
            "New appendix"
        ),
    ).to_dict(orient="records")

    assert [row["Status"] for row in result] == ["Modified", "Removed", "Added"]
    assert "Changed: Old price: 10 -> New price: 12" in result[0]["Changes"]
    assert result[1]["Actual Page"] == "-"
    assert result[2]["Reference Page"] == "-"


def test_combined_document_input_is_supported():
    comparator = DocumentComparatorLLM()

    result = comparator.compare_documents(
        "Document: reference.pdf\n--- Page 1 ---\nSame text\n"
        "Document: actual.pdf\n--- Page 1 ---\nSame text"
    )

    assert result.to_dict(orient="records") == [
        {
            "Page": "Page 1",
            "Reference Page": "Page 1",
            "Actual Page": "Page 1",
            "Status": "Unchanged",
            "Changes": "No text changes.",
        }
    ]
