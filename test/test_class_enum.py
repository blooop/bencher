import unittest
import bencher as bn


class TestClassEnum(unittest.TestCase):
    def test_basic(self):
        instance1 = bn.ExampleEnum.to_class(bn.ExampleEnum.Class1)
        self.assertEqual(instance1.classname, "class1")
        instance2 = bn.ExampleEnum.to_class(bn.ExampleEnum.Class2)
        self.assertEqual(instance2.classname, "class2")
