import difflib
import re
import sys

import pandas as pd

from exception.custom_exception import DocumentPortalException
from logger import GLOBAL_LOGGER as log


class DocumentComparatorLLM:
    """Compare PDF text page by page and report explicit, deterministic changes."""

    RESULT_COLUMNS = ["Page", "Reference Page", "Actual Page", "Status", "Changes"]

    def _parse_combined_docs(self, combined_docs: str) -> dict[str, dict[int, str]]:
        documents: dict[str, dict[int, str]] = {}
        current_document = "Document 1"
        current_page = 0
        current_lines: list[str] = []

        def flush_page() -> None:
            nonlocal current_lines, current_page, current_document
            if current_page > 0:
                documents.setdefault(current_document, {})[current_page] = "\n".join(current_lines).strip()
                current_lines = []

        for raw_line in combined_docs.splitlines():
            doc_match = re.match(r"^Document:\s*(.+)$", raw_line.strip())
            page_match = re.match(r"^---\s*Page\s*(\d+)\s*---$", raw_line.strip())

            if doc_match:
                flush_page()
                current_document = doc_match.group(1).strip() or current_document
                current_page = 0
            elif page_match:
                flush_page()
                current_page = int(page_match.group(1))
            elif current_page > 0:
                current_lines.append(raw_line)

        flush_page()
        return documents

    @staticmethod
    def _pages_from_text(text: str) -> dict[int, str]:
        pages: dict[int, str] = {}
        current_page = None
        current_lines: list[str] = []

        def flush_page() -> None:
            nonlocal current_lines, current_page
            if current_page is not None:
                pages[current_page] = "\n".join(current_lines).strip()
                current_lines = []

        for raw_line in text.splitlines():
            page_match = re.match(r"^---\s*Page\s*(\d+)\s*---$", raw_line.strip())
            if page_match:
                flush_page()
                current_page = int(page_match.group(1))
            elif current_page is not None:
                current_lines.append(raw_line)

        flush_page()
        return pages

    @staticmethod
    def _normalized_lines(text: str) -> list[str]:
        return [" ".join(line.split()) for line in text.splitlines() if line.strip()]

    def _summarize_page_diff(self, reference_text: str, actual_text: str) -> str:
        reference_lines = self._normalized_lines(reference_text)
        actual_lines = self._normalized_lines(actual_text)

        if reference_lines == actual_lines:
            return "No text changes."

        changes: list[str] = []
        matcher = difflib.SequenceMatcher(a=reference_lines, b=actual_lines, autojunk=False)
        for tag, ref_start, ref_end, actual_start, actual_end in matcher.get_opcodes():
            removed = reference_lines[ref_start:ref_end]
            added = actual_lines[actual_start:actual_end]

            if tag == "delete":
                changes.extend(f"Removed: {line}" for line in removed)
            elif tag == "insert":
                changes.extend(f"Added: {line}" for line in added)
            elif tag == "replace":
                paired_count = min(len(removed), len(added))
                changes.extend(
                    f"Changed: {removed[index]} -> {added[index]}"
                    for index in range(paired_count)
                )
                changes.extend(f"Removed: {line}" for line in removed[paired_count:])
                changes.extend(f"Added: {line}" for line in added[paired_count:])

        return "\n".join(changes)

    def _local_compare_from_texts(self, reference_text: str, actual_text: str) -> pd.DataFrame:
        reference_pages = self._pages_from_text(reference_text)
        actual_pages = self._pages_from_text(actual_text)
        return self._compare_page_maps(reference_pages, actual_pages)

    def _compare_page_maps(
        self, reference_pages: dict[int, str], actual_pages: dict[int, str]
    ) -> pd.DataFrame:
        rows = []

        for page_number in sorted(set(reference_pages) | set(actual_pages)):
            reference_page = reference_pages.get(page_number)
            actual_page = actual_pages.get(page_number)

            if reference_page is None:
                status = "Added"
                changes = "Page exists only in the actual document."
            elif actual_page is None:
                status = "Removed"
                changes = "Page exists only in the reference document."
            elif self._normalized_lines(reference_page) == self._normalized_lines(actual_page):
                status = "Unchanged"
                changes = "No text changes."
            else:
                status = "Modified"
                changes = self._summarize_page_diff(reference_page, actual_page)

            rows.append(
                {
                    "Page": f"Page {page_number}",
                    "Reference Page": f"Page {page_number}" if reference_page is not None else "-",
                    "Actual Page": f"Page {page_number}" if actual_page is not None else "-",
                    "Status": status,
                    "Changes": changes,
                }
            )

        return pd.DataFrame(rows, columns=self.RESULT_COLUMNS)

    def _local_compare_documents(self, combined_docs: str) -> pd.DataFrame:
        documents = self._parse_combined_docs(combined_docs)
        if len(documents) < 2:
            raise ValueError("Expected two documents in combined_docs")

        document_names = list(documents)[:2]
        reference_pages = documents[document_names[0]]
        actual_pages = documents[document_names[1]]
        return self._compare_page_maps(reference_pages, actual_pages)

    def compare_documents(
        self,
        combined_docs: str,
        reference_text: str | None = None,
        actual_text: str | None = None,
    ) -> pd.DataFrame:
        try:
            if reference_text is not None and actual_text is not None:
                result = self._local_compare_from_texts(reference_text, actual_text)
            else:
                result = self._local_compare_documents(combined_docs)

            log.info("Document comparison completed", pages=len(result))
            return result
        except Exception as e:
            log.error("Error in compare_documents", error=str(e))
            raise DocumentPortalException("Error comparing documents", e) from e
