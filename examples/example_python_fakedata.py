import numpy as np

from netCDF4 import Dataset
import os

###########################
## create the model data ##
###########################

# some spatial information
x = np.arange(-6, 6, 0.1)
y = np.arange(-3, 3, 0.1)

# some temporal information
t = np.arange(1, 5)

# meshes for each to make fake data
T, Y, X = np.meshgrid(t, y, x, indexing="ij")

# make fake time by x by y data
#   hint: this would be the data from a model, experiment, or the field
eta = np.sin(T * X + Y)
velocity = np.cos(T * Y + X)
H_SL = np.linspace(0.25, 0.9, num=len(t))  # sea level


#####################################
## create and fill the netcdf file ##
#####################################

directory = os.getcwd()
file_path = os.path.join(directory, "fakemodel_output.nc")
output_netcdf = Dataset(file_path, "w", format="NETCDF4")

# add some description information (see netCDF docs for more)
output_netcdf.description = "Output from MyFakeModel"
output_netcdf.source = "MyFakeModel v0.1"
output_netcdf.sandsuet_version = "1.0.0"

# create time and spatial netCDF dimensions
output_netcdf.createDimension("time", T.shape[0])
output_netcdf.createDimension("y", T.shape[1])
output_netcdf.createDimension("x", T.shape[2])

# create time and spatial netCDF variables
v_time = output_netcdf.createVariable("time", "f4", ("time",))
v_time.units = "second"
v_x = output_netcdf.createVariable("x", "f4", ("x"))
v_x.units = "meter"
v_y = output_netcdf.createVariable("y", "f4", ("y"))
v_y.units = "meter"

# fill the variables with the coordinate information
v_time[:] = t
v_x[:] = x
v_y[:] = y

# set up variables for output data grids
v_eta = output_netcdf.createVariable("eta", "f4", ("time", "y", "x"))
v_eta.units = "meter"
v_eta.long_name = "channel_bottom__elevation"
v_velocity = output_netcdf.createVariable("velocity", "f4", ("time", "y", "x"))
v_velocity.units = "meter/second"
v_velocity.long_name = "channel_water_flowing__speed"
v_eta[:] = eta
v_velocity[:] = velocity

# set up metadata group and populate variables
output_netcdf.createGroup("aux")
v_H_SL = output_netcdf.createVariable(  # an array, the sea level
    "aux/H_SL", "f4", ("time",)
)  # only has time dimensions
v_H_SL.units = "meter"
v_H_SL.long_name = "basin_water_surface__elevation"
v_H_SL[:] = H_SL

# close the netcdf file
output_netcdf.close()
