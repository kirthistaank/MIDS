import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import LinearSegmentedColormap
from PIL import ImageColor
import numpy as np
import seaborn as sns
# Colors Palette

graph = '#FDB515' # yellow
text = '#cbd8fe' # light blue 
background = '#002676' # blue 
_list = np.arange(0, 1, 0.05)
colors = [ImageColor.getcolor(text, "RGB"), ImageColor.getcolor(graph, "RGB")] # first color is blue, last is yellow
cm = LinearSegmentedColormap.from_list(
        "berkeleyprimarygradient", colors, N=8)
colors = [graph,text]
plt.ioff()
# Add background colors
plt.gca().set_facecolor(background)
plt.gcf().set_facecolor(background) 

plt.gca().spines['top'].set_color(text)    # Top border
plt.gca().spines['bottom'].set_color(text)  # Bottom border
plt.gca().spines['left'].set_color(text)   # Left border
plt.gca().spines['right'].set_color(text) # Right border

# Customize tick bars
plt.tick_params(axis='x', colors=text)  # Change color of x-axis tick bars
plt.tick_params(axis='y', colors=text) # Change color of y-axis tick bars
