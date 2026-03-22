import seaborn as sns
from PIL import ImageColor
#UC Berekeley Color Palette theme for graphs
berkeley_palette_primary = ["#002676", "#FDB515"]# Skipping white "#FFFFFF"
berkeley_palette_preferred_dark = ["#010133","#FC9313", "#00553A","#770747","#431170"]

berkeley_palette_alternative_medium=["#004AAE","#FFC31B","#018943","#E7115E","#8236C7"]
berkeley_palette_alternative_light = ["#9FD1FF","#FFE88D","#B3E59A","#FFCFE5","#FFCFE5"]
berkeley_palette_black_grey=["#808080","#808080"]#Skipping black "#000000"

berkeley_palette_special_colors = ["#C09748"]
berkeley_palette_all = berkeley_palette_primary+berkeley_palette_preferred_dark+berkeley_palette_alternative_medium+berkeley_palette_alternative_light+berkeley_palette_special_colors+berkeley_palette_black_grey


# Global Colors Palette
graph = '#FDB515' # yellow
text = '#cbd8fe' # light blue 
background = '#002676' # blue 

# Global variables 

# Correction key for data
us_state_names = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina",
    "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah",
    "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"
]
us_states_abbr = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", 
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", 
    "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", 
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", 
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", 
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", 
    "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", 
    "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", 
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", 
    "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", 
    "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", 
    "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", 
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", 
    "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", 
    "Wisconsin": "WI", "Wyoming": "WY"
}
abbreviation_to_name = {
    "AK": "Alaska",
    "AL": "Alabama",
    "AR": "Arkansas",
    "AZ": "Arizona",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "IA": "Iowa",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MO": "Missouri",
    "MS": "Mississippi",
    "MT": "Montana",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "NE": "Nebraska",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NV": "Nevada",
    "NY": "New York",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VA": "Virginia",
    "VT": "Vermont",
    "WA": "Washington",
    "WI": "Wisconsin",
    "WV": "West Virginia",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "AS": "American Samoa",
    "GU": "Guam GU",
    "MP": "Northern Mariana Islands",
    "PR": "Puerto Rico PR"
}
us_state_correction = {
    "au large de la californie": "California",
    "Pacifique":"California",
    "au large de la Californie":"California",
    "nouveau mexique": "New Mexico",
    "chicago": "Illinois",
    "los angeles": "California",
    "swisher districts": "Texas",
    "rhode isl. ": "Rhode Island",
    "near los angeles": "California",
    "atlantic terminal station": "New York",
    "north california": "California",
    "los angeles": "California",
    "jerauld": "South Dakota",
    "jefferson davis": "Mississippi",
    "nassau-florida": "Florida",
    "wilkes": "North Carolina",
    "noble in richland": "Illinois",
    "marion-in": "Indiana",
    "central michigan ": "Michigan",
    "south california": "California",
    "south-western louisiana": "Louisiana",
    "north california ": "California",
    "northern washington ": "Washington",
    "central-northern usa": "None",
    "montana and idaho s": "None",
    "hollywood": "California",
    "eastern washington ": "Washington",
    "eastern new mexico": "New Mexico",
    "district of columbia":"Washington, D.C.",
    "Nouveau Mexique" :"New Mexico"
}

# plot configuration
# Define custom rcParams
custom_rc = {
    "axes.titlesize": 16,
    "axes.labelsize": 14,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "legend.fontsize": 12,
    "figure.figsize": (8, 6),
    "figure.dpi": 100,
    "lines.linewidth": 2,
    "grid.color": "gray",
    "grid.linestyle": "--",
    "colorbar.tick.color": "red",
}

# Misc 
text_props = {'color':"w"}
