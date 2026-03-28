"""Example: view an .rrd file locally or publish it to a git branch."""

import rerun as rr
import bencher as bn
import panel as pn


def example_rerun2_local():
    """Save rerun data to an .rrd file and display it locally via rrd_to_pane."""
    rr.init("rerun_example_local")
    file_path = "dat1.rrd"
    rr.save(file_path)

    rr.log("s1", rr.Scalars(1))
    rr.log("s1", rr.Scalars(4))
    rr.log("s1", rr.Scalars(2))

    row = pn.Row()
    row.append(bn.rrd_to_pane(f"http://127.0.0.1:8001/{file_path}"))
    row.show()


def example_rerun2_publish():
    """Save rerun data and publish the .rrd file to a git branch for viewing."""
    rr.init("rerun_example_publish")
    file_path = "dat1.rrd"
    rr.save(file_path)

    rr.log("s1", rr.Scalars(1))
    rr.log("s1", rr.Scalars(4))
    rr.log("s1", rr.Scalars(2))

    bn.publish_and_view_rrd(
        file_path,
        remote="https://github.com/blooop/bencher.git",
        branch_name="test_rrd",
        content_callback=bn.github_content,
    ).show()


if __name__ == "__main__":
    example_rerun2_local()
