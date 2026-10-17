import unittest

from joy.folder import shorten_folder


class ShortenFolderTest(unittest.TestCase):
    def test_a_folder_that_fits_is_left_alone(self):
        self.assertEqual(shorten_folder("~/joy", 20), "~/joy")

    def test_a_long_folder_loses_its_middle_and_keeps_the_end(self):
        path = "~/Desktop/playground/AI/joy/plan-build-test/joy"
        self.assertEqual(shorten_folder(path, 25), "~/…/plan-build-test/joy")
        self.assertEqual(shorten_folder(path, 12), "~/…/joy")

    def test_an_absolute_folder_keeps_its_leading_slash(self):
        self.assertEqual(shorten_folder("/var/lib/some/deep/project", 18), "/…/deep/project")

    def test_a_very_narrow_room_still_fits(self):
        shortened = shorten_folder("~/a/very-long-project-name", 8)
        self.assertLessEqual(len(shortened), 8)
        self.assertTrue(shortened.endswith("name"))


if __name__ == "__main__":
    unittest.main()
