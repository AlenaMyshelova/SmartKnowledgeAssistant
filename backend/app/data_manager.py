from __future__ import annotations
from asyncio.log import logger
from app.vector_search import vector_search

from pathlib import Path
from typing import List, Dict, Any, Optional

import os
import pandas as pd


class DataManager:

    """ Class managing company FAQ data with vector search capabilities.
       Capabilities:
       - Reliable CSV loading relative to this file's location.
       - Fallback separator: tries ';' first, then ','.
       - Search across Category / Question / Answer columns (case-insensitive).
       - Vector semantic search using FAISS and OpenAI embeddings.
       - Retrieve all categories and data by category.
       - Return metadata about sources (columns, record counts).
    """

    def __init__(
        self,
        company_faqs_relpath: str = "./data/company_faqs.csv",
        encoding: str = "utf-8",
    ) -> None:
        self.encoding = encoding
        self.data_sources: Dict[str, pd.DataFrame] = {}
        
        # Absolute path to CSV relative to this file's location
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent  # app/ -> backend/
        self.company_faqs_path: Path = (backend_dir / company_faqs_relpath).resolve()
        
        # Directory for user-uploaded files
        self.upload_dir = backend_dir / "data" / "uploaded_files"
        self.upload_dir.mkdir(exist_ok=True, parents=True)

        logger.info(f"FAQ path: {self.company_faqs_path}") 

        # Allow path overrides via environment variables (optional)
        env_override = os.getenv("COMPANY_FAQS_PATH")
        if env_override:
            self.company_faqs_path = Path(env_override).expanduser().resolve()

        # Load data
        self.load_company_faqs()
        
        # Ensure vector index for FAQ exists
        self._ensure_faq_index()

    # -------------------
    # Data loading
    # -------------------
    def _read_csv_with_fallback(self, path: Path) -> pd.DataFrame:
        """
        Try reading CSV first with sep=';', then with sep=','.

        """
        last_err: Optional[Exception] = None

        for sep in (";", ","):
            try:
                return pd.read_csv(path, sep=sep, encoding=self.encoding)
            except Exception as e:
                last_err = e  # try next separator

        # If we reached here, both methods failed
        raise RuntimeError(f"Failed to read CSV at {path}: {last_err}")

    def load_company_faqs(self) -> None:
        """Load FAQ from CSV into memory."""
        try:
            if self.company_faqs_path.exists():
                df = self._read_csv_with_fallback(self.company_faqs_path)

                # Normalize expected columns (minimal contract)
                expected = {"Category", "Question", "Answer"}
                missing = expected - set(df.columns)
                if missing:
                    raise ValueError(
                        f"CSV {self.company_faqs_path} is missing required columns: {sorted(missing)}"
                    )

                # Convert strings to str (in case of NaN) to avoid errors with .str.lower()
                for col in ("Category", "Question", "Answer"):
                    df[col] = df[col].astype(str)

                self.data_sources["company_faqs"] = df

                print(
                    f"Loaded {len(df)} FAQ records from {self.company_faqs_path}"
                )
                # Small sample for visual inspection
                with pd.option_context("display.max_colwidth", 120):
                    print("Sample data:")
                    print(df.head(2))
            else:
                print(f"company_faqs.csv not found at: {self.company_faqs_path}")
        except Exception as e:
            print(f"Error loading company_faqs.csv from {self.company_faqs_path}: {e}")
    
    # Check and create vector index
    def _ensure_faq_index(self) -> None:
        """Check existence and freshness of vector index for FAQ."""
        try:
            index_exists = False
            for index_info in vector_search.list_indexes():
                if index_info['id'] == 'company_faqs':
                    index_exists = True
                    break
            
            # If index does not exist or FAQ file is newer, create a new index
            if not index_exists or (
                self.company_faqs_path.exists() and 
                self.company_faqs_path.stat().st_mtime > vector_search.last_updated.get('company_faqs', 0)
            ):
                print("Building vector index for company FAQs...")
                vector_search.build_index_for_company_faqs(str(self.company_faqs_path))
        
        except Exception as e:
            print(f"Error ensuring FAQ index: {e}")

    # -------------------
    # Search and queries
    # -------------------
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search FAQs using vector search.
        If vector search yields no results, fallback to standard text search.
        
        Args:
            query: user search query
            limit: maximum number of results
            
        Returns:
            List of found FAQs with relevance scores
        """
        try:
            # Check for index and try vector search
            self._ensure_faq_index()
            results = vector_search.search(query, 'company_faqs', top_k=limit)
            
            # If vector search yields results, return them
            if results:
                return results
                
            # If no results, use traditional search
            print("No vector search results, falling back to text search")
            return self._fallback_text_search(query, limit)
            
        except Exception as e:
            print(f"Error in vector search: {e}")
            # In case of vector search error, use text search
            return self._fallback_text_search(query, limit)
    
    #  Fallback text search
    def _fallback_text_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        df = self.data_sources.get("company_faqs")
        if df is None or df.empty:
            return []

        q = (query or "").strip().lower()
        if not q:
            return []

        mask = (
            df["Question"].str.lower().str.contains(q, na=False)
            | df["Answer"].str.lower().str.contains(q, na=False)
            | df["Category"].str.lower().str.contains(q, na=False)
        )

        results = df[mask].head(limit)
        records = results.to_dict("records")
        
        # Add dummy relevance score for compatibility with vector search
        for record in records:
            record["_score"] = 0.5
            
        return records
    
    # Search in uploaded user files
    def search_uploaded_file(self, query: str, file_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search uploaded file using vector search.
    
        """
        try:
            # Form source identifier
            source_id = f"uploaded_{file_id}"
            
            # Check for index existence
            index_exists = False
            for index_info in vector_search.list_indexes():
                if index_info['id'] == source_id:
                    index_exists = True
                    break
            
            # If index does not exist, create it
            if not index_exists:
                file_path = self.upload_dir / f"{file_id}.csv"
                if file_path.exists():
                    print(f"Building vector index for uploaded file {file_id}...")
                    vector_search.build_index_for_uploaded_file(file_id, str(file_path))
                else:
                    print(f"File not found: {file_id}")
                    return []
            
            results = vector_search.search(query, source_id, top_k=limit)
            return results
            
        except Exception as e:
            print(f"Error in search_uploaded_file: {e}")
            return []

    def get_all_data_sources(self) -> Dict[str, Any]:
        """
        Metadata for all loaded data sources
        """
        info: Dict[str, Any] = {}
        
        # Process standard data sources
        for name, df in self.data_sources.items():
            info[name] = {
                "records_count": int(len(df)),
                "columns": list(df.columns),
                "path": str(self.company_faqs_path) if name == "company_faqs" else None,
                "has_vector_index": name in {idx["id"] for idx in vector_search.list_indexes()}
            }
        
        # Add uploaded user files
        for file_path in self.upload_dir.glob("*.csv"):
            file_id = file_path.stem
            source_id = f"uploaded_{file_id}"
            
            try:
                df = pd.read_csv(file_path)
                info[source_id] = {
                    "name": f"Uploaded: {file_path.name}",
                    "type": "csv_uploaded",
                    "records_count": len(df),
                    "columns": list(df.columns),
                    "path": str(file_path),
                    "has_vector_index": source_id in {idx["id"] for idx in vector_search.list_indexes()}
                }
            except Exception as e:
                print(f"Error reading uploaded file {file_path}: {e}")
        
        return info

    def get_faq_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Return all FAQ entries with an exact category match (case insensitive)."""
        df = self.data_sources.get("company_faqs")
        if df is None or df.empty:
            return []
        c = (category or "").strip().lower()
        if not c:
            return []
        
        results = df[df["Category"].str.lower() == c]
        return results.to_dict("records")

    def get_all_categories(self) -> List[str]:
        """List of unique categories (as they appear in the data)."""
        df = self.data_sources.get("company_faqs")
        if df is None or df.empty:
            return []
        # Remove empty/NaN, convert to str
        cats = df["Category"].dropna().astype(str).unique().tolist()
        return cats


    def reload(self) -> None:
        """Reload data from CSV and update vector indexes."""
        self.load_company_faqs()
        # Update vector index after reloading data
        self._ensure_faq_index()