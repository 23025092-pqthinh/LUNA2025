from typing import TypeVar, Generic, List, Type
from sqlalchemy.orm import Query
from sqlalchemy import desc, asc
from ..schemas import Page

T = TypeVar("T")

class Paginator(Generic[T]):
    """Helper for paginating SQLAlchemy queries with filtering and sorting"""
    
    def __init__(self, query: Query, page: int = 1, page_size: int = 50):
        self.query = query
        self.page = max(1, page)
        self.page_size = min(100, max(1, page_size))
        
    def filter_by(self, **kwargs):
        """Add filter conditions, skipping None values"""
        for k, v in kwargs.items():
            if v is not None:
                self.query = self.query.filter(getattr(self.model, k) == v)
        return self
        
    def order_by(self, *criteria):
        """Add ORDER BY clause. Use string with '-' prefix for DESC"""
        for c in criteria:
            if isinstance(c, str):
                if c.startswith('-'):
                    self.query = self.query.order_by(desc(c[1:]))
                else:
                    self.query = self.query.order_by(asc(c))
            else:
                self.query = self.query.order_by(c)
        return self
    
    def execute(self) -> Page[T]:
        """Execute query and return Page object"""
        total = self.query.count()
        items = (self.query.offset((self.page - 1) * self.page_size)
                          .limit(self.page_size)
                          .all())
        return Page(
            items=items,
            total=total,
            page=self.page,
            page_size=self.page_size
        )