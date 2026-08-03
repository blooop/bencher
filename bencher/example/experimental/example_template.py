import holoviews as hv
import numpy as np
import panel as pn

pn.extension(sizing_mode="stretch_width")

ACCENT_COLOR = pn.template.FastListTemplate.accent_base_color
XS = np.linspace(0, np.pi)


def sine(freq, phase):
    return (
        hv.Curve((XS, np.sin(XS * freq + phase)))
        .opts(responsive=True, min_height=400, title="Sine", color=ACCENT_COLOR)
        .opts(line_width=6)
    )


def cosine(freq, phase):
    return (
        hv.Curve((XS, np.cos(XS * freq + phase)))
        .opts(responsive=True, min_height=400, title="Cosine", color=ACCENT_COLOR)
        .opts(line_width=6)
    )


freq_widget = pn.widgets.FloatSlider(label="Frequency", start=0, end=10, value=2)
phase_widget = pn.widgets.FloatSlider(label="Phase", start=0, end=np.pi)

sine = pn.bind(sine, freq=freq_widget, phase=phase_widget)
cosine = pn.bind(cosine, freq=freq_widget, phase=phase_widget)

template = pn.template.FastListTemplate(
    site="Panel",
    title="FastListTemplate",
    sidebar=[pn.pane.Markdown("## Settings"), freq_widget, phase_widget],
    main=[
        pn.pane.HoloViews(hv.DynamicMap(sine) + hv.DynamicMap(cosine), sizing_mode="stretch_both")
    ],
).show()
