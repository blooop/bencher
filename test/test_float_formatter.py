import unittest

from bencher.results.float_formatter import FormatFloat


class TestFormatFloat(unittest.TestCase):
    def test_all(self):
        test = (
            ("1234567.", 1234567),
            ("-123456.", -123456),
            ("1.23e+13", 12345678901234),
            ("123.4567", 123.4567),
            ("123.4568", 123.45678),
            ("1.234568", 1.2345678),
            ("0.123457", 0.12345678),
            ("   1234.", 1234),
            ("1.235e+7", 12345678),
            ("-1.23e+6", -1234567),
        )

        width = 8
        ff8 = FormatFloat(width)

        for expected, given in test:
            output = ff8(given)
            self.assertEqual(len(output), width, msg=output)
            self.assertEqual(output, expected, msg=given)
