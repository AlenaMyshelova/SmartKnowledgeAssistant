from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

import os
import pandas as pd


class DataManager:
    """
    Класс-обёртка над локальными FAQ-данными компании.

    Возможности:
    - Надёжная загрузка CSV относительно текущего файла (а не текущей рабочей директории).
    - Fallback разделителя: сперва пробуем ';', затем ','.
    - Поиск по колонкам Category / Question / Answer (чувствительность к регистру выключена).
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

        # Разрешаем переопределение путей через переменные окружения (опционально)
        env_override = os.getenv("COMPANY_FAQS_PATH")
        if env_override:
            self.company_faqs_path = Path(env_override).expanduser().resolve()

        self.load_company_faqs()

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

    # -------------------
    # Поиск и выборки
    # -------------------
    def search_faqs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск простым полнотекстовым фильтром в колонках:
        - Category
        - Question
        - Answer
        Возвращает первые `limit` совпадений.
        """
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
        return results.to_dict("records")

    def get_all_data_sources(self) -> Dict[str, Any]:
        """Метаданные по всем загруженным источникам: число записей и список колонок."""
        info: Dict[str, Any] = {}
        for name, df in self.data_sources.items():
            info[name] = {
                "records_count": int(len(df)),
                "columns": list(df.columns),
                "path": str(self.company_faqs_path) if name == "company_faqs" else None,
            }
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
        """Перезагрузить данные из CSV (можно повесить на админ-кнопку)."""
        self.load_company_faqs()