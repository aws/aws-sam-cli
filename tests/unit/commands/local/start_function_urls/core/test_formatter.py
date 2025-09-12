"""
Unit tests for start-function-urls core formatters
"""

from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.local.start_function_urls.core.formatters import InvokeFunctionUrlsCommandHelpTextFormatter
from samcli.cli.row_modifiers import BaseLineRowModifier


class TestInvokeFunctionUrlsCommandHelpTextFormatter(TestCase):
    """Test InvokeFunctionUrlsCommandHelpTextFormatter class"""
    
    def test_formatter_initialization(self):
        """Test formatter initialization with default values"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter()
        
        # Check that ADDITIVE_JUSTIFICATION is set
        self.assertEqual(formatter.ADDITIVE_JUSTIFICATION, 6)
        
        # Check that modifiers list contains BaseLineRowModifier
        self.assertEqual(len(formatter.modifiers), 1)
        self.assertIsInstance(formatter.modifiers[0], BaseLineRowModifier)
    
    @patch('samcli.commands.local.start_function_urls.core.formatters.ALL_OPTIONS', 
           ['--short', '--medium-option', '--very-long-option-name'])
    def test_left_justification_calculation(self):
        """Test left justification length calculation"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=100)
        
        # The longest option is '--very-long-option-name' (23 chars)
        # Plus ADDITIVE_JUSTIFICATION (6) = 29
        # But it should not exceed width // 2 - indent_increment
        # width=100, so max is 50 - indent_increment
        expected_max = 50 - formatter.indent_increment
        expected_length = min(23 + 6, expected_max)
        
        self.assertEqual(formatter.left_justification_length, expected_length)
    
    @patch('samcli.commands.local.start_function_urls.core.formatters.ALL_OPTIONS', 
           ['--a', '--b', '--c'])
    def test_left_justification_with_short_options(self):
        """Test left justification with short option names"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=80)
        
        # The longest option is '--a' (3 chars)
        # Plus ADDITIVE_JUSTIFICATION (6) = 9
        self.assertEqual(formatter.left_justification_length, 9)
    
    @patch('samcli.commands.local.start_function_urls.core.formatters.ALL_OPTIONS', 
           ['--extremely-very-super-long-option-name-that-is-too-long'])
    def test_left_justification_max_limit(self):
        """Test that left justification respects max width limit"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=80)
        
        # Even with a very long option, it should not exceed width // 2 - indent_increment
        max_allowed = 40 - formatter.indent_increment
        
        self.assertLessEqual(formatter.left_justification_length, max_allowed)
    
    def test_formatter_inherits_from_root_formatter(self):
        """Test that formatter inherits from RootCommandHelpTextFormatter"""
        from samcli.cli.formatters import RootCommandHelpTextFormatter
        
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter()
        self.assertIsInstance(formatter, RootCommandHelpTextFormatter)
    
    @patch('samcli.commands.local.start_function_urls.core.formatters.ALL_OPTIONS', [])
    def test_formatter_with_no_options(self):
        """Test formatter initialization when ALL_OPTIONS is empty"""
        # When ALL_OPTIONS is empty, max([]) will raise ValueError
        # The formatter code needs to be fixed to handle this, but for now
        # we'll test that it raises the expected error
        with self.assertRaises(ValueError) as context:
            formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=100)
        
        # The error message varies between Python versions
        error_msg = str(context.exception)
        self.assertTrue(
            "max() arg is an empty sequence" in error_msg or 
            "max() iterable argument is empty" in error_msg,
            f"Unexpected error message: {error_msg}"
        )
    
    def test_formatter_with_custom_width(self):
        """Test formatter with custom terminal width"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=120)
        
        # Width should affect the max justification length
        max_allowed = 60 - formatter.indent_increment  # 120 // 2
        self.assertLessEqual(formatter.left_justification_length, max_allowed)
    
    def test_formatter_with_very_narrow_width(self):
        """Test formatter with very narrow terminal width"""
        formatter = InvokeFunctionUrlsCommandHelpTextFormatter(width=40)
        
        # Even with narrow width, formatter should work
        max_allowed = 20 - formatter.indent_increment  # 40 // 2
        self.assertLessEqual(formatter.left_justification_length, max_allowed)
