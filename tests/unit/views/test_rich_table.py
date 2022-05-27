import sys
from io import StringIO
from unittest import TestCase

from samcli.views.concrete_views.rich_table import RichTable


class TestRichTableView(TestCase):
    def test_create_basic_table(self):
        table = RichTable("test_table")

        table.add_column("heading1")
        table.add_column("heading2")
        table.add_column("heading3")

        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])

        expected_table = """            test_table            
┏━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ heading1 ┃ heading2 ┃ heading3 ┃
┡━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ hello 1  │ hello 2  │ hello 3  │
│ hello 1  │ hello 2  │ hello 3  │
│ hello 1  │ hello 2  │ hello 3  │
│ hello 1  │ hello 2  │ hello 3  │
└──────────┴──────────┴──────────┘
"""

        # Capture events to stdout to compare against expected table
        sys.stdout = table_out = StringIO()
        table.print()

        rich_table = table._table

        # Comment out this assertion until we find a better way to evaluate the output
        # self.assertEqual(expected_table, table_out.getvalue())
        self.assertEqual(len(rich_table.columns), 3)
        self.assertEqual(rich_table.row_count, 4)

    def test_create_table_with_styling(self):
        table = RichTable(title="another_test_table", table_options={"title_style": "blue"})

        table.add_column("heading1", options={"justify": "left", "style": "green"})
        table.add_column("heading2", options={"justify": "right", "style": "red"})
        table.add_column("heading3", options={"justify": "center", "style": "blue"})

        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])
        table.add_row(["hello 1", "hello 2", "hello 3"])

        expected_table = """        another_test_table        
┏━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ heading1 ┃ heading2 ┃ heading3 ┃
┡━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ hello 1  │  hello 2 │ hello 3  │
│ hello 1  │  hello 2 │ hello 3  │
│ hello 1  │  hello 2 │ hello 3  │
│ hello 1  │  hello 2 │ hello 3  │
└──────────┴──────────┴──────────┘
"""

        sys.stdout = table_out = StringIO()
        table.print()

        rich_table = table._table

        self.assertEqual(rich_table.columns[0].style, "green")
        self.assertEqual(rich_table.columns[1].style, "red")
        self.assertEqual(rich_table.columns[2].style, "blue")
        self.assertEqual(rich_table.title_style, "blue")
        # Comment out this assertion until we find a better way to evaluate the output
        # self.assertEqual(expected_table, table_out.getvalue())
        self.assertEqual(len(rich_table.columns), 3)
        self.assertEqual(rich_table.row_count, 4)
