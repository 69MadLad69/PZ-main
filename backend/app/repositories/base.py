from __future__ import annotations

from typing import Generic, Iterator, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):

    def __init__(self, model: Type[ModelT], db: Session) -> None:
        self.model = model
        self.db = db

    def create(self, **kwargs) -> ModelT:
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.flush()
        return instance

    def bulk_create(self, records: List[dict]) -> None:
        self.db.bulk_insert_mappings(self.model, records)
        self.db.flush()

    def get(self, pk: int) -> Optional[ModelT]:
        return self.db.get(self.model, pk)

    def get_or_raise(self, pk: int) -> ModelT:
        obj = self.get(pk)
        if obj is None:
            raise ValueError(f"{self.model.__name__} with id={pk} not found")
        return obj

    def all(self) -> List[ModelT]:
        return list(self.db.scalars(select(self.model)))

    def count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(self.model)) or 0

    def filter_by(self, **kwargs) -> List[ModelT]:
        stmt = select(self.model).filter_by(**kwargs)
        return list(self.db.scalars(stmt))

    def first_by(self, **kwargs) -> Optional[ModelT]:
        stmt = select(self.model).filter_by(**kwargs).limit(1)
        return self.db.scalars(stmt).first()

    def update(self, pk: int, **kwargs) -> ModelT:
        instance = self.get_or_raise(pk)
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.db.flush()
        return instance

    def delete(self, pk: int) -> None:
        instance = self.get_or_raise(pk)
        self.db.delete(instance)
        self.db.flush()

    def iter_chunks(self, chunk_size: int = 1000) -> Iterator[List[ModelT]]:
        """Memory-efficient iteration over large tables."""
        offset = 0
        while True:
            stmt = select(self.model).offset(offset).limit(chunk_size)
            rows = list(self.db.scalars(stmt))
            if not rows:
                break
            yield rows
            offset += chunk_size
