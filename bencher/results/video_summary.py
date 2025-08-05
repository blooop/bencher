from typing import Optional, List
from copy import deepcopy
import panel as pn
import xarray as xr
from param import Parameter
from bencher.results.bench_result_base import BenchResultBase, ReduceType
from bencher.variables.results import ResultImage
from bencher.plotting.plot_filter import VarRange, PlotFilter
from bencher.utils import callable_name, int_to_col, color_tuple_to_255
from bencher.video_writer import VideoWriter
from bencher.results.video_controls import VideoControls
from bencher.results.composable_container.composable_container_video import (
    ComposableContainerVideo,
    ComposeType,
    RenderCfg,
)


class VideoSummaryResult(BenchResultBase):
    def to_video_summary(
        self,
        result_var: Parameter = None,
        reverse: bool = True,
        result_types=(ResultImage,),
        **kwargs,
    ) -> Optional[pn.panel]:
        return self.to_video_grid(
            result_var=result_var,
            result_types=result_types,
            time_sequence_dimension=-1,
            reverse=reverse,
            **kwargs,
        )

    def to_video_grid(
        self,
        result_var: Parameter = None,
        result_types=(ResultImage,),
        pane_collection: pn.pane = None,
        time_sequence_dimension=0,
        target_duration: float = None,
        compose_method_list: List = None,
        **kwargs,
    ) -> Optional[pn.panel]:
        """Returns the results compiled into a video

        Args:
            result_var (Parameter, optional): The result var to plot. Defaults to None.
            result_types (tuple, optional): The types of result var to convert to video. Defaults to (ResultImage,).
            collection (pn.pane, optional): If there are multiple results, use this collection to stack them. Defaults to pn.Row().
            compose_method_list (List: optional): Defines how each of the dimensions is composed in the video. ie, concatenate the videos horizontally, vertically, sequentially or alpha overlay. Seee bch.ComposeType for the options.

        Returns:
            Optional[pn.panel]: a panel pane with a video of all results concatenated together
        """
        plot_filter = PlotFilter(
            float_range=VarRange(0, None),
            cat_range=VarRange(0, None),
            panel_range=VarRange(1, None),
            input_range=VarRange(1, None),
        )
        matches_res = plot_filter.matches_result(
            self.plt_cnt_cfg, callable_name(self.to_video_grid_ds), override=False
        )

        if pane_collection is None:
            pane_collection = pn.Row()

        if matches_res.overall:
            ds = self.to_dataset(ReduceType.SQUEEZE)
            for rv in self.get_results_var_list(result_var):
                if isinstance(rv, result_types):
                    pane_collection.append(
                        self.to_video_grid_ds(
                            ds,
                            rv,
                            time_sequence_dimension=time_sequence_dimension,
                            target_duration=target_duration,
                            compose_method_list=compose_method_list,
                            **kwargs,
                        )
                    )
            return pane_collection
        return matches_res.to_panel()

    def to_video_grid_ds(
        self,
        dataset: xr.Dataset,
        result_var: Parameter,
        reverse=True,
        time_sequence_dimension=0,
        video_controls: VideoControls = None,
        target_duration: float = None,
        compose_method_list: List = None,
        target_dimension: int = 0,
        **kwargs,
    ):
        """Creates a video grid from the provided dataset.

        This method generates a video by composing multiple plot panes into a grid
        layout and renders them as a video file.

        Args:
            dataset (xr.Dataset): The dataset containing benchmark results.
            result_var (Parameter): The result variable to plot.
            reverse (bool, optional): Whether to reverse the sequence. Defaults to True.
            time_sequence_dimension (int, optional): The dimension to use for time sequencing. Defaults to 0.
            video_controls (VideoControls, optional): Controls for video playback. If None, creates default controls.
            target_duration (float, optional): Target duration for the video in seconds.
            compose_method_list (List, optional): List of composition methods for combining panes.
            target_dimension (int, optional): The target dimensionality for data filtering. Defaults to 0.
            **kwargs: Additional keyword arguments passed to video rendering.

        Returns:
            Optional[pn.pane.HTML]: A video container with playback controls if successful, None otherwise.
        """
        cvc = self._to_video_panes_ds(
            dataset,
            self.plot_cb,
            target_dimension=target_dimension,
            horizontal=True,
            compose_method=ComposeType.right,
            time_sequence_dimension=time_sequence_dimension,
            result_var=result_var,
            final=True,
            reverse=reverse,
            compose_method_list=compose_method_list,
            target_duration=target_duration,
            **kwargs,
        )

        filename = VideoWriter().write_video_raw(cvc)

        if filename is not None:
            if video_controls is None:
                video_controls = VideoControls()
            return video_controls.video_container(
                filename, width=kwargs.get("width", None), height=kwargs.get("height", None)
            )
        return None

    def plot_cb(self, dataset, result_var, **kwargs):
        val = self.ds_to_container(dataset, result_var, container=None, **kwargs)
        return val

    def dataset_to_compose_list(
        self,
        dataset: xr.Dataset,
        first_compose_method: ComposeType = ComposeType.down,
        time_sequence_dimension: int = 0,
    ) -> List[ComposeType]:
        """ "Given a dataset, chose an order for composing the results.  By default will flip between right and down and the last dimension will be a time sequence.

        Args:
            dataset (xr.Dataset): the dataset to render
            first_compose_method (ComposeType, optional): the direction of the first composition method. Defaults to ComposeType.right.
            time_sequence_dimension (int, optional): The dimension to start time sequencing instead of composing in space. Defaults to 0.

        Returns:
            List[ComposeType]: A list of composition methods for composing the dataset result
        """

        num_dims = len(dataset.sizes)
        if time_sequence_dimension == -1:  # use time sequence for everything
            compose_method_list = [ComposeType.sequence] * (num_dims + 1)
        else:
            compose_method_list = [first_compose_method]
            compose_method_list.extend(
                ComposeType.flip(compose_method_list[-1]) for _ in range(num_dims - 1)
            )
            compose_method_list.append(ComposeType.sequence)

            for i in range(min(len(compose_method_list), time_sequence_dimension + 1)):
                compose_method_list[i] = ComposeType.sequence

        return compose_method_list

    def _to_video_panes_ds(
        self,
        dataset: xr.Dataset,
        plot_callback: callable = None,
        target_dimension=0,
        compose_method=ComposeType.right,
        compose_method_list=None,
        result_var=None,
        time_sequence_dimension=0,
        root_dimensions=None,
        reverse=False,
        target_duration: float = None,
        **kwargs,
    ) -> pn.panel:
        num_dims = len(dataset.sizes)
        dims = list(d for d in dataset.sizes)
        if reverse:
            dims = list(reversed(dims))

        if root_dimensions is None:
            root_dimensions = num_dims

        if compose_method_list is None:
            compose_method_list = self.dataset_to_compose_list(
                dataset, compose_method, time_sequence_dimension=time_sequence_dimension
            )

            # print(compose_method_list)

        compose_method_list_pop = deepcopy(compose_method_list)
        if len(compose_method_list_pop) > 1:
            compose_method = compose_method_list_pop.pop()

        if num_dims > (target_dimension) and num_dims != 0:
            selected_dim = dims[-1]
            outer_container = ComposableContainerVideo()
            for i in range(dataset.sizes[selected_dim]):
                sliced = dataset.isel({selected_dim: i})
                label_val = sliced.coords[selected_dim].values.item()
                inner_container = ComposableContainerVideo()

                panes = self._to_video_panes_ds(
                    sliced,
                    plot_callback=plot_callback,
                    target_dimension=target_dimension,
                    compose_method_list=compose_method_list_pop,
                    result_var=result_var,
                    root_dimensions=root_dimensions,
                    time_sequence_dimension=time_sequence_dimension,
                )
                inner_container.append(panes)

                rendered = inner_container.render(
                    RenderCfg(
                        var_name=selected_dim,
                        var_value=label_val,
                        compose_method=compose_method,
                        duration=target_duration,
                    )
                )
                outer_container.append(rendered)
            return outer_container.render(
                RenderCfg(
                    compose_method=compose_method,
                    duration=target_duration,
                    background_col=color_tuple_to_255(int_to_col(num_dims - 2, 0.05, 1.0)),
                    # background_col= (255,0,0),
                )
            )
        return plot_callback(dataset=dataset, result_var=result_var, **kwargs)
