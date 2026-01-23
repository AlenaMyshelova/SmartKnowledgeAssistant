from typing import List, Dict, Any

from app.data_manager import DataManager
import logging
class DataService:
    """
    Service for working with data sources.
    Provides a convenient interface for working with FAQs and other data.
    """
    
    def __init__(self):
        self.data_manager = DataManager()
    
    def get_all_data_sources(self) -> Dict[str, Any]:
        """
        Get information about all available data sources.
        
        Returns:
            Dictionary with information about each source
        """
        return self.data_manager.get_all_data_sources()
    
    def get_categories(self) -> List[str]:
        """ Get all available FAQ categories."""
        return self.data_manager.get_all_categories()
    
    def get_faqs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get FAQs by a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of FAQ entries in the specified category
        """
        return self.data_manager.get_faq_by_category(category)
    
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search FAQs by query.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of relevant FAQ entries
        """
        return self.data_manager.search_faqs(query, limit)
    async def search_similar(
        self,
        query: str,
        data_source: str = "company_faqs",
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents based on a query.
        
        Args:
            query: Search query
            data_source: Data source (company_faqs, uploaded_files, etc.)
            top_k: Number of results
            
        Returns:
            List of relevant documents
        """
        try:
            if data_source == "company_faqs":
                results = self.search_faqs(query, top_k)
                
                # Convert to expected format
                sources = []
                for faq in results:
                    sources.append({
                        "content": f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}",
                        "source": "company_faqs",
                        "category": faq.get('category', 'general'),
                        "relevance": faq.get('score', 0.8),
                        "metadata": {
                            "question": faq.get('question', ''),
                            "answer": faq.get('answer', ''),
                            "category": faq.get('category', '')
                        }
                    })
                
                return sources
                
            elif data_source == "uploaded_files":
                # currently no uploaded files search implemented
                return []
                
            else:
                # For general_knowledge return empty list
                return []
                
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error in search_similar: {e}")
            return []

    def get_data_statistics(self) -> Dict[str, Any]:
        """Get data statistics."""
        sources = self.get_all_data_sources()
        categories = self.get_categories()
        
        return {
            "total_sources": len(sources),
            "total_categories": len(categories),
            "categories": categories,
            "sources_detail": sources
        }

data_service = DataService()