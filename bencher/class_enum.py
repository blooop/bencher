from __future__ import annotations
from strenum import StrEnum
from typing import Any, TypeVar
import importlib
from abc import abstractmethod
from dataclasses import dataclass
from enum import auto

T = TypeVar("T")  # Generic type for return value of to_class


class ClassEnum(StrEnum):
    """A string-based enum class that maps enum values to corresponding class instances.

    ClassEnum is a pattern to make it easier to create a factory method that converts
    from an enum value to a corresponding class instance. Subclasses should implement
    the to_class() method which takes an enum value and returns an instance of the
    corresponding class.

    This pattern is useful for configuration-driven class instantiation, allowing
    classes to be selected via string configuration values that match enum names.
    """

    @classmethod
    def to_class_generic(cls, module_import: str, class_name: str) -> Any:
        """Create an instance of a class from its module path and class name.

        This utility method dynamically imports a module and instantiates a class from it.

        Args:
            module_import (str): The module path to import (e.g., "bencher.class_enum")
            class_name (str): The name of the class to instantiate

        Returns:
            Any: A new instance of the specified class
        """
        class_def = getattr(importlib.import_module(module_import), class_name)
        return class_def()

    @classmethod
    @abstractmethod
    def to_class(cls, enum_val: ClassEnum) -> Any:
        """Convert an enum value to its corresponding class instance.

        Subclasses must override this method to implement the mapping from
        enum values to class instances.

        Args:
            enum_val (ClassEnum): The enum value to convert to a class instance

        Returns:
            Any: An instance of the class corresponding to the enum value

        Raises:
            NotImplementedError: If this method is not overridden by a subclass
        """
        raise NotImplementedError("Subclasses must implement to_class()")


@dataclass
class BaseClass:
    """Base class for the ClassEnum example.

    A simple dataclass that serves as the base class for the ClassEnum example classes.

    Attributes:
        baseclassname (str): A name for the base class
    """

    baseclassname: str = "class0"


@dataclass
class Class1(BaseClass):
    """Example subclass 1 for the ClassEnum demonstration.

    Attributes:
        classname (str): A name for this class
    """

    classname: str = "class1"


@dataclass
class Class2(BaseClass):
    """Example subclass 2 for the ClassEnum demonstration.

    Attributes:
        classname (str): A name for this class
    """

    classname: str = "class2"


class ExampleEnum(ClassEnum):
    """An example implementation of ClassEnum.

    This enum demonstrates how to use ClassEnum to map enum values to class instances.
    Each enum value corresponds to a class name that can be instantiated.
    """

    Class1 = auto()
    Class2 = auto()

    @classmethod
    def to_class(cls, enum_val: ExampleEnum) -> BaseClass:
        """Convert an ExampleEnum value to its corresponding class instance.

        Args:
            enum_val (ExampleEnum): The enum value to convert

        Returns:
            BaseClass: An instance of either Class1 or Class2, depending on the enum value
        """
        return cls.to_class_generic("bencher.class_enum", enum_val)
