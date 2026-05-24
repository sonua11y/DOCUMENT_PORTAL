import difflib
import re
import sys
from dotenv import load_dotenv
import pandas as pd
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import OutputFixingParser
from utils.model_loader import ModelLoader
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException
from prompt.prompt_library import PROMPT_REGISTRY
from model.models import SummaryResponse,PromptType

class DocumentComparatorLLM:
    def __init__(self):
        load_dotenv()
        self.loader = ModelLoader()
        self.llm = self.loader.load_llm()
        self.parser = JsonOutputParser(pydantic_object=SummaryResponse)
        self.fixing_parser = OutputFixingParser.from_llm(parser=self.parser, llm=self.llm)
        self.prompt = PROMPT_REGISTRY[PromptType.DOCUMENT_COMPARISON.value]
        self.chain = self.prompt | self.llm | self.parser
        log.info("DocumentComparatorLLM initialized", model=self.llm)

    def _parse_combined_docs(self, combined_docs: str) -> dict[str, dict[int, str]]:
        documents: dict[str, dict[int, str]] = {}
        current_document = "Document 1"
        current_page = 0
        current_lines: list[str] = []

        def flush_page() -> None:
            nonlocal current_lines, current_page, current_document
            if current_lines:
                documents.setdefault(current_document, {})[current_page] = "\n".join(current_lines).strip()
                current_lines = []

        for raw_line in combined_docs.splitlines():
            doc_match = re.match(r"^Document:\s*(.+)$", raw_line.strip())
            page_match = re.match(r"^---\s*Page\s*(\d+)\s*---$", raw_line.strip())

            if doc_match:
                flush_page()
                current_document = doc_match.group(1).strip() or current_document
                current_page = 0
                continue

            if page_match:
                flush_page()
                current_page = int(page_match.group(1))
                continue

            if current_page > 0:
                current_lines.append(raw_line)

        flush_page()
        return documents

    def _summarize_page_diff(self, reference_text: str, actual_text: str) -> str:
        reference_lines = [line.strip() for line in reference_text.splitlines() if line.strip()]
        actual_lines = [line.strip() for line in actual_text.splitlines() if line.strip()]

        if reference_lines == actual_lines:
            return "NO CHANGE"

        diff = list(difflib.unified_diff(reference_lines, actual_lines, lineterm=""))
        if not diff:
            return "NO CHANGE"

        useful_lines = [line for line in diff if line and not line.startswith(("---", "+++", "@@"))]
        if not useful_lines:
            return "NO CHANGE"

        return " | ".join(useful_lines[:8])

    def _pages_from_text(self, text: str) -> dict[int, str]:
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
                continue

            if current_page is not None:
                current_lines.append(raw_line)

        flush_page()
        return pages

    def _local_compare_from_texts(self, reference_text: str, actual_text: str) -> pd.DataFrame:
        reference_pages = self._pages_from_text(reference_text)
        actual_pages = self._pages_from_text(actual_text)

        rows = []
        all_pages = sorted(set(reference_pages.keys()) | set(actual_pages.keys()))
        for page_number in all_pages:
            reference_text = reference_pages.get(page_number, "")
            actual_text = actual_pages.get(page_number, "")
            changes = self._summarize_page_diff(reference_text, actual_text)
            rows.append({"Page": f"Page {page_number}", "Changes": changes})

        return pd.DataFrame(rows)

    def _local_compare_documents(self, combined_docs: str) -> pd.DataFrame:
        documents = self._parse_combined_docs(combined_docs)
        if len(documents) >= 2:
            document_names = list(documents.keys())[:2]
            reference_pages = documents[document_names[0]]
            actual_pages = documents[document_names[1]]

            rows = []
            all_pages = sorted(set(reference_pages.keys()) | set(actual_pages.keys()))
            for page_number in all_pages:
                reference_text = reference_pages.get(page_number, "")
                actual_text = actual_pages.get(page_number, "")
                changes = self._summarize_page_diff(reference_text, actual_text)
                rows.append({"Page": f"Page {page_number}", "Changes": changes})

            return pd.DataFrame(rows)

        raise ValueError("Expected two documents in combined_docs")

    def compare_documents(self, combined_docs: str, reference_text: str | None = None, actual_text: str | None = None) -> pd.DataFrame:
        try:
            if len(combined_docs) > 6000:
                if reference_text is not None and actual_text is not None:
                    log.warning("Combined comparison input is large; using local page-wise comparison", chars=len(combined_docs))
                    return self._local_compare_from_texts(reference_text, actual_text)
                log.warning("Combined comparison input is large; using local page-wise comparison", chars=len(combined_docs))
                return self._local_compare_documents(combined_docs)

            inputs = {
                "combined_docs": combined_docs,
                "format_instruction": self.parser.get_format_instructions()
            }

            log.info("Invoking document comparison LLM chain")
            response = self.chain.invoke(inputs)
            log.info("Chain invoked successfully", response_preview=str(response)[:200])
            return self._format_response(response)
        except Exception as e:
            log.error("Error in compare_documents", error=str(e))
            try:
                log.warning("Falling back to local page-wise comparison", error=str(e))
                if reference_text is not None and actual_text is not None:
                    return self._local_compare_from_texts(reference_text, actual_text)
                return self._local_compare_documents(combined_docs)
            except Exception as fallback_error:
                log.error("Local comparison fallback failed", error=str(fallback_error))
                raise DocumentPortalException("Error comparing documents", sys)

    def _format_response(self, response_parsed: list[dict]) -> pd.DataFrame: #type: ignore
        try:
            df = pd.DataFrame(response_parsed)
            return df
        except Exception as e:
            log.error("Error formatting response into DataFrame", error=str(e))
            DocumentPortalException("Error formatting response", sys)
