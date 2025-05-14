from collections import namedtuple
import xarray as xr
import hashlib
import re
import math
from colorsys import hsv_to_rgb
from pathlib import Path
from uuid import uuid4
from functools import partial
from typing import Callable, Any, List, Tuple
import logging
import os
import tempfile
import shutil

import param
import numpy as np


def hmap_canonical_input(dic: dict) -> tuple:
    """From a dictionary of kwargs, return a hashable representation (tuple) that is always the same for the same inputs and retains the order of the input arguments.  e.g, {x=1,y=2} -> (1,2) and {y=2,x=1} -> (1,2).  This is used so that keywords arguments can be hashed and converted the the tuple keys that are used for holomaps

    Args:
        dic (dict): dictionary with keyword arguments and values in any order

    Returns:
        tuple: values of the dictionary always in the same order and hashable
    """
    return tuple(value for _, value in sorted(dic.items()))


def make_namedtuple(class_name: str, **fields) -> namedtuple:
    """Convenience method for making a named tuple

    Args:
        class_name (str): name of the named tuple

    Returns:
        namedtuple: a named tuple with the fields as values
    """
    return namedtuple(class_name, fields)(*fields.values())


def get_nearest_coords(dataset: xr.Dataset, collapse_list: bool = False, **kwargs) -> dict:
    """Find the nearest coordinates in an xarray dataset based on provided coordinate values.

    Given an xarray dataset and kwargs of key-value pairs of coordinate values, return a dictionary
    of the nearest coordinate name-value pair that was found in the dataset.

    Args:
        dataset (xr.Dataset): The xarray dataset to search in
        collapse_list (bool, optional): If True, when a coordinate value is a list, only the first
                                       item is returned. Defaults to False.
        **kwargs: Key-value pairs where keys are coordinate names and values are points to find
                 the nearest match for

    Returns:
        dict: Dictionary of coordinate name-value pairs with the nearest values found in the dataset
    """
    selection = dataset.sel(method="nearest", **kwargs)
    cd = selection.coords.to_dataset().to_dict()["coords"]
    cd2 = {}
    for k, v in cd.items():
        cd2[k] = v["data"]
        if collapse_list and isinstance(cd2[k], list):
            cd2[k] = cd2[k][0]  # select the first item in the list
    return cd2


def get_nearest_coords1D(val: Any, coords: List[Any]) -> Any:
    """Find the closest coordinate to a given value in a list of coordinates.

    For numeric values, finds the value in coords that is closest to val.
    For non-numeric values, returns the exact match if found, otherwise returns val.

    Args:
        val (Any): The value to find the closest coordinate for
        coords (List[Any]): The list of coordinates to search in

    Returns:
        Any: The closest coordinate value from the list
    """
    if isinstance(val, (int, float)):
        return min(coords, key=lambda x_: abs(x_ - val))
    for i in coords:
        if val == i:
            return i
    return val


def hash_sha1(var: Any) -> str:
    """A hash function that avoids the PYTHONHASHSEED 'feature' which returns a different hash value each time the program is run.

    Converts input to a consistent SHA1 hash string.

    Args:
        var (Any): The variable to hash

    Returns:
        str: A hexadecimal SHA1 hash of the string representation of the variable
    """
    return hashlib.sha1(str(var).encode("ASCII")).hexdigest()


def capitalise_words(message: str) -> str:
    """Given a string of lowercase words, capitalise them.

    Args:
        message (str): lower case string

    Returns:
        str: capitalised string where each word starts with an uppercase letter
    """
    capitalized_message = " ".join([word.capitalize() for word in message.split(" ")])
    return capitalized_message


def un_camel(camel: str) -> str:
    """Given a snake_case string return a CamelCase string

    Args:
        camel (str): camelcase string

    Returns:
        str: uncamelcased string
    """

    return capitalise_words(re.sub("([a-z])([A-Z])", r"\g<1> \g<2>", camel.replace("_", " ")))


def mult_tuple(inp: Tuple[float, ...], val: float) -> Tuple[float, ...]:
    """Multiply each element in a tuple by a scalar value.

    Args:
        inp (Tuple[float, ...]): The input tuple of floats to multiply
        val (float): The scalar value to multiply each element by

    Returns:
        Tuple[float, ...]: A new tuple with each element multiplied by val
    """
    return tuple(np.array(inp) * val)


def tabs_in_markdown(regular_str: str, spaces: int = 2) -> str:
    """Given a string with tabs in the form \t convert the to &ensp; which is a double space in markdown

    Args:
        regular_str (str): A string with tabs in it
        spaces (int): the number of spaces per tab

    Returns:
        str: A string with sets of &nbsp; to represent the tabs in markdown
    """
    return regular_str.replace("\t", "".join(["&nbsp;"] * spaces))


