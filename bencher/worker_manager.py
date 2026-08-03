"""Worker management for benchmarking.

This module provides the WorkerManager class for handling worker function
configuration and validation in benchmark runs, and the :data:`WorkerState` sum
type that models what a manager is holding at any moment (plan 23 P9, C7).
"""

from __future__ import annotations

import logging
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import assert_never

from param import Parameter

from bencher.variables.parametrised_sweep import ParametrizedSweep

logger = logging.getLogger(__name__)


def kwargs_to_input_cfg(worker_input_cfg: type[ParametrizedSweep], **kwargs) -> ParametrizedSweep:
    """Create a configured instance of a ParametrizedSweep with the provided keyword arguments.

    ``worker_input_cfg`` is a *class*, and always was: every caller passes one (the
    docstrings said "class" while the annotation said instance) and the body
    instantiates it. Annotated honestly here as part of putting this module on the
    strict `ty` list -- with the old annotation, ``worker_input_cfg()`` reads as
    ``ParametrizedSweep.__call__``, i.e. a ``dict``, and the next line is an error.
    ``bencher.py`` and ``sweep_executor.py`` still carry the instance annotation on
    their pass-through parameters; correcting those is for whenever they join the
    strict list.

    Args:
        worker_input_cfg (type[ParametrizedSweep]): The ParametrizedSweep class to instantiate
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        ParametrizedSweep: A configured instance of the worker_input_cfg class
    """
    input_cfg = worker_input_cfg()
    input_cfg.param.update(kwargs)
    return input_cfg


def worker_cfg_wrapper(
    worker: Callable, worker_input_cfg: type[ParametrizedSweep], **kwargs
) -> dict:
    """Wrap a worker function to accept keyword arguments instead of a config object.

    This wrapper creates an instance of the worker_input_cfg class, updates it with the
    provided keyword arguments, and passes it to the worker function.

    Args:
        worker (Callable): The worker function that expects a config object
        worker_input_cfg (type[ParametrizedSweep]): The class defining the configuration
        **kwargs: Keyword arguments to update the configuration with

    Returns:
        dict: The result of calling the worker function with the configured input
    """
    input_cfg = kwargs_to_input_cfg(worker_input_cfg, **kwargs)
    return worker(input_cfg)


@dataclass(frozen=True)
class Unbound:
    """Nothing attached yet -- what a fresh :class:`WorkerManager` holds.

    Neither callable nor declaring: every read of the sweep's variables raises from
    here, naming the method to call (this is setup time, before any sample has been
    collected, so raising loses nothing).
    """


@dataclass(frozen=True)
class Declared:
    """A worker *class*, attached by :meth:`WorkerManager.set_worker_class`.

    Declaring but not callable. Everything the declaration path needs is class-level
    (``param.objects()`` plus the ``get_inputs_only`` / ``get_input_defaults`` /
    ``get_results_only`` classmethods), so this state can describe and hash a sweep;
    what it cannot do is run one, which is why ``worker`` reads back as ``None``.
    """

    worker_class: type[ParametrizedSweep]


@dataclass(frozen=True)
class RunnableFunction:
    """A plain callable worker -- a function, a bound method, or a ``partial``.

    Callable but not declaring: no ``ParametrizedSweep`` is attached, so the sweep's
    variables have to come from the caller (``input_vars`` / ``result_vars`` /
    ``const_vars`` on ``plot_sweep``). ``worker_input_cfg`` is folded into ``fn`` as a
    ``partial`` at bind time and deliberately does *not* become a declaration source:
    it never was one, and making it one would silently switch on ``plot_sweep``'s
    auto-discovery for every function-plus-config caller.
    """

    fn: Callable


@dataclass(frozen=True)
class RunnableInstance:
    """A ``ParametrizedSweep`` instance: callable *and* the declaration source.

    The common case. ``worker`` is the instance's bound ``__call__``, and the same
    instance answers what inputs, results and defaults the sweep is made of.
    """

    instance: ParametrizedSweep


# The states a WorkerManager can be in (plan 23 P9, C7). Previously one
# `worker_class_instance: ParametrizedSweep | type[ParametrizedSweep] | None` field
# carried all four, with "declaration only" inferred from `worker is None` and three
# `RuntimeError("Worker class instance not set")` sites standing in for the missing
# type. Note this is *four* variants, not the three plan 23 P9 sketched: callability
# and declaring-ness are independent axes, and the plan's `Runnable(fn, instance)`
# would have needed `instance: ParametrizedSweep | None` -- putting the sentinel back
# inside a variant, so the three raise sites could not become exhaustive matches. A
# comment rather than a docstring: check-docstring-first reads a bare string after a
# module-level assignment as a misplaced module docstring.
WorkerState = Unbound | Declared | RunnableFunction | RunnableInstance


