import xarray as xr
import numpy as np
import pandas as pd
import os
from sandplover.cube import DataCube


class Delft3DConverter:
    
    VARIABLE_MAPPING = {
        'DPS': 'water_depth',      # Water depth (from bed to water surface)
        'S1': 'water_level',       # Water level (surface elevation)
        'U1': 'u_velocity',        # x-direction velocity
        'V1': 'v_velocity',        # y-direction velocity
        'MUDFRAC': 'mud_frac',     # Mud fraction
        
        #### Additional Variables (Uncomment to use) 
        # Add more Delft3D variables here by uncommenting and modifying: for examples..
        
        # 'TAUKSI': 'bed_shear_stress_x',  # Bed shear stress in x-direction
        # 'TAUETA': 'bed_shear_stress_y',  # Bed shear stress in y-direction
        # 'SBUU': 'bed_load_x',    # Bed load transport in x-direction
        # 'SBVV': 'bed_load_y',    # Bed load transport in y-direction
        # 'SSUU': 'suspended_load_x',  # Suspended load transport in x-direction
        # 'SSVV': 'suspended_load_y',  # Suspended load transport in y-direction
    }
    
    def __init__(self, trim_file_path):
        self.trim_file_path = trim_file_path
        self.trim_ds = None
        self.data_dict = {}
        self.dimensions = {}
        self.cube = None
        
    def load_dataset(self):
        """Load the Delft3D NetCDF dataset."""
        self.trim_ds = xr.open_dataset(self.trim_file_path, decode_timedelta=True)
        print(f"File loaded: {self.trim_file_path}")
        return self
    
    def inspect_variables(self):
        """Display available variables and coordinates."""
        if self.trim_ds is None:
            raise ValueError("Dataset not loaded. Call load_dataset() first.")
        
        print(f"Available variables: {list(self.trim_ds.data_vars.keys())}")
        print(f"Coordinates: {list(self.trim_ds.coords.keys())}")
        return self
    
    def extract_variables(self):
        """Extract and process variables from Delft3D dataset."""
        if self.trim_ds is None:
            raise ValueError("Dataset not loaded. Call load_dataset() first.")
        
        u_vel = None
        v_vel = None
        mud_frac = None
        water_depth = None  # DPS
        water_level = None  # S1
        
        # ========== Additional temporary variables (Uncomment to use) ==========
        # Uncomment these if you add bed shear stress or transport variables
        # tau_x = None  # For TAUKSI
        # tau_y = None  # For TAUETA
        # bed_load_x = None  # For SBUU
        # bed_load_y = None  # For SBVV
        # suspended_x = None  # For SSUU
        # suspended_y = None  # For SSVV
        
        for delft_var, sp_var in self.VARIABLE_MAPPING.items():
            if delft_var in self.trim_ds.data_vars:
                var_data = self.trim_ds[delft_var].values
                
                # U1, V1 are 4D - extract surface layer
                if delft_var in ['U1', 'V1'] and len(var_data.shape) == 4:
                    var_data = var_data[:, 0, :, :]
                    
                    if sp_var == 'u_velocity':
                        u_vel = var_data
                    elif sp_var == 'v_velocity':
                        v_vel = var_data
                    
                    # ========== Store other 4D velocity components (Uncomment to use) ==========
                    # If you need to store the actual u and v components as separate variables:
                    # self.data_dict[sp_var] = var_data
                        
                # MUDFRAC is 3D
                elif delft_var == 'MUDFRAC' and len(var_data.shape) == 3:
                    mud_frac = var_data
                
                # DPS and S1 are 3D - store temporarily for eta calculation
                elif delft_var == 'DPS' and len(var_data.shape) == 3:
                    water_depth = var_data
                elif delft_var == 'S1' and len(var_data.shape) == 3:
                    water_level = var_data
                
                # ========== Handle bed shear stress (Uncomment to use) ==========
                # elif delft_var == 'TAUKSI' and len(var_data.shape) == 3:
                #     tau_x = var_data
                #     # Optionally store as separate variable:
                #     # self.data_dict[sp_var] = var_data
                # elif delft_var == 'TAUETA' and len(var_data.shape) == 3:
                #     tau_y = var_data
                #     # Optionally store as separate variable:
                #     # self.data_dict[sp_var] = var_data
                
                # ========== Handle sediment transport (Uncomment to use) ==========
                # elif delft_var == 'SBUU' and len(var_data.shape) == 3:
                #     bed_load_x = var_data
                # elif delft_var == 'SBVV' and len(var_data.shape) == 3:
                #     bed_load_y = var_data
                # elif delft_var == 'SSUU' and len(var_data.shape) == 3:
                #     suspended_x = var_data
                # elif delft_var == 'SSVV' and len(var_data.shape) == 3:
                #     suspended_y = var_data
                    
        # Calculate bed elevation (eta) from water level and water depth
        if water_level is not None and water_depth is not None:
            eta = water_level - water_depth
            self.data_dict['eta'] = eta
            self.data_dict['water_depth'] = water_depth
            print(f"Bed elevation (eta = S1 - DPS): [{np.nanmin(eta):.4f}, {np.nanmax(eta):.4f}] m")
        
        # Calculate velocity magnitude
        if u_vel is not None and v_vel is not None:
            velocity_magnitude = np.sqrt(u_vel**2 + v_vel**2)
            self.data_dict['velocity'] = velocity_magnitude
            print(f"Velocity magnitude: [{np.nanmin(velocity_magnitude):.4f}, {np.nanmax(velocity_magnitude):.4f}] m/s")
        
        # Calculate sand fraction
        if mud_frac is not None:
            sand_frac = 1.0 - mud_frac
            self.data_dict['mud_frac'] = mud_frac
            self.data_dict['sand_frac'] = sand_frac
            print(f"Sediment fractions calculated")
        
        # ========== Additional Derived Variables (Uncomment to use) ==========
        
        # Example 1: Calculate total bed shear stress magnitude
        # if tau_x is not None and tau_y is not None:
        #     bed_shear_stress_magnitude = np.sqrt(tau_x**2 + tau_y**2)
        #     self.data_dict['bed_shear_stress'] = bed_shear_stress_magnitude
        #     print(f"Bed shear stress magnitude calculated")
        
        # Example 2: Calculate total bed load transport magnitude
        # if bed_load_x is not None and bed_load_y is not None:
        #     bed_load_magnitude = np.sqrt(bed_load_x**2 + bed_load_y**2)
        #     self.data_dict['bed_load_transport'] = bed_load_magnitude
        #     print(f"Bed load transport magnitude calculated")
        
        # Example 3: Calculate total suspended load transport magnitude
        # if suspended_x is not None and suspended_y is not None:
        #     suspended_load_magnitude = np.sqrt(suspended_x**2 + suspended_y**2)
        #     self.data_dict['suspended_load_transport'] = suspended_load_magnitude
        #     print(f"Suspended load transport magnitude calculated")
        
        # Example 4: Calculate total sediment transport (bed + suspended)
        # if 'bed_load_transport' in self.data_dict and 'suspended_load_transport' in self.data_dict:
        #     total_transport = self.data_dict['bed_load_transport'] + self.data_dict['suspended_load_transport']
        #     self.data_dict['total_sediment_transport'] = total_transport
        #     print(f"Total sediment transport calculated")
        
        # Example 5: Calculate velocity direction (angle in degrees)
        # if u_vel is not None and v_vel is not None:
        #     velocity_direction = np.arctan2(v_vel, u_vel) * 180 / np.pi
        #     self.data_dict['velocity_direction'] = velocity_direction
        #     print(f"Velocity direction calculated")
        
        # Transpose all variables from (time, M, N) to (time, N, M) = (time, x, y)
        for key in self.data_dict:
            self.data_dict[key] = np.transpose(self.data_dict[key], (0, 2, 1))

        print(f"Variables: {list(self.data_dict.keys())}")
        return self

    def generate_dimensions(self):
        """Generate dimension information for DataCube."""
        if self.trim_ds is None:
            raise ValueError("Dataset not loaded. Call load_dataset() first.")

        # Time coordinate
        if 'time' in self.trim_ds.coords:
            self.dimensions['time'] = self.trim_ds['time'].values

        if len(self.data_dict) > 0:
            first_var = list(self.data_dict.values())[0]
            shape = first_var.shape  # (time, N, M) = (time, x, y) after transpose

            # x: dim1 (size N=227), y: dim2 (size M=302)
            self.dimensions['x'] = np.arange(1, shape[1] + 1, dtype=float)
            self.dimensions['y'] = np.arange(1, shape[2] + 1, dtype=float)

            print(f"Dimensions: time={shape[0]}, x={shape[1]}, y={shape[2]}")
        
        return self
    
    def create_datacube(self):
        """Create Sandplover DataCube from processed data."""
        if len(self.data_dict) == 0:
            raise ValueError("No data to create DataCube. Call extract_variables() first.")
        
        try:
            self.cube = DataCube(self.data_dict, dimensions=self.dimensions)
            print(f"DataCube created: {self.cube.shape} (time, y, x)")
            print(f"   Variables: {self.cube.variables}")
        except Exception as e:
            print(f"DataCube creation failed: {e}")
            self.cube = None
        
        return self
    
    def save_datacube(self, output_path, overwrite=True):
        """
        Save DataCube to NetCDF file with swapped x and y dimensions.
        
        Parameters:
        -----------
        output_path : str
            Path to save the NetCDF file
        overwrite : bool
            Whether to overwrite existing file
        """
        if self.cube is None:
            raise ValueError("No DataCube to save. Call create_datacube() first.")
        
        # Handle existing file according to overwrite flag
        if os.path.exists(output_path):
            if overwrite:
                os.remove(output_path)
            else:
                raise FileExistsError(
                    f"Output file '{output_path}' already exists and overwrite is set to False."
                )
        
        # Create xarray Dataset — data is already in (time, x, y) order
        data_vars = {}
        for var_name in self.cube.variables:
            data_vars[var_name] = (
                ['time', 'x', 'y'],
                self.cube[var_name].data
            )

        coords = {
            'time': self.cube.dim0_coords,
            'x': self.cube.dim1_coords,  # x coords (size N=227)
            'y': self.cube.dim2_coords   # y coords (size M=302)
        }
        
        ds_save = xr.Dataset(data_vars, coords=coords)
        
        # Add metadata
        ds_save.attrs['description'] = 'Sandplover DataCube from Delft3D trim file'
        ds_save.attrs['source'] = os.path.basename(self.trim_file_path)
        ds_save.attrs['eta_calculation'] = 'eta = S1 - DPS (water_level - water_depth)'
        ds_save.attrs['velocity_calculation'] = 'magnitude = sqrt(U1^2 + V1^2) from surface layer'
        ds_save.attrs['sediment_calculation'] = 'sand_frac = 1.0 - mud_frac (MUDFRAC)'
        ds_save.attrs['created'] = str(pd.Timestamp.now())
        ds_save.attrs['note'] = 'x and y dimensions are swapped from original Delft3D grid'
        
        # Add variable attributes
        self._add_variable_attributes(ds_save)
        
        # Save as NetCDF
        ds_save.to_netcdf(output_path)
        print(f"Saved: {output_path}")
        
        return self
    
    def _add_variable_attributes(self, dataset):
        """Add attributes to variables in the dataset."""
        if 'velocity' in dataset:
            dataset['velocity'].attrs['long_name'] = 'Velocity magnitude'
            dataset['velocity'].attrs['units'] = 'm/s'
            dataset['velocity'].attrs['source'] = 'sqrt(U1^2 + V1^2)'
        
        if 'mud_frac' in dataset:
            dataset['mud_frac'].attrs['long_name'] = 'Mud fraction'
            dataset['mud_frac'].attrs['units'] = 'dimensionless'
            dataset['mud_frac'].attrs['source'] = 'MUDFRAC'
        
        if 'sand_frac' in dataset:
            dataset['sand_frac'].attrs['long_name'] = 'Sand fraction'
            dataset['sand_frac'].attrs['units'] = 'dimensionless'
            dataset['sand_frac'].attrs['source'] = '1.0 - MUDFRAC'
        
        if 'eta' in dataset:
            dataset['eta'].attrs['long_name'] = 'Bed elevation'
            dataset['eta'].attrs['units'] = 'm'
            dataset['eta'].attrs['source'] = 'S1 - DPS'
        
        if 'water_depth' in dataset:
            dataset['water_depth'].attrs['long_name'] = 'Water depth'
            dataset['water_depth'].attrs['units'] = 'm'
            dataset['water_depth'].attrs['source'] = 'DPS'
    
    def get_statistics(self):
        """Display statistics for all variables in the DataCube."""
        if self.cube is None:
            raise ValueError("No DataCube available. Call create_datacube() first.")
        
        print("Variable Statistics:")
        print("-" * 50)
        
        for var in self.cube.variables:
            data = self.cube[var].data
            print(f"{var}:")
            print(f"  Shape: {data.shape}")
            print(f"  Range: [{np.nanmin(data):.4f}, {np.nanmax(data):.4f}]")
            print(f"  Mean: {np.nanmean(data):.4f}, Std: {np.nanstd(data):.4f}")
        
        return self
    
    def convert(self, output_path=None, show_stats=False):
        """
        Convenience method to run full conversion pipeline.
        
        Parameters:
        -----------
        output_path : str, optional
            Path to save the NetCDF file. If None, won't save.
        show_stats : bool
            Whether to display statistics after conversion
        
        Returns:
        --------
        self : Delft3DConverter
            The converter instance for further operations
        """
        self.load_dataset()
        self.extract_variables()
        self.generate_dimensions()
        self.create_datacube()
        
        if output_path:
            self.save_datacube(output_path)
        
        if show_stats:
            self.get_statistics()
        
        return self
