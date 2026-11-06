import unittest
from product_categories import normalize_categories,stored_categories


class CategoriesTest(unittest.TestCase):
    def test_legacy_and_parent_book_membership(self):
        self.assertEqual(normalize_categories('books'),['books'])
        self.assertEqual(normalize_categories('fabric-books'),['books','fabric-books'])
        self.assertEqual(normalize_categories(['toys','fabric-books','fabric-books']),['books','fabric-books','toys'])
        self.assertEqual(normalize_categories(stored_categories(['cards','books'])),['books','cards'])
    def test_requires_valid_selection(self):
        for value in [[],None,{},['unknown'],['books',None]]:
            with self.assertRaises(ValueError):normalize_categories(value)
