import os
from venv import logger
import numpy as np
import faiss
import pickle
import time
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
import pandas as pd
from openai import OpenAI
from app.core.config import settings

class VectorSearchEngine:
    """
    Класс для векторного поиска с использованием FAISS и OpenAI эмбеддингов.
    Превращает тексты в векторы и выполняет семантический поиск.
    """
    
    def __init__(self, index_dir: str = "./data/indexes"):
        """Инициализация поискового движка."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-3-small"  # Модель OpenAI для эмбеддингов
        current_file = Path(__file__).resolve()
        backend_dir = current_file.parent.parent 
        self.index_dir = backend_dir / index_dir
        self.index_dir.mkdir(exist_ok=True, parents=True)
        
        logger.info(f"Vector index path: {self.index_dir}") 
        # Словари для хранения индексов и данных
        self.indexes = {}          # FAISS индексы {source_id: index}
        self.documents = {}        # Исходные документы {source_id: [docs]}
        self.last_updated = {}     # {source_id: timestamp}
    
    def _get_embedding(self, text: str) -> List[float]:
        """Получение эмбеддинга для текста через OpenAI API."""
        try:
            text = text.replace("\n", " ")
            response = self.client.embeddings.create(
                input=text,
                model=self.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error creating embedding: {e}")
            return [0.0] * 1536  # Размерность эмбеддингов модели
    
    def _get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Получение эмбеддингов для нескольких текстов (пакетный режим)."""
        try:
            cleaned_texts = [text.replace("\n", " ") for text in texts]
            response = self.client.embeddings.create(
                input=cleaned_texts,
                model=self.embedding_model
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Error creating batch embeddings: {e}")
            return [[0.0] * 1536 for _ in range(len(texts))]
    
    def _create_faiss_index(self, embeddings: List[List[float]]) -> faiss.IndexFlatL2:
        """Создание FAISS индекса из списка эмбеддингов."""
        embeddings_np = np.array(embeddings).astype('float32')
        dimension = embeddings_np.shape[1]  # Размерность векторов
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_np)
        return index
    
    def build_index_from_dataframe(
        self, 
        df: pd.DataFrame, 
        source_id: str, 
        text_columns: List[str],
        metadata_columns: Optional[List[str]] = None
    ) -> None:
        """Построение индекса из pandas DataFrame."""
        if metadata_columns is None:
            metadata_columns = []
        
        # Шаг 1: Подготовка текстов
        texts = []
        documents = []
        
        for _, row in df.iterrows():
            # Объединяем текст из указанных колонок
            combined_text = " ".join([str(row[col]) for col in text_columns if col in row])
            texts.append(combined_text)
            
            # Сохраняем оригинальный документ с метаданными
            doc = {col: row[col] for col in df.columns if col in text_columns + metadata_columns}
            doc["_source_id"] = source_id
            doc["_document_id"] = len(documents)
            documents.append(doc)
        
        # Шаг 2: Генерация эмбеддингов (по батчам)
        print(f"Generating embeddings for {len(texts)} texts from {source_id}...")
        
        batch_size = 100  # Размер пакета для API
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = self._get_embeddings_batch(batch)
            embeddings.extend(batch_embeddings)
            print(f"Processed batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
        
        # Шаг 3: Создание FAISS индекса
        print(f"Building FAISS index for {source_id}...")
        index = self._create_faiss_index(embeddings)
        
        # Шаг 4: Сохранение индекса и данных
        self.indexes[source_id] = index
        self.documents[source_id] = documents
        self.last_updated[source_id] = time.time()
        
        # Шаг 5: Сохранение на диск
        self._save_index(source_id)
        print(f"Index for {source_id} built successfully with {len(documents)} documents.")
    
    def build_index_for_company_faqs(self, csv_path: str) -> None:
        """Построение индекса для файла FAQ компании."""
        try:
            # Загружаем CSV файл
            df = pd.read_csv(csv_path)
            
            # Определяем разделитель, если это не стандартная запятая
            if len(df.columns) == 1:
                # Пробуем другой разделитель
                df = pd.read_csv(csv_path, sep=';')
            
            # Строим индекс
            self.build_index_from_dataframe(
                df=df,
                source_id="company_faqs",
                text_columns=["Question", "Answer"],
                metadata_columns=["Category"]
            )
            
        except Exception as e:
            print(f"Error building index for company FAQs: {e}")
    
    def search(
        self, 
        query: str, 
        source_id: str, 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Семантический поиск по индексу."""
        try:
            # Шаг 1: Проверяем наличие индекса
            if source_id not in self.indexes:
                # Пробуем загрузить индекс с диска
                if not self._load_index(source_id):
                    print(f"No index found for {source_id}")
                    return []
            
            # Шаг 2: Получаем эмбеддинг запроса
            query_embedding = self._get_embedding(query)
            query_vector = np.array([query_embedding]).astype('float32')
            
            # Шаг 3: Выполняем поиск по индексу
            distances, indices = self.indexes[source_id].search(query_vector, top_k)
            
            # Шаг 4: Формируем результаты
            results = []
            for i, doc_idx in enumerate(indices[0]):
                if doc_idx < 0 or doc_idx >= len(self.documents[source_id]):
                    continue  # Пропускаем невалидные индексы
                
                # Получаем оригинальный документ
                doc = self.documents[source_id][doc_idx].copy()
                
                # Добавляем оценку близости (преобразуем в диапазон 0-1)
                similarity = 1 / (1 + distances[0][i])
                doc["_score"] = float(similarity)
                
                # Удаляем служебные поля
                doc.pop("_source_id", None)
                doc.pop("_document_id", None)
                
                results.append(doc)
            
            return results
            
        except Exception as e:
            print(f"Error searching in {source_id}: {e}")
            return []
    
    def _save_index(self, source_id: str) -> bool:
        """Сохранение индекса на диск."""
        try:
            # Проверяем наличие индекса и данных
            if source_id not in self.indexes or source_id not in self.documents:
                return False
            
            # Создаем директорию если нужно
            index_path = self.index_dir / f"{source_id}.index"
            data_path = self.index_dir / f"{source_id}.data"
            
            # Сохраняем FAISS индекс
            faiss.write_index(self.indexes[source_id], str(index_path))
            
            # Сохраняем документы и метаданные
            with open(data_path, 'wb') as f:
                pickle.dump({
                    'documents': self.documents[source_id],
                    'last_updated': self.last_updated.get(source_id, time.time())
                }, f)
            
            return True
            
        except Exception as e:
            print(f"Error saving index {source_id}: {e}")
            return False
    
    def _load_index(self, source_id: str) -> bool:
        """Загрузка индекса с диска."""
        try:
            # Проверяем наличие файлов
            index_path = self.index_dir / f"{source_id}.index"
            data_path = self.index_dir / f"{source_id}.data"
            
            if not index_path.exists() or not data_path.exists():
                return False
            
            # Загружаем FAISS индекс
            self.indexes[source_id] = faiss.read_index(str(index_path))
            
            # Загружаем документы и метаданные
            with open(data_path, 'rb') as f:
                data = pickle.load(f)
                self.documents[source_id] = data['documents']
                self.last_updated[source_id] = data.get('last_updated', time.time())
            
            print(f"Loaded index {source_id} with {len(self.documents[source_id])} documents.")
            return True
            
        except Exception as e:
            print(f"Error loading index {source_id}: {e}")
            return False
    
    def list_indexes(self) -> List[Dict[str, Any]]:
        """Получение списка всех доступных индексов."""
        indexes = []
        
        # Проверяем сохраненные на диске индексы
        for file_path in self.index_dir.glob("*.index"):
            source_id = file_path.stem
            data_path = self.index_dir / f"{source_id}.data"
            
            if not data_path.exists():
                continue
            
            # Если индекс еще не загружен, загружаем его метаданные
            if source_id not in self.last_updated and data_path.exists():
                try:
                    with open(data_path, 'rb') as f:
                        data = pickle.load(f)
                        last_updated = data.get('last_updated', 0)
                        doc_count = len(data.get('documents', []))
                except Exception:
                    last_updated = 0
                    doc_count = 0
            else:
                last_updated = self.last_updated.get(source_id, 0)
                doc_count = len(self.documents.get(source_id, []))
            
            indexes.append({
                'id': source_id,
                'last_updated': last_updated,
                'doc_count': doc_count,
                'file_size': file_path.stat().st_size
            })
        
        return indexes

# Создаем глобальный экземпляр поискового движка
vector_search = VectorSearchEngine()