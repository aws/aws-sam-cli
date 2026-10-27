import io
from contextlib import redirect_stdout
from collections import OrderedDict
from unittest import TestCase

from samcli.commands._utils.table_print import pprint_column_names, pprint_columns

TABLE_FORMAT_STRING = "{Alpha:<{0}} {Beta:<{1}} {Gamma:<{2}}"
TABLE_FORMAT_ARGS = OrderedDict({"Alpha": "Alpha", "Beta": "Beta", "Gamma": "Gamma"})


class TestTablePrint(TestCase):
    def setUp(self):
        self.redirect_out = io.StringIO()

    def test_pprint_column_names(self):
        @pprint_column_names(TABLE_FORMAT_STRING, TABLE_FORMAT_ARGS)
        def to_be_decorated(*args, **kwargs):
            pass

        with redirect_stdout(self.redirect_out):
            to_be_decorated()
        output = (
            "------------------------------------------------------------------------------------------------\n"
            "Alpha                            Beta                             Gamma                          \n"
            "------------------------------------------------------------------------------------------------\n"
            "------------------------------------------------------------------------------------------------\n"
            "\n"
        )

        self.assertEqual(output, self.redirect_out.getvalue())

    def test_json_output_mode_skips_table_chrome(self):
        # In JSON mode the decorator must not print any table borders/headers to stdout; the wrapped
        # function owns its structured output.
        @pprint_column_names(TABLE_FORMAT_STRING, TABLE_FORMAT_ARGS)
        def to_be_decorated(*args, **kwargs):
            return kwargs.get("output_mode")

        with redirect_stdout(self.redirect_out):
            result = to_be_decorated(output_mode="json")

        self.assertEqual(self.redirect_out.getvalue(), "")
        self.assertEqual(result, "json")

    def test_unknown_output_mode_raises(self):
        # A typo (anything other than text/json) must fail loudly rather than silently fall through
        # to table output and corrupt a caller's JSON stream.
        @pprint_column_names(TABLE_FORMAT_STRING, TABLE_FORMAT_ARGS)
        def to_be_decorated(*args, **kwargs):
            pass

        with self.assertRaises(ValueError):
            to_be_decorated(output_mode="jsonn")

    def test_pprint_column_names_and_text(self):
        @pprint_column_names(TABLE_FORMAT_STRING, TABLE_FORMAT_ARGS)
        def to_be_decorated(*args, **kwargs):
            pprint_columns(
                columns=["A", "B", "C"],
                width=kwargs["width"],
                margin=kwargs["margin"],
                format_args=kwargs["format_args"],
                format_string=TABLE_FORMAT_STRING,
                columns_dict=TABLE_FORMAT_ARGS.copy(),
            )

        with redirect_stdout(self.redirect_out):
            to_be_decorated()

        output = (
            "------------------------------------------------------------------------------------------------\n"
            "Alpha                            Beta                             Gamma                          \n"
            "------------------------------------------------------------------------------------------------\n"
            "A                                B                                C                              \n"
            "------------------------------------------------------------------------------------------------\n"
            "\n"
        )
        self.assertEqual(output, self.redirect_out.getvalue())

    def test_pprint_exceptions_with_no_column_names(self):
        with self.assertRaises(ValueError):

            @pprint_column_names(TABLE_FORMAT_STRING, {})
            def to_be_decorated(*args, **kwargs):
                pprint_columns(
                    columns=["A", "B", "C"],
                    width=kwargs["width"],
                    margin=kwargs["margin"],
                    format_args=kwargs["format_args"],
                    format_string=TABLE_FORMAT_STRING,
                    columns_dict=TABLE_FORMAT_ARGS.copy(),
                )

    def test_pprint_exceptions_with_too_many_column_names(self):
        massive_dictionary = {str(i): str(i) for i in range(100)}
        with self.assertRaises(ValueError):

            @pprint_column_names(TABLE_FORMAT_STRING, massive_dictionary)
            def to_be_decorated(*args, **kwargs):
                pprint_columns(
                    columns=["A", "B", "C"],
                    width=kwargs["width"],
                    margin=kwargs["margin"],
                    format_args=kwargs["format_args"],
                    format_string=TABLE_FORMAT_STRING,
                    columns_dict=TABLE_FORMAT_ARGS.copy(),
                )
