import os
import unittest

os.environ.setdefault("ICS_INPUT_URL", "https://example.invalid/calendar.ics")

from app import repair_ics


class RepairTests(unittest.TestCase):
    def test_repairs_raw_newline_escapes_text_and_prefixes_summary(self):
        source = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
            "UID:1\r\nSUMMARY:Cours\r\n"
            "DESCRIPTION:Nom A., Nom B. - Extérieur\r\n2A, 2B\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        ).encode()
        result = repair_ics(source, "CUSTOM - ").decode()
        unfolded = result.replace("\r\n ", "")
        self.assertIn("SUMMARY:CUSTOM - Cours\r\n", unfolded)
        self.assertIn("DESCRIPTION:Nom A.\\, Nom B. - Extérieur\\n2A\\, 2B\r\n", unfolded)
        self.assertNotIn("\r\n2A", result)
        self.assertTrue(all(len(line.encode()) <= 75 for line in result.split("\r\n")))

    def test_preserves_existing_escapes(self):
        source = b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:A\\, B\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
        result = repair_ics(source, "").decode()
        self.assertIn("SUMMARY:A\\, B", result)
        self.assertNotIn("SUMMARY:A\\\\, B", result)

    def test_rejects_malformed_non_text_property(self):
        source = b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nbroken\r\nEND:VCALENDAR\r\n"
        with self.assertRaises(ValueError):
            repair_ics(source, "")


if __name__ == "__main__":
    unittest.main()