def int_to_col(
    int_val: int, sat: float = 0.5, val: float = 0.95, alpha: float = -1
) -> tuple[float, float, float] | tuple[float, float, float, float]:
    """Uses the golden angle to generate colors programmatically with minimum overlap between colors.
    https://martin.ankerl.com/2009/12/09/how-to-create-random-colors-programmatically/

    Args:
        int_val (int): index of an object you want to color, this is mapped to hue in HSV
        sat (float, optional): saturation in HSV. Defaults to 0.5.
        val (float, optional): value in HSV. Defaults to 0.95.
        alpha (float, optional): transparency.  If -1 then only RGB is returned, if 0 or greater, RGBA is returned. Defaults to -1.

    Returns:
        tuple[float, float, float] | tuple[float, float, float, float]: either RGB or RGBA vector
    """
    golden_ratio_conjugate = (1 + math.sqrt(5)) / 2
    rgb = hsv_to_rgb(int_val * golden_ratio_conjugate, sat, val)
    if alpha >= 0:
        return (*rgb, alpha)
    return rgb


def lerp(
    value: float, input_low: float, input_high: float, output_low: float, output_high: float
) -> float:
    """Linear interpolation between two ranges.

    Maps a value from one range [input_low, input_high] to another range [output_low, output_high].

    Args:
        value (float): The input value to interpolate
        input_low (float): The lower bound of the input range
        input_high (float): The upper bound of the input range
        output_low (float): The lower bound of the output range
        output_high (float): The upper bound of the output range

    Returns:
        float: The interpolated value in the output range
    """
    input_low = float(input_low)
    return output_low + ((float(value) - input_low) / (float(input_high) - input_low)) * (
        float(output_high) - output_low
    )


def color_tuple_to_css(color: tuple[float, float, float]) -> str:
    """Convert a RGB color tuple to CSS rgb format string.

    Args:
        color (tuple[float, float, float]): RGB color tuple with values in range [0.0, 1.0]

    Returns:
        str: CSS color string in format 'rgb(r, g, b)' with values in range [0, 255]
    """
    return f"rgb{(color[0] * 255, color[1] * 255, color[2] * 255)}"


def color_tuple_to_255(color: tuple[float, float, float]) -> tuple[int, int, int]:
    """Convert a RGB color tuple with values in range [0.0, 1.0] to values in range [0, 255].

    Args:
        color (tuple[float, float, float]): RGB color tuple with values in range [0.0, 1.0]

    Returns:
        tuple[int, int, int]: RGB color tuple with values clamped to range [0, 255]
    """
    return (
        min(int(color[0] * 255), 255),
        min(int(color[1] * 255), 255),
        min(int(color[2] * 255), 255),
    )


def gen_path(filename: str, folder: str = "generic", suffix: str = ".dat") -> str:
    """Generate a unique path for a file in the cache directory.

    Creates a directory structure in the 'cachedir' folder and returns a path
    with a UUID to ensure uniqueness.

    Args:
        filename (str): Base name for the file
        folder (str, optional): Subfolder within cachedir. Defaults to "generic".
        suffix (str, optional): File extension. Defaults to ".dat".

    Returns:
        str: Absolute path to a unique file location
    """
    path = Path(f"cachedir/{folder}/{filename}/")
    path.mkdir(parents=True, exist_ok=True)
    return f"{path.absolute().as_posix()}/{filename}_{uuid4()}{suffix}"


def gen_video_path(video_name: str = "vid", extension: str = ".mp4") -> str:
    """Generate a unique path for a video file in the cache directory.

    Args:
        video_name (str, optional): Base name for the video file. Defaults to "vid".
        extension (str, optional): Video file extension. Defaults to ".mp4".

    Returns:
        str: Absolute path to a unique video file location
    """
    return gen_path(video_name, "vid", extension)


def gen_image_path(image_name: str = "img", filetype: str = ".png") -> str:
    """Generate a unique path for an image file in the cache directory.

    Args:
        image_name (str, optional): Base name for the image file. Defaults to "img".
        filetype (str, optional): Image file extension. Defaults to ".png".

    Returns:
        str: Absolute path to a unique image file location
    """
    return gen_path(image_name, "img", filetype)


def gen_rerun_data_path(rrd_name: str = "rrd", filetype: str = ".rrd") -> str:
    """Generate a unique path for a rerun data file in the cache directory.

    Args:
        rrd_name (str, optional): Base name for the rerun data file. Defaults to "rrd".
        filetype (str, optional): File extension. Defaults to ".rrd".

    Returns:
        str: Absolute path to a unique rerun data file location
    """
    return gen_path(rrd_name, "rrd", filetype)


