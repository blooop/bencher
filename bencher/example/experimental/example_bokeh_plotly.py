import holoviews as hv
import numpy as np
import panel as pn

backend1 = "plotly"
backend2 = "bokeh"

hv.extension(backend2, backend1)

main = pn.Row()

dat = np.ones([10, 10])

surf = hv.Surface(dat)
main.append(hv.render(surf, backend=backend1))

heat = hv.HeatMap(dat)
heat *= hv.Text(0, 0, "I only work with bokeh and matplotlib")
main.append(heat)

main.show()
