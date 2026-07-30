from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto
from typing import Any

from strenum import StrEnum

from bencher.results.float_formatter import FormatFloat


# TODO enable these options
class ComposeType(StrEnum):
    right = auto()  # append the container to the right (creates a row)
    down = auto()  # append the container below (creates a column)
    sequence = auto()  # display the container after (in time)
    overlay = auto()  # overlay on top of the current container (alpha blending)

    def flip(self):
        match self:
            case ComposeType.right:
                return ComposeType.down
            case ComposeType.down:
                return ComposeType.right
            case _:
                raise RuntimeError("cannot flip this type")

    @staticmethod
    def from_horizontal(horizontal: bool):
        return ComposeType.right if horizontal else ComposeType.down


def compose_method_list_for_dims(
    num_dims: int,
    first_compose_method: ComposeType = ComposeType.down,
    time_sequence_dimension: int = 0,
) -> list[ComposeType]:
    """Choose a composition method per dimension for a *num_dims*-dimensional sweep.

    By default the methods alternate between right and down (so nested dimensions
    stay readable) and a trailing sequence is appended for the level that varies
    fastest.  Levels up to *time_sequence_dimension* are forced to sequence.

    Args:
        num_dims (int): Number of dimensions being composed.
        first_compose_method (ComposeType, optional): Direction of the first
            composition. Defaults to ComposeType.down.
        time_sequence_dimension (int, optional): Compose dimensions up to this
            index in time rather than in space. ``-1`` sequences everything.
            Defaults to 0.

    Returns:
        list[ComposeType]: One composition method per level, consumed from the end.
    """
    if time_sequence_dimension == -1:  # use time sequence for everything
        return [ComposeType.sequence] * (num_dims + 1)

    compose_method_list = [first_compose_method]
    compose_method_list.extend(
        ComposeType.flip(compose_method_list[-1]) for _ in range(num_dims - 1)
    )
    compose_method_list.append(ComposeType.sequence)

    for i in range(min(len(compose_method_list), time_sequence_dimension + 1)):
        compose_method_list[i] = ComposeType.sequence

    return compose_method_list


class PaneLayout(StrEnum):
    """Controls how multi-dimensional data is laid out in panel displays.

    grid: Use rows/columns for all dimensions (default, existing behavior)
    tabs: Use tabs for all outer dimensions, only the innermost uses grid
    tabs_and_grid: Use tabs for the outermost dimension, grid for inner dimensions
    """

    grid = auto()
    tabs = auto()
    tabs_and_grid = auto()

    @classmethod
    def all(cls) -> list[PaneLayout]:
        """Return all layout values.  Use this instead of hard-coded name lists."""
        return list(cls)


@dataclass(kw_only=True)
class ComposableContainerBase:
    """A base class for renderer backends.  A composable renderer"""

    compose_method: ComposeType = ComposeType.right
    container: list[Any] = field(default_factory=list)
    label_len: int = 0

    @staticmethod
    def label_formatter(var_name: str, var_value: float | str) -> str:
        """Take a variable name and values and return a pretty version with approximate fixed width

        Args:
            var_name (str): The name of the variable, usually a dimension
            var_value (int | float | str): The value of the dimension

        Returns:
            str: Pretty string representation with fixed width
        """

        if isinstance(var_value, (int, float)):
            var_value = FormatFloat()(var_value)
        if var_name is not None and var_value is not None:
            return f"{var_name}={var_value}"
        if var_name is not None:
            return f"{var_name}"
        if var_value is not None:
            return f"{var_value}"
        return None

    def append(self, obj: Any) -> None:
        """Add an object to the container.  The relationship between the objects is defined by the ComposeType

        Args:
            obj (Any): Object to add to the container
        """
        self.container.append(obj)

    def render(self):
        """Return a representation of the container that can be composed with other render() results. This function can also be used to defer layout and rending options until all the information about the container content is known.  You may need to override this method depending on the container. See composable_container_video as an example.

        Returns:
            Any: Visual representation of the container that can be combined with other containers
        """
        return self.container
