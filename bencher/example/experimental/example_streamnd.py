# pylint: skip-file  #this is experimental still


import time

import holoviews as hv
import numpy as np
import panel as pn
from holoviews import streams

hv.extension("bokeh")

# Step 1: Set up your initial data
# For demonstration purposes, let's create a simple initial Image plot.

# Initial data (replace this with your actual data source)
initial_data = np.random.rand(10, 10)

# Create an Image plot from the initial data
initial_plot = hv.Image(initial_data)


# Step 2: Create a callback function to update the plot with new data
def update_plot(new_data):
    # Update the Image plot with the new data
    new_plot = hv.Image(new_data)
    return new_plot


# Step 3: Create a DynamicMap that triggers the update_plot callback
# The DynamicMap will automatically update the plot when new_data changes.
dmap = hv.DynamicMap(
    update_plot, streams=[streams.Stream.define("NewData", new_data=initial_data)()]
)

# Display the initial plot and start streaming updates
layout = initial_plot + dmap
layout = layout.cols(1)

# Simulate streaming updates by continuously updating the new_data stream
for i in range(10):
    # Replace this line with your actual data source/streaming mechanism
    new_data = np.random.rand(10, 10)
    # Update the new_data stream to trigger the DynamicMap callback
    dmap.event(NewData=new_data)
    # Sleep for a specified interval
    time.sleep(1)


pn.Row(dmap).show()
