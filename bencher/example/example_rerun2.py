import rerun as rr
import bencher as bch
import panel as pn


rr.init("rerun_example_local")
file_path = "dat1.rrd"

rr.log("s1", rr.Scalars(1))
rr.log("s1", rr.Scalars(4))
rr.log("s1", rr.Scalars(2))

local = True

if local:
    row = pn.Row()
    row.append(bch.rerun_to_pane())
    row.show()
else:
    # publish data to a github branch
    rr.save(file_path)
    bch.publish_and_view_rrd(
        file_path,
        remote="https://github.com/blooop/bencher.git",
        branch_name="test_rrd",
        content_callback=bch.github_content,
    ).show()
