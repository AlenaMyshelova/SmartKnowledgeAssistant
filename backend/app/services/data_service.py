from typing import List, Dict, Any

from app.data_manager import DataManager

class DataService:
    """
    Сервис для работы с источниками данных.
    Предоставляет удобный интерфейс для работы с FAQ и другими данными.
    """
    
    def __init__(self):
        self.data_manager = DataManager()
    
    def get_all_data_sources(self) -> Dict[str, Any]:
        """
        Получение информации обо всех доступных источниках данных.
        
        Returns:
            Словарь с информацией о каждом источнике
        """
        return self.data_manager.get_all_data_sources()
    
    def get_categories(self) -> List[str]:
        """
        Получение всех доступных категорий FAQ.
        
        Returns:
            Список строк с названиями категорий
        """
        return self.data_manager.get_all_categories()
    
    def get_faqs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Получение FAQ по определенной категории.
        
        Args:
            category: Название категории
            
        Returns:
            Список FAQ записей в указанной категории
        """
        return self.data_manager.get_faq_by_category(category)
    
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск FAQ по запросу.
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            
        Returns:
            Список релевантных FAQ записей
        """
        return self.data_manager.search_faqs(query, limit)
    
    def get_data_statistics(self) -> Dict[str, Any]:
        """
        Получение статистики по данным.
        
        Returns:
            Словарь со статистикой
        """
        sources = self.get_all_data_sources()
        categories = self.get_categories()
        
        return {
            "total_sources": len(sources),
            "total_categories": len(categories),
            "categories": categories,
            "sources_detail": sources
        }

# Создаем единственный экземпляр сервиса
data_service = DataService()