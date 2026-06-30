from landlab import RasterModelGrid
from landlab.io.sandsuet import dump

# create model grid
grid = RasterModelGrid((3, 4), xy_spacing=(10.0, 20.0))
grid.add_field("topographic__elevation", np.arange(12.0), at="node")
grid.add_field("surface_water__depth", np.zeros(12), at="node")

# write to netCDF file
result = dump(grid, stream="sandsuet.nc")

# that's it!
