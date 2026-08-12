"""arXiv source connector — fetches papers from arXiv API.

Handles search, fetching by ID, and parsing arXiv XML responses.
Respects rate limits (1 request per 3 seconds per arXiv guidelines).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import time
import re


@dataclass
class ArxivPaper:
    """A paper fetched from arXiv."""
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: str
    updated: str
    pdf_url: str
    full_text: str = ""  # Populated if full text is fetched
    source: str = "arxiv.org"


class ArxivSource:
    """Fetches papers from the arXiv API.

    Respects arXiv rate limits: max 1 request per 3 seconds.
    """

    BASE_URL = "http://export.arxiv.org/api/query"
    RATE_LIMIT_SECONDS = 3.0

    def __init__(self):
        self._last_request = 0.0

    def _rate_limit(self):
        """Enforce arXiv rate limit."""
        elapsed = time.time() - self._last_request
        if elapsed < self.RATE_LIMIT_SECONDS:
            time.sleep(self.RATE_LIMIT_SECONDS - elapsed)
        self._last_request = time.time()

    def search(self, query: str, max_results: int = 10, start: int = 0) -> list[ArxivPaper]:
        """Search arXiv for papers matching a query.

        Args:
            query: Search query (supports arXiv query syntax).
            max_results: Maximum papers to return (max 100 per request).
            start: Offset for pagination.

        Returns:
            List of ArxivPaper objects with metadata and abstracts.
        """
        self._rate_limit()

        params = {
            "search_query": query,
            "start": str(start),
            "max_results": str(min(max_results, 100)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(url, headers={"User-Agent": "Nullresearch-Triage/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_data = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise ConnectionError(f"arXiv API unavailable: {e}")

        return self._parse_search_results(xml_data)

    def fetch_by_id(self, arxiv_id: str, fetch_full_text: bool = False) -> Optional[ArxivPaper]:
        """Fetch a single paper by arXiv ID.

        Args:
            arxiv_id: arXiv ID (e.g., '2401.00001' or 'arxiv:2401.00001').
            fetch_full_text: If True, also fetch the PDF full text (currently returns abstract only).

        Returns:
            ArxivPaper or None if not found.
        """
        arxiv_id = arxiv_id.replace("arxiv:", "").strip()
        papers = self.search(f"id:{arxiv_id}", max_results=1)
        if not papers:
            return None
        paper = papers[0]
        paper.arxiv_id = arxiv_id
        return paper

    def fetch_recent(self, category: str = "cs.AI", max_results: int = 10, days: int = 1) -> list[ArxivPaper]:
        """Fetch recent papers in a category.

        Args:
            category: arXiv category (e.g., 'cs.AI', 'cs.CL', 'cs.LG').
            max_results: Maximum papers to return.
            days: Look back this many days.

        Returns:
            List of ArxivPaper objects.
        """
        query = f"cat:{category}"
        papers = self.search(query, max_results=max_results)
        return papers

    def fetch_papers_for_triage(self, categories: list[str], max_per_category: int = 5) -> list[dict]:
        """Fetch papers formatted for the triage pipeline.

        Returns papers in the format expected by LiteratureTriageAgent.triage_queue().
        """
        all_papers = []
        for category in categories:
            try:
                papers = self.fetch_recent(category, max_results=max_per_category)
                for p in papers:
                    all_papers.append({
                        "id": p.arxiv_id,
                        "title": p.title,
                        "text": p.abstract + ("\n\n" + p.full_text if p.full_text else ""),
                        "source": f"https://arxiv.org/abs/{p.arxiv_id}",
                        "metadata": {
                            "authors": p.authors,
                            "categories": p.categories,
                            "published": p.published,
                        },
                    })
            except ConnectionError as e:
                print(f"  [warn] Skipping {category}: {e}")
                continue
        return all_papers

    def _parse_search_results(self, xml_data: str) -> list[ArxivPaper]:
        """Parse arXiv API XML response into ArxivPaper objects."""
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }

        root = ET.fromstring(xml_data)
        papers = []

        for entry in root.findall("atom:entry", ns):
            arxiv_id = self._extract_text(entry, "atom:id", ns)
            arxiv_id = arxiv_id.split("/abs/")[-1] if arxiv_id else "unknown"

            title = self._extract_text(entry, "atom:title", ns)
            title = re.sub(r'\s+', ' ', title).strip()

            abstract = self._extract_text(entry, "atom:summary", ns)
            abstract = re.sub(r'\s+', ' ', abstract).strip()

            authors = [
                self._extract_text(author, "atom:name", ns)
                for author in entry.findall("atom:author", ns)
            ]

            categories = [
                cat.get("term", "")
                for cat in entry.findall("atom:category", ns)
            ]

            published = self._extract_text(entry, "atom:published", ns)
            updated = self._extract_text(entry, "atom:updated", ns)

            # Find PDF link
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                elif link.get("rel") == "alternate":
                    pass  # Abstract page link

            papers.append(ArxivPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                abstract=abstract,
                categories=categories,
                published=published or "",
                updated=updated or "",
                pdf_url=pdf_url,
            ))

        return papers

    def _extract_text(self, element, xpath: str, ns: dict) -> str:
        """Safely extract text from an XML element."""
        child = element.find(xpath, ns)
        return child.text.strip() if child is not None and child.text else ""