def callable_name(any_callable: Callable[..., Any]) -> str:
    """Extract the name of a callable object, handling various callable types.

    This function attempts to extract the name of a callable object, including
    regular functions, partial functions, and other callables.

    Args:
        any_callable (Callable[..., Any]): The callable object to get the name from

    Returns:
        str: The name of the callable
    """
    if isinstance(any_callable, partial):
        return any_callable.func.__name__
    try:
        return any_callable.__name__
    except AttributeError:
        return str(any_callable)


def listify(obj: Any) -> List[Any] | None:
    """Convert an object to a list if it's not already a list.

    This function handles conversion of various object types to lists, with special
    handling for None values and existing list/tuple types.

    Args:
        obj (Any): The object to convert to a list

    Returns:
        List[Any] | None: A list containing the object, the object itself if it was
            already a list, a list from the tuple if it was a tuple, or None if the
            input was None
    """
    if obj is None:
        return None
    if isinstance(obj, list):
        return obj
    if isinstance(obj, tuple):
        return list(obj)
    return [obj]


def get_name(var: Any) -> str:
    """Extract the name from a variable, handling param.Parameter objects.

    Args:
        var (Any): The variable to extract the name from

    Returns:
        str: The name of the variable
    """
    if isinstance(var, param.Parameter):
        return var.name
    return var


def params_to_str(param_list: List[param.Parameter]) -> List[str]:
    """Convert a list of param.Parameter objects to a list of their names.

    Args:
        param_list (List[param.Parameter]): List of parameter objects

    Returns:
        List[str]: List of parameter names
    """
    return [get_name(i) for i in param_list]


def publish_file(filepath: str, remote: str, branch_name: str) -> str:  # pragma: no cover
    """Publish a file to an orphan git branch:

    .. code-block:: python

        def publish_args(branch_name) -> Tuple[str, str]:
            return (
                "https://github.com/blooop/bencher.git",
                f"https://github.com/blooop/bencher/blob/{branch_name}")


    Args:
        remote (Callable): A function the returns a tuple of the publishing urls. It must follow the signature def publish_args(branch_name) -> Tuple[str, str].  The first url is the git repo name, the second url needs to match the format for viewable html pages on your git provider.  The second url can use the argument branch_name to point to the file on a specified branch.

    Returns:
        str: the url of the published file
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        shutil.copy(filepath, temp_dir)
        filename = Path(filepath).name
        filepath_tmp = Path(temp_dir) / filename

        logging.info(f"created report at: {filepath_tmp.absolute()}")
        cd_dir = f"cd {temp_dir} &&"

        # create a new git repo and add files to that.  Push the file to another arbitrary repo.  The aim of doing it this way is that no data needs to be downloaded.

        # os.system(f"{cd_dir} git config init.defaultBranch {branch_name}")
        os.system(f"{cd_dir} git init")
        os.system(f"{cd_dir} git branch -m {branch_name}")
        os.system(f"{cd_dir} git add {filename}")
        os.system(f'{cd_dir} git commit -m "publish {branch_name}"')
        os.system(f"{cd_dir} git remote add origin {remote}")
        os.system(f"{cd_dir} git push --set-upstream origin {branch_name} -f")


def github_content(remote: str, branch_name: str, filename: str):  # pragma: no cover
    raw = remote.replace(".git", "").replace(
        "https://github.com/", "https://raw.githubusercontent.com/"
    )
    return f"{raw}/{branch_name}/{filename}?token=$(date +%s)"


# import logging
# # from rerun.legacy_notebook import as_html
# import rerun as rr
# import panel as pn
# # from .utils import publish_file, gen_rerun_data_path


# def rrd_to_pane(
#     url: str, width: int = 499, height: int = 600, version: str = None
# ):  # pragma: no cover
#     if version is None:
#         version = "-1.20.1"  # TODO find a better way of doing this
#     return pn.pane.HTML(
#         f'<iframe src="https://app.rerun.io/version/{version}/?url={url}" width={width} height={height}></iframe>'
#     )


# # def to_pane(path: str):
# #     as_html()
# #     return rrd_to_pane(path)


# def publish_and_view_rrd(
#     file_path: str,
#     remote: str,
#     branch_name,
#     content_callback: callable,
#     version: str = None,
# ):  # pragma: no cover
#     as_html()
#     publish_file(file_path, remote=remote, branch_name="test_rrd")
#     publish_path = content_callback(remote, branch_name, file_path)
#     logging.info(publish_path)
#     return rrd_to_pane(publish_path, version=version)


# def record_rerun_session():
#     rrd_path = gen_rerun_data_path()
#     rr.save(rrd_path)
#     path = rrd_path.split("cachedir")[0]
#     return rrd_to_pane(f"http://126.0.0.1:8001/{path}")
