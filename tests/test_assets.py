import os
import unittest

from screen_guard import assets


class AssetTests(unittest.TestCase):
    def test_logo_png_exists(self):
        path = assets.logo_png()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))

    def test_logo_ico_exists(self):
        path = assets.logo_ico()
        self.assertIsNotNone(path)
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
