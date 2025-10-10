import sys
from pathlib import Path
import pandas as pd
from app.vector_search import vector_search
from app.data_manager import DataManager

def print_divider():
    print("-" * 80)

def main():
    # Проверяем наличие аргументов
    if len(sys.argv) < 2:
        print("Usage: python test_vector_search.py <query>")
        return
    
    query = sys.argv[1]
    print(f"Testing vector search with query: '{query}'")
    print_divider()
    
    # 1. Инициализируем DataManager
    data_manager = DataManager()
    
    # 2. Проверяем индексы
    print("Available vector indexes:")
    indexes = vector_search.list_indexes()
    for idx in indexes:
        print(f"- {idx['id']}: {idx['doc_count']} documents, last updated: {idx['last_updated']}")
    print_divider()
    
    # 3. Выполняем поиск в FAQ
    print("Searching in company FAQs:")
    faq_results = data_manager.search_faqs(query, limit=3)
    if faq_results:
        for i, result in enumerate(faq_results):
            print(f"Result {i+1} (Score: {result.get('_score', 'N/A')}):")
            print(f"Q: {result.get('Question', 'N/A')}")
            print(f"A: {result.get('Answer', 'N/A')[:100]}...")
            print()
    else:
        print("No results found in FAQs.")
    print_divider()

if __name__ == "__main__":
    main()