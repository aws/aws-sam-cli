from unittest import TestCase

from samcli.cli.row_modifiers import (
    RowDefinition,
    BaseLineRowModifier,
    HighlightNewRowNameModifier,
    ShowcaseRowModifier,
)


class TestRowModifier(TestCase):
    def setUp(self) -> None:
        self.justification_length = 10
        self.row = RowDefinition(name="Name", text="Text")

    def test_base_line_row_modifier(self):
        modifier = BaseLineRowModifier()
        result = modifier.apply(self.row, self.justification_length)

        self.assertEqual(result.name, "Name      ")
        self.assertEqual(result.text, "Text")

    def test_highlight_new_row_name_modifier(self):
        modifier = HighlightNewRowNameModifier()
        result = modifier.apply(self.row, self.justification_length)

        self.assertIn("Name NEW!", result.name)
        self.assertEqual(result.text, "Text")

    def test_showcase_row_modifier(self):
        modifier = ShowcaseRowModifier()
        result = modifier.apply(self.row, self.justification_length)

        self.assertEqual(result.name, f"\x1b[32m{self.row.name}      \x1b[0m")
        self.assertEqual(result.text, f"\x1b[32m{self.row.text}\x1b[0m")
