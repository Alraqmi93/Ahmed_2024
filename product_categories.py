"""Multiple product categories with legacy single-category compatibility."""
import json

CATEGORIES=('books','fabric-books','board-books','cards','hardcover-books','toys')
BOOK_TYPES={'fabric-books','board-books','hardcover-books'}


def normalize_categories(value):
    if isinstance(value,str):value=json.loads(value) if value.startswith('[') else [value]
    if not isinstance(value,list) or not value or any(not isinstance(x,str) or x not in CATEGORIES for x in value):
        raise ValueError('Select at least one valid category / اختر فئة واحدة صالحة على الأقل')
    chosen=set(value)
    if chosen & BOOK_TYPES:chosen.add('books')
    return [key for key in CATEGORIES if key in chosen]


def stored_categories(value):
    categories=normalize_categories(value)
    return categories[0] if len(categories)==1 else json.dumps(categories)