class WorkerManager:
    """Manages worker function configuration and validation for benchmarks.

    This class handles the setup and management of worker functions used in benchmarking,
    including support for both callable functions and ParametrizedSweep instances.

    The state is held as a single :data:`WorkerState` (plan 23 P9); ``worker`` and
    ``worker_class_instance`` are backward-compatible read-only views over it, so the
    public ``set_worker`` / ``set_worker_class`` API is unchanged.

    Attributes:
        state (WorkerState): ``Unbound()`` | ``Declared(cls)`` | ``RunnableFunction(fn)``
            | ``RunnableInstance(instance)``
        worker (Callable | None): The configured worker function, or None when nothing
            callable is attached (``Unbound`` / ``Declared``)
        worker_class_instance (ParametrizedSweep | type[ParametrizedSweep] | None): The
            declaration source -- an instance, a class, or None when there is none
        worker_input_cfg (type[ParametrizedSweep] | None): The input configuration class,
            when the worker is a function that takes one
    """

    def __init__(self) -> None:
        """Initialize a new WorkerManager."""
        self._state: WorkerState = Unbound()
        self.worker_input_cfg: type[ParametrizedSweep] | None = None

    @property
    def state(self) -> WorkerState:
        """The worker's lifecycle state; only ``set_worker*`` may change it."""
        return self._state

    @property
    def worker(self) -> Callable | None:
        """The callable worker, or None when nothing callable is attached.

        A backward-compatible view over :attr:`state`. ``None`` here is not a
        sentinel any longer -- it is what the two non-callable states project to --
        so callers reading it still see the pre-P9 contract (``Unbound`` and
        ``Declared`` both mean "cannot sample").
        """
        match self._state:
            case Unbound() | Declared():
                return None
            case RunnableFunction(fn=fn):
                return fn
            case RunnableInstance(instance=instance):
                return instance.__call__
            case _ as unreachable:
                assert_never(unreachable)

    @property
    def worker_class_instance(self) -> ParametrizedSweep | type[ParametrizedSweep] | None:
        """The declaration source: an instance, a class, or None.

        A backward-compatible view over :attr:`state` (``Bench`` mirrors it onto
        itself and ``plot_sweep`` gates auto-discovery on it being non-None).
        """
        match self._state:
            case Unbound() | RunnableFunction():
                return None
            case Declared(worker_class=worker_class):
                return worker_class
            case RunnableInstance(instance=instance):
                return instance
            case _ as unreachable:
                assert_never(unreachable)

    def _declaring(self) -> ParametrizedSweep | type[ParametrizedSweep]:
        """Return whatever declares this sweep's variables, or raise saying what to call.

        Total over :data:`WorkerState`: the three pre-P9
        ``RuntimeError("Worker class instance not set")`` sites in
        :meth:`get_result_vars` / :meth:`get_inputs_only` / :meth:`get_input_defaults`
        collapse into this one exhaustive match, so a new state cannot be added without
        `ty` demanding an answer for it here.

        Raising (rather than returning an empty list) is correct because every caller
        is on the *declaration* path -- ``plot_sweep`` deciding what to sweep, before
        any sample exists -- so nothing expensive is lost, and a silent empty answer
        would produce a sweep with no variables instead of an error naming the fix.

        Returns:
            ParametrizedSweep | type[ParametrizedSweep]: The instance or class whose
                ``get_*`` classmethods describe the sweep.

        Raises:
            RuntimeError: If no ParametrizedSweep is attached to read variables from.
        """
        match self._state:
            case RunnableInstance(instance=instance):
                return instance
            case Declared(worker_class=worker_class):
                return worker_class
            case Unbound():
                raise RuntimeError(
                    "No worker is attached, so there are no benchmark variables to read. "
                    "Call set_worker(<ParametrizedSweep instance>) to attach one, or "
                    "set_worker_class(<ParametrizedSweep subclass>) to declare a sweep "
                    "without running it."
                )
            case RunnableFunction():
                raise RuntimeError(
                    "The worker is a plain function, so no ParametrizedSweep declares this "
                    "sweep's variables. Either call set_worker(<ParametrizedSweep "
                    "instance>) instead, or pass input_vars/result_vars/const_vars to "
                    "plot_sweep() explicitly."
                )
            case _ as unreachable:
                assert_never(unreachable)

    def set_worker(
        self,
        worker: Callable | ParametrizedSweep,
        worker_input_cfg: type[ParametrizedSweep] | None = None,
    ) -> None:
        """Set the benchmark worker function and its input configuration.

        This method sets up the worker function to be benchmarked. The worker can be either a
        callable function that takes a ParametrizedSweep instance or a ParametrizedSweep
        instance with a __call__ method. In the latter case, worker_input_cfg is not needed.

        Args:
            worker (Callable | ParametrizedSweep): Either a function that will be benchmarked or a
                ParametrizedSweep instance with a __call__ method. When a ParametrizedSweep is
                provided, its __call__ method becomes the worker function.
            worker_input_cfg (type[ParametrizedSweep], optional): The class defining the inputs
                for the worker function. Only needed if worker is a function rather than a
                ParametrizedSweep instance. Defaults to None.

        Raises:
            RuntimeError: If worker is a class type instead of an instance.
        """
        # Parsed into one WorkerState here, at the boundary (plan 23 P9). A `match` on
        # the *argument* rather than an isinstance ladder, which is also what retires
        # the two TRY004 noqa suppressions this method and set_worker_class carried: the
        # rule fires on a non-TypeError raised under an isinstance guard, and
        # RuntimeError is the contract these two methods have always had (asserted by
        # test_set_worker_class_type_error and test_set_worker_class_rejects_an_instance,
        # and catchable by callers).
        match worker:
            case ParametrizedSweep():
                state: WorkerState = RunnableInstance(worker)
                if (
                    type(worker).__call__ is not ParametrizedSweep.__call__
                    and type(worker).benchmark is ParametrizedSweep.benchmark
                ):
                    warnings.warn(
                        f"{type(worker).__name__} overrides __call__() which is deprecated. "
                        "Override benchmark() instead.",
                        DeprecationWarning,
                        stacklevel=2,
                    )
                logger.info("setting worker from bench class.__call__")
            case type():
                raise RuntimeError("This should be a class instance, not a class")
            case _:
                if worker_input_cfg is None:
                    state = RunnableFunction(worker)
                else:
                    state = RunnableFunction(partial(worker_cfg_wrapper, worker, worker_input_cfg))
                logger.info(f"setting worker {worker}")
        self._state = state
        self.worker_input_cfg = worker_input_cfg

    def set_worker_class(self, worker_class: type[ParametrizedSweep]) -> None:
        """Attach a worker *class* for declaration only, leaving ``worker`` unset.

        Everything the declaration path needs from a worker is class-level --
        ``param.objects()`` plus the ``get_inputs_only`` / ``get_input_defaults`` /
        ``get_results_only`` classmethods -- so a class is enough to resolve variables
        by name, describe a sweep and hash it. What a class cannot do is be *called*,
        which is why :meth:`set_worker` rejects one. Since P9 that distinction *is* the
        state -- :class:`Declared` is declaring-but-not-callable, so ``worker`` reads
        back ``None`` by construction rather than by being left unassigned, and any
        attempt to sample raises rather than silently calling a class object.

        This exists for :func:`bencher.identity.sweep_identity`, which answers "what
        keys would this declaration produce" without running anything. Requiring an
        instance would put that out of reach of a worker whose ``__init__`` demands
        live resources -- an open device, a running simulator, an attached robot --
        which is exactly the expensive benchmark whose keys are worth checking before
        committing to a run.

        Args:
            worker_class: A ParametrizedSweep subclass. Never instantiated, never
                called.

        Raises:
            RuntimeError: If given an instance rather than a class -- the mirror of
                ``set_worker``'s complaint, so neither method silently accepts what
                the other is for.
        """
        match worker_class:
            case type():
                self._state = Declared(worker_class)
            case _:
                raise RuntimeError(
                    "This should be a class, not a class instance. Use set_worker() for "
                    "an instance."
                )
        logger.info(f"setting worker class {worker_class} for declaration only")

    def get_result_vars(self, as_str: bool = True) -> list[str] | list[Parameter]:
        """Retrieve the result variables from the worker class instance.

        Args:
            as_str (bool): If True, the result variables are returned as strings.
                           If False, they are returned in their original form.
                           Default is True.

        Returns:
            list[str] | list[Parameter]: The result variables, as names or as the
                ``param.Parameter`` descriptors themselves -- ``get_results_only``
                returns descriptors, not sweep instances.

        Raises:
            RuntimeError: If no ParametrizedSweep is attached (see :meth:`_declaring`).
        """
        declaring = self._declaring()
        if as_str:
            # str() because param types `Parameter.name` as `str | None`; a declared
            # parameter always has one, assigned when the owning class is created.
            return [str(i.name) for i in declaring.get_results_only()]
        return declaring.get_results_only()

    def get_inputs_only(self) -> list[Parameter]:
        """Retrieve the input variables from the worker class instance.

        Returns:
            list[Parameter]: The input variables, as ``param.Parameter`` descriptors.

        Raises:
            RuntimeError: If no ParametrizedSweep is attached (see :meth:`_declaring`).
        """
        return self._declaring().get_inputs_only()

    def get_input_defaults(self) -> list:
        """Retrieve the default input values from the worker class instance.

        Returns:
            list: A list of default input values as (parameter, value) tuples.

        Raises:
            RuntimeError: If no ParametrizedSweep is attached (see :meth:`_declaring`).
        """
        return self._declaring().get_input_defaults()
