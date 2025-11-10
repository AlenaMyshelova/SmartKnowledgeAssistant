from __future__ import annotations
from app.vector_search import vector_search

from pathlib import Path
from typing import List, Dict, Any, Optional

import os
import pandas as pd


class DataManager:
    """
    Класс-обёртка над локальными FAQ-данными компании с векторным поиском.

    Возможности:
    - Надёжная загрузка CSV относительно текущего файла (а не текущей рабочей директории).
    - Fallback разделителя: сперва пробуем ';', затем ','.
    - Поиск по колонкам Category / Question / Answer (чувствительность к регистру выключена).
    - Векторный семантический поиск с использованием FAISS и OpenAI embeddings.
    - Получение всех категорий и данных по категории.
    - Возврат метаданных по источникам (колонки, число записей).
    """

    def __init__(
        self,
        # Путь по умолчанию: ../data/company_faqs.csv относительно данного файла
        company_faqs_relpath: str = "../data/company_faqs.csv",
        encoding: str = "utf-8",
    ) -> None:
        self.encoding = encoding
        self.data_sources: Dict[str, pd.DataFrame] = {}
        
        # Абсолютный путь к CSV относительно местоположения этого файла
        base_dir = Path(__file__).resolve().parent
        self.company_faqs_path: Path = (base_dir / company_faqs_relpath).resolve()
        
        # Директория для загружаемых пользователями файлов
        self.upload_dir = Path(company_faqs_relpath).parent / "uploaded_files"
        self.upload_dir.mkdir(exist_ok=True, parents=True)

        # Разрешаем переопределение путей через переменные окружения (опционально)
        env_override = os.getenv("COMPANY_FAQS_PATH")
        if env_override:
            self.company_faqs_path = Path(env_override).expanduser().resolve()

        # Загружаем данные
        self.load_company_faqs()
        
        # Создаем векторный индекс для FAQ, если еще нет
        self._ensure_faq_index()

    # -------------------
    # Загрузка данных
    # -------------------
    def _read_csv_with_fallback(self, path: Path) -> pd.DataFrame:
        """
        Пробуем прочитать CSV сперва с sep=';', затем с sep=','.
        Бросаем исключение дальше, если оба варианта не сработали.
        """
        last_err: Optional[Exception] = None

        for sep in (";", ","):
            try:
                return pd.read_csv(path, sep=sep, encoding=self.encoding)
            except Exception as e:
                last_err = e  # пробуем следующий разделитель

        # Если дошли сюда — оба способа не сработали
        raise RuntimeError(f"Failed to read CSV at {path}: {last_err}")

    def load_company_faqs(self) -> None:
        """Загрузка FAQ из CSV в память."""
        try:
            if self.company_faqs_path.exists():
                df = self._read_csv_with_fallback(self.company_faqs_path)

                # Нормализуем ожидаемые колонки (минимальный контракт)
                expected = {"Category", "Question", "Answer"}
                missing = expected - set(df.columns)
                if missing:
                    raise ValueError(
                        f"CSV {self.company_faqs_path} is missing required columns: {sorted(missing)}"
                    )

                # Приводим строки к str (на случай NaN), чтобы избежать ошибок при .str.lower()
                for col in ("Category", "Question", "Answer"):
                    df[col] = df[col].astype(str)

                self.data_sources["company_faqs"] = df

                print(
                    f"Loaded {len(df)} FAQ records from {self.company_faqs_path}"
                )
                # Небольшая выборка для визуальной проверки
                with pd.option_context("display.max_colwidth", 120):
                    print("Sample data:")
                    print(df.head(2))
            else:
                print(f"company_faqs.csv not found at: {self.company_faqs_path}")
        except Exception as e:
            print(f"Error loading company_faqs.csv from {self.company_faqs_path}: {e}")
    
    # Проверка и создание векторного индекса
    def _ensure_faq_index(self) -> None:
        """Проверка наличия и актуальности векторного индекса для FAQ."""
        try:
            # Проверяем существует ли индекс
            index_exists = False
            for index_info in vector_search.list_indexes():
                if index_info['id'] == 'company_faqs':
                    index_exists = True
                    break
            
            # Если индекса нет или файл FAQ новее, создаем новый индекс
            if not index_exists or (
                self.company_faqs_path.exists() and 
                self.company_faqs_path.stat().st_mtime > vector_search.last_updated.get('company_faqs', 0)
            ):
                print("Building vector index for company FAQs...")
                vector_search.build_index_for_company_faqs(str(self.company_faqs_path))
        
        except Exception as e:
            print(f"Error ensuring FAQ index: {e}")

    # -------------------
    # Поиск и выборки
    # -------------------
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск по FAQ с использованием векторного поиска.
        Если векторный поиск не дал результатов, используется стандартный текстовый поиск.
        
        Args:
            query: поисковый запрос пользователя
            limit: максимальное число результатов
            
        Returns:
            Список найденных FAQ с оценкой релевантности
        """
        try:
            # Проверяем наличие индекса и пробуем векторный поиск
            self._ensure_faq_index()
            results = vector_search.search(query, 'company_faqs', top_k=limit)
            
            # Если векторный поиск дал результаты, возвращаем их
            if results:
                return results
                
            # Если нет результатов, используем традиционный поиск
            print("No vector search results, falling back to text search")
            return self._fallback_text_search(query, limit)
            
        except Exception as e:
            print(f"Error in vector search: {e}")
            # В случае ошибки векторного поиска используем текстовый
            return self._fallback_text_search(query, limit)
    
    #  Резервный текстовый поиск
    def _fallback_text_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Резервный текстовый поиск (оригинальная реализация)."""
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
        
        # Добавляем фиктивную оценку релевантности для совместимости с векторным поиском
        for record in records:
            record["_score"] = 0.5
            
        return records
    
    # Поиск в загруженных пользовательских файлах
    def search_uploaded_file(self, query: str, file_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск по загруженному файлу с использованием векторного поиска.
        
        Args:
            query: поисковый запрос
            file_id: идентификатор файла
            limit: максимальное число результатов
            
        Returns:
            Список найденных строк с оценкой релевантности
        """
        try:
            # Формируем идентификатор источника
            source_id = f"uploaded_{file_id}"
            
            # Проверяем наличие индекса
            index_exists = False
            for index_info in vector_search.list_indexes():
                if index_info['id'] == source_id:
                    index_exists = True
                    break
            
            # Если индекса нет, создаем его
            if not index_exists:
                file_path = self.upload_dir / f"{file_id}.csv"
                if file_path.exists():
                    print(f"Building vector index for uploaded file {file_id}...")
                    vector_search.build_index_for_uploaded_file(file_id, str(file_path))
                else:
                    print(f"File not found: {file_id}")
                    return []
            
            # Выполняем векторный поиск
            results = vector_search.search(query, source_id, top_k=limit)
            return results
            
        except Exception as e:
            print(f"Error in search_uploaded_file: {e}")
            return []

    def get_all_data_sources(self) -> Dict[str, Any]:
        """
        Метаданные по всем загруженным источникам: 
        число записей, список колонок и наличие векторного индекса.
        """
        info: Dict[str, Any] = {}
        
        # Обрабатываем стандартные источники
        for name, df in self.data_sources.items():
            info[name] = {
                "records_count": int(len(df)),
                "columns": list(df.columns),
                "path": str(self.company_faqs_path) if name == "company_faqs" else None,
                "has_vector_index": name in {idx["id"] for idx in vector_search.list_indexes()}
            }
        
        # Добавляем загруженные пользователем файлы
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
        """Вернуть все записи FAQ по точному совпадению категории (без учёта регистра)."""
        df = self.data_sources.get("company_faqs")
        if df is None or df.empty:
            return []

        c = (category or "").strip().lower()
        if not c:
            return []

        results = df[df["Category"].str.lower() == c]
        return results.to_dict("records")

    def get_all_categories(self) -> List[str]:
        """Список уникальных категорий (как есть в данных)."""
        df = self.data_sources.get("company_faqs")
        if df is None or df.empty:
            return []
        # Убираем пустые/NaN, приводим к str
        cats = df["Category"].dropna().astype(str).unique().tolist()
        return cats

    # -------------------
    # Дополнительно
    # -------------------
    def reload(self) -> None:
        """Перезагрузить данные из CSV и обновить векторные индексы."""
        self.load_company_faqs()
        # Обновляем векторный индекс после перезагрузки данных
        self._ensure_faq_index()