from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto
from typing import Any, assert_never

from strenum import StrEnum

from bencher.results.float_formatter import FormatFloat


class Axis(StrEnum):
    """A spatial composition direction -- the only thing that has an opposite.

    ``ComposeType`` has two members that say *where* the next container goes
    (``right``/``down``) and two that do not (``sequence``/``overlay``).  Only the
    first pair can be flipped, so ``flip()`` lives here rather than on
    ``ComposeType``: asking a non-spatial compose type for its opposite is now
    unrepresentable instead of a ``RuntimeError`` raised mid-render
    (plan 23 C6, phase P8).

    The member values match the corresponding ``ComposeType`` values, so an ``Axis``
    compares equal to the ``ComposeType`` it maps to.
    """

    right = auto()  # append the container to the right (creates a row)
    down = auto()  # append the container below (creates a column)

    def flip(self) -> Axis:
        """Return the other axis.  Total by construction."""
        match self:
            case Axis.right:
                return Axis.down
            case Axis.down:
                return Axis.right
            case _ as unreachable:
                assert_never(unreachable)

    def to_compose_type(self) -> ComposeType:
        """Return the ``ComposeType`` that composes along this axis."""
        match self:
            case Axis.right:
                return ComposeType.right
            case Axis.down:
                return ComposeType.down
            case _ as unreachable:
                assert_never(unreachable)

    @staticmethod
    def from_horizontal(horizontal: bool) -> Axis:
        return Axis.right if horizontal else Axis.down


# TODO enable these options
class ComposeType(StrEnum):
    right = auto()  # append the container to the right (creates a row)
    down = auto()  # append the container below (creates a column)
    sequence = auto()  # display the container after (in time)
    overlay = auto()  # overlay on top of the current container (alpha blending)

    def as_axis(self) -> Axis | None:
        """The spatial axis this method composes along, or None if it has none.

        ``sequence`` and ``overlay`` place nothing beside anything, so they have no
        axis and nothing to flip -- hence ``None`` rather than a raise.
        """
        match self:
            case ComposeType.right:
                return Axis.right
            case ComposeType.down:
                return Axis.down
            case ComposeType.sequence | ComposeType.overlay:
                return None
            case _ as unreachable:
                assert_never(unreachable)

    @staticmethod
    def from_horizontal(horizontal: bool) -> ComposeType:
        return ComposeType.right if horizontal else ComposeType.down


def compose_method_list_for_dims(
    num_dims: int,
    first_compose_method: ComposeType | Axis = ComposeType.down,
    time_sequence_dimension: int = 0,
) -> list[ComposeType]:
    """Choose a composition method per dimension for a *num_dims*-dimensional sweep.

    By default the methods alternate between right and down (so nested dimensions
    stay readable) and a trailing sequence is appended for the level that varies
    fastest.  Levels up to *time_sequence_dimension* are forced to sequence.

    Args:
        num_dims (int): Number of dimensions being composed.
        first_compose_method (ComposeType | Axis, optional): Direction of the first
            composition. Defaults to ComposeType.down.  A method with no axis
            (``sequence``/``overlay``) cannot alternate, so it is repeated on every
            spatial level instead; before plan 23 P8 that combination raised
            ``RuntimeError`` from ``ComposeType.flip`` partway through rendering.
        time_sequence_dimension (int, optional): Compose dimensions up to this
            index in time rather than in space. ``-1`` sequences everything.
            Defaults to 0.

    Returns:
        list[ComposeType]: One composition method per level, consumed from the end.
    """
    if time_sequence_dimension == -1:  # use time sequence for everything
        return [ComposeType.sequence] * (num_dims + 1)

    if isinstance(first_compose_method, Axis):
        first = first_compose_method.to_compose_type()
        axis: Axis | None = first_compose_method
    else:
        first = first_compose_method
        axis = first_compose_method.as_axis()

    compose_method_list = [first]
    for _ in range(num_dims - 1):
        if axis is None:
            compose_method_list.append(first)
        else:
            axis = axis.flip()
            compose_method_list.append(axis.to_compose_type())
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
    def label_formatter(var_name: str | None, var_value: float | str | None) -> str | None:
        """Take a variable name and values and return a pretty version with approximate fixed width

        Args:
            var_name (str | None): The name of the variable, usually a dimension
            var_value (int | float | str | None): The value of the dimension

        Returns:
            str | None: Pretty string representation with fixed width, or None when
                neither a name nor a value was given (every caller tests for None).
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
