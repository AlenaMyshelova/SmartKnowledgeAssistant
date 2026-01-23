from typing import List, Dict, Any, Tuple

def build_context_from_results(results: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Creates context for AI query from search results.
    
    Args:
        results: search results (with relevance scores)
        
    Returns:
        Tuple[str, str]: (context for AI, note about data scarcity)
    """
    if not results:
        return "", "\n\nNote: No relevant information was found in our knowledge base. Please answer based on your general knowledge."
    
    # Sort results by relevance (if scores are present)
    if "_score" in results[0]:
        results = sorted(results, key=lambda x: x.get("_score", 0), reverse=True)
    
    # Build context from results
    context_parts = []
    
    for i, result in enumerate(results):
    # More informative label with category and ID
        category = result.get("Category", "General")
        faq_id = result.get("ID", i+1)
        
        # Form section header
        section = f"--- {category} FAQ #{faq_id} ---\n"
        
        # Add document content
        if "Question" in result and "Answer" in result:
            # For FAQ format
            section += f"Question: {result['Question']}\n"
            section += f"Answer: {result['Answer']}\n"
            
            # Add category if present
            if "Category" in result and result["Category"]:
                section += f"Category: {result['Category']}\n"
        else:
            # For arbitrary document
            # Exclude service fields
            skip_fields = ["_score", "_id", "_source", "_document_id", "_source_id"]
            
            # Add all other fields
            for key, value in result.items():
                if key not in skip_fields and value is not None:
                    section += f"{key}: {value}\n"
        
        context_parts.append(section)
    
    # Combine all sections into a single context
    full_context = "\n".join(context_parts)

    # Determine if there is sufficient relevant information
    has_relevant_info = any(result.get("_score", 0) > 0.7 for result in results)
    
    scarcity_note = ""
    if not has_relevant_info:
        scarcity_note = "\n\nNote: The information provided may not directly answer the question. Please use your general knowledge where appropriate, but mention when you do so."
    
    return full_context, scarcity_note