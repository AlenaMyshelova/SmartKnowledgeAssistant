from typing import List, Dict, Any, Tuple

def build_context_from_results(results: List[Dict[str, Any]]) -> Tuple[str, str]:
    """
    Создание контекста для запроса к AI из результатов поиска.
    
    Args:
        results: результаты поиска (с оценками релевантности)
        
    Returns:
        Tuple[str, str]: (контекст для AI, заметка о недостатке данных)
    """
    if not results:
        return "", "\n\nNote: No relevant information was found in our knowledge base. Please answer based on your general knowledge."
    
    # НОВОЕ: Сортируем результаты по релевантности (если есть оценки)
    if "_score" in results[0]:
        results = sorted(results, key=lambda x: x.get("_score", 0), reverse=True)
    
    # Строим контекст из результатов
    context_parts = []
    
    for i, result in enumerate(results):
    # Более информативная метка с категорией и ID
        category = result.get("Category", "General")
        faq_id = result.get("ID", i+1)
        
        # Формируем заголовок секции
        section = f"--- {category} FAQ #{faq_id} ---\n"
        
        # Добавляем содержимое документа
        if "Question" in result and "Answer" in result:
            # Для FAQ формата
            section += f"Question: {result['Question']}\n"
            section += f"Answer: {result['Answer']}\n"
            
            # Добавляем категорию, если есть
            if "Category" in result and result["Category"]:
                section += f"Category: {result['Category']}\n"
        else:
            # Для произвольного документа
            # Исключаем служебные поля
            skip_fields = ["_score", "_id", "_source", "_document_id", "_source_id"]
            
            # Добавляем все остальные поля
            for key, value in result.items():
                if key not in skip_fields and value is not None:
                    section += f"{key}: {value}\n"
        
        context_parts.append(section)
    
    # Объединяем все секции в единый контекст
    full_context = "\n".join(context_parts)
    
    # НОВОЕ: Определяем, достаточно ли релевантной информации
    has_relevant_info = any(result.get("_score", 0) > 0.7 for result in results)
    
    scarcity_note = ""
    if not has_relevant_info:
        scarcity_note = "\n\nNote: The information provided may not directly answer the question. Please use your general knowledge where appropriate, but mention when you do so."
    
    return full_context, scarcity_note