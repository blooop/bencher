import unittest

import bencher as bn


class TestClassEnum(unittest.TestCase):
    def test_basic(self):
        instance1 = bn.ExampleEnum.to_class(bn.ExampleEnum.Class1)
        assert instance1.classname == "class1"
        instance2 = bn.ExampleEnum.to_class(bn.ExampleEnum.Class2)
        assert instance2.classname == "class2"
