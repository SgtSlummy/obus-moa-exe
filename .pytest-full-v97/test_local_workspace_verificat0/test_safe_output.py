import unittest

class SafeOutput(unittest.TestCase):
    def test_output(self):
        print('API_KEY=not-for-models')
