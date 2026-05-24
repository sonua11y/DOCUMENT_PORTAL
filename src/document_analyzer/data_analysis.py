import os
import sys
import re
from google.api_core.exceptions import ResourceExhausted
from utils.model_loader import ModelLoader
from logger import GLOBAL_LOGGER as log
from exception.custom_exception import DocumentPortalException
from model.models import *
from langchain_core.output_parsers import JsonOutputParser
from langchain.output_parsers import OutputFixingParser
from prompt.prompt_library import PROMPT_REGISTRY # type: ignore

class DocumentAnalyzer:
    """
    Analyzes documents using a pre-trained model.
    Automatically logs all actions and supports session-based organization.
    """
    def __init__(self):
        try:
            self.loader=ModelLoader()
            self.llm=self.loader.load_llm()
            self.fallback_llm = None

            llm_provider = os.getenv("LLM_PROVIDER", "google")
            if llm_provider != "groq" and "groq" in self.loader.config.get("llm", {}):
                try:
                    self.fallback_llm = self.loader.load_llm("groq")
                    log.info("Groq fallback LLM initialized for document analysis")
                except Exception as fallback_error:
                    log.warning("Groq fallback unavailable", error=str(fallback_error))
            
            # Prepare parsers
            self.parser = JsonOutputParser(pydantic_object=Metadata)
            self.fixing_parser = OutputFixingParser.from_llm(parser=self.parser, llm=self.llm)
            
            self.prompt = PROMPT_REGISTRY["document_analysis"]
            
            log.info("DocumentAnalyzer initialized successfully")
            
            
        except Exception as e:
            log.error(f"Error initializing DocumentAnalyzer: {e}")
            raise DocumentPortalException("Error in DocumentAnalyzer initialization", sys)
        
        
    
    def _build_chain(self, llm):
        return self.prompt | llm | OutputFixingParser.from_llm(parser=self.parser, llm=llm)


    def _is_quota_error(self, error: Exception) -> bool:
        error_text = str(error)
        return isinstance(error, ResourceExhausted) or "RATE_LIMIT_EXCEEDED" in error_text or "Quota exceeded" in error_text


    def _local_metadata_fallback(self, document_text: str) -> dict:
        """
        Deterministic fallback for when external LLM calls are unavailable.
        Keeps the API responsive with best-effort metadata extraction.
        """
        cleaned_lines = [line.strip() for line in document_text.splitlines() if line.strip()]
        first_line = cleaned_lines[0] if cleaned_lines else "Untitled Document"

        title = first_line[:120]
        if len(cleaned_lines) > 1 and len(cleaned_lines[0]) < 8:
            title = cleaned_lines[1][:120]

        author_match = re.search(r"(?im)^(?:author|by)[:\s]+(.+)$", document_text)
        authors = [author_match.group(1).strip()] if author_match else []

        date_patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b\d{2}/\d{2}/\d{4}\b",
            r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
            r"\b[A-Za-z]+\s+\d{1,2},\s+\d{4}\b",
        ]
        detected_dates = []
        for pattern in date_patterns:
            detected_dates.extend(re.findall(pattern, document_text))

        date_created = detected_dates[0] if detected_dates else "Not Available"
        last_modified = detected_dates[-1] if detected_dates else "Not Available"

        publisher_match = re.search(r"(?im)^(?:publisher|published by)[:\s]+(.+)$", document_text)
        publisher = publisher_match.group(1).strip() if publisher_match else "Not Available"

        page_count = document_text.count("\f") + 1 if document_text.strip() else "Not Available"

        sentences = re.split(r"(?<=[.!?])\s+", document_text.replace("\n", " "))
        summary = [sentence.strip() for sentence in sentences if sentence.strip()][:3]
        if not summary and document_text.strip():
            summary = [document_text.strip()[:300]]

        sentiment_score = 0
        positive_terms = ("good", "great", "excellent", "success", "positive", "benefit", "improve")
        negative_terms = ("bad", "poor", "fail", "risk", "negative", "issue", "problem")
        lower_text = document_text.lower()
        for term in positive_terms:
            sentiment_score += lower_text.count(term)
        for term in negative_terms:
            sentiment_score -= lower_text.count(term)

        if sentiment_score > 0:
            sentiment = "Positive"
        elif sentiment_score < 0:
            sentiment = "Negative"
        else:
            sentiment = "Neutral"

        return {
            "Summary": summary,
            "Title": title,
            "Author": authors,
            "DateCreated": date_created,
            "LastModifiedDate": last_modified,
            "Publisher": publisher,
            "Language": "Not Available",
            "PageCount": page_count,
            "SentimentTone": sentiment,
        }


    def analyze_document(self, document_text:str)-> dict:
        """
        Analyze a document's text and extract structured metadata & summary.
        """
        try:
            chain = self._build_chain(self.llm)
            
            log.info("Meta-data analysis chain initialized")

            response = chain.invoke({
                "format_instructions": self.parser.get_format_instructions(),
                "document_text": document_text
            })

            log.info("Metadata extraction successful", keys=list(response.keys()))
            
            return response

        except Exception as e:
            if self.fallback_llm:
                log.warning("Primary LLM failed, retrying analysis with fallback LLM", error=str(e))
                try:
                    fallback_chain = self._build_chain(self.fallback_llm)
                    response = fallback_chain.invoke({
                        "format_instructions": self.parser.get_format_instructions(),
                        "document_text": document_text
                    })
                    log.info("Metadata extraction successful using fallback LLM", keys=list(response.keys()))
                    return response
                except Exception as fallback_error:
                    log.error("Fallback metadata analysis failed", error=str(fallback_error))
                    log.warning("Using local metadata fallback after external LLM failure", error=str(fallback_error))
                    return self._local_metadata_fallback(document_text)

            log.error("Metadata analysis failed", error=str(e))
            log.warning("Using local metadata fallback after primary LLM failure", error=str(e))
            return self._local_metadata_fallback(document_text)
        
    
