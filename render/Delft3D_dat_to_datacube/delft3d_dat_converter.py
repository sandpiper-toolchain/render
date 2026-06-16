import numpy as np
import xarray as xr
import pandas as pd
import os
import struct
from sandplover.cube import DataCube


# =============================================================================
# NEFIS Binary Reader
# =============================================================================

class NEFISReader:
    """
    Reader for Deltares NEFIS 5.x binary files (.dat / .def pair).

    NEFIS 5.x format (separate files, little-endian, uint64 addresses):
      .dat  : 60-byte header | 8-byte file-size | GROUP data hash table (997×8) | records
      .def  : 60-byte header | 8-byte file-size | ELEMENT hash (997×8)
                                                  | CELL hash (997×8)
                                                  | GROUP def hash (997×8) | records

    All addresses are 8-byte unsigned integers (uint64, little-endian).
    NIL pointer = 2^64 - 1
    """

    HEADER_LEN   = 60
    ADDR_BYTES   = 8
    N_HASH       = 997          # hash table entries

    # Offsets of hash tables inside each file
    # Byte 0-59: header string, bytes 60-67: file size, bytes 68+: first hash table
    HASH_OFFSET_DAT_GROUP   = HEADER_LEN + ADDR_BYTES                              # 68
    HASH_OFFSET_DEF_ELEMENT = HEADER_LEN + ADDR_BYTES                              # 68
    HASH_OFFSET_DEF_CELL    = HEADER_LEN + ADDR_BYTES + N_HASH * ADDR_BYTES        # 8044
    HASH_OFFSET_DEF_GROUP   = HEADER_LEN + ADDR_BYTES + 2 * N_HASH * ADDR_BYTES   # 16020

    NIL = 2**64 - 1

    def __init__(self, dat_path, def_path):
        self.dat_path = dat_path
        self.def_path = def_path
        self._elements   = {}   # name -> dict
        self._cells      = {}   # name -> dict
        self._grp_defs   = {}   # name -> dict
        self._grp_data   = {}   # name -> dict
        self._read_metadata()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_uint64(f, n=1):
        data = f.read(8 * n)
        if len(data) < 8 * n:
            return None
        if n == 1:
            return struct.unpack_from('<Q', data)[0]
        return list(struct.unpack_from(f'<{n}Q', data))

    @staticmethod
    def _read_uint32(f, n=1):
        data = f.read(4 * n)
        if n == 1:
            return struct.unpack_from('<I', data)[0]
        return list(struct.unpack_from(f'<{n}I', data))

    @staticmethod
    def _read_str(f, n):
        return f.read(n).decode('latin-1', errors='replace').rstrip('\x00').rstrip()

    def _scan_hash_table(self, f, table_offset):
        """Read 997-entry hash table, return list of non-NIL record offsets."""
        f.seek(table_offset)
        raw = f.read(self.N_HASH * self.ADDR_BYTES)
        entries = struct.unpack_from(f'<{self.N_HASH}Q', raw)
        return [e for e in entries if e != self.NIL]

    # ------------------------------------------------------------------
    # Metadata reading
    # ------------------------------------------------------------------

    def _read_metadata(self):
        with open(self.def_path, 'rb') as fdef:
            self._read_elements(fdef)
            self._read_cells(fdef)
            self._read_grp_defs(fdef)
        with open(self.dat_path, 'rb') as fdat:
            self._read_grp_data(fdat)

    def _read_elements(self, fdef):
        """
        Element record layout (180 bytes):
          Link(8) Size(8) Code(8) Name(16) Type(8)
          SizeElm(8) SizeVal(4) Descript(96) [NDim, Dim*5](24)
        """
        offsets = self._scan_hash_table(fdef, self.HASH_OFFSET_DEF_ELEMENT)
        for off in offsets:
            fdef.seek(off)
            _link     = self._read_uint64(fdef)
            _size     = self._read_uint64(fdef)
            _code     = self._read_str(fdef, 8)
            name      = self._read_str(fdef, 16)
            type_str  = self._read_str(fdef, 8)
            size_elm  = self._read_uint64(fdef)
            size_val  = self._read_uint32(fdef)
            _descript = self._read_str(fdef, 96)
            raw_dims  = list(struct.unpack_from('<6I', fdef.read(24)))
            ndim      = raw_dims[0] if raw_dims[0] > 0 else 1
            dims      = raw_dims[1:1 + ndim]
            self._elements[name] = {
                'offset':   off,
                'size_elm': size_elm,
                'size_val': size_val,
                'type':     type_str.strip(),
                'ndim':     ndim,
                'dims':     dims,
            }

    def _read_cells(self, fdef):
        """
        Cell record layout (variable):
          Link(8) Size(8) Code(8) Name(16) CellSize(8) NumElm(4) [Name(16)*NumElm]
        """
        offsets = self._scan_hash_table(fdef, self.HASH_OFFSET_DEF_CELL)
        for off in sorted(offsets):
            fdef.seek(off)
            _link     = self._read_uint64(fdef)
            _size     = self._read_uint64(fdef)
            _code     = self._read_str(fdef, 8)
            name      = self._read_str(fdef, 16)
            cell_size = self._read_uint64(fdef)
            num_elm   = self._read_uint32(fdef)
            elm_names = [self._read_str(fdef, 16) for _ in range(num_elm)]
            self._cells[name] = {
                'offset':    off,
                'cell_size': cell_size,
                'elements':  elm_names,
            }

    def _read_grp_defs(self, fdef):
        """
        Group definition record:
          Link(8) Size(8) Code(8) DefName(16) CelName(16) Dimens[11](44)
          Dimens = [NDim, SizeDim*5, OrderDim*5]
        """
        offsets = self._scan_hash_table(fdef, self.HASH_OFFSET_DEF_GROUP)
        for off in sorted(offsets):
            fdef.seek(off)
            _link    = self._read_uint64(fdef)
            _size    = self._read_uint64(fdef)
            _code    = self._read_str(fdef, 8)
            defname  = self._read_str(fdef, 16)
            celname  = self._read_str(fdef, 16)
            raw_dims = list(struct.unpack_from('<11I', fdef.read(44)))
            ndim     = raw_dims[0] if raw_dims[0] > 0 else 1
            size_dim  = raw_dims[1:1 + ndim]
            order_dim = raw_dims[6:6 + ndim]
            self._grp_defs[defname] = {
                'offset':    off,
                'cel_name':  celname,
                'ndim':      ndim,
                'size_dim':  size_dim,
                'order_dim': order_dim,
            }

    def _read_grp_data(self, fdat):
        """
        Group data record header (416 bytes):
          Link(8) Size(8) RecType(8) Name(16) DefName(16)
          IANames(80) IAValue(20) RANames(80) RAValue(20) SANames(80) SAValue(80)
        Then CellSize(8) for VarDim groups, then 4-level pointer tree.
        """
        offsets = self._scan_hash_table(fdat, self.HASH_OFFSET_DAT_GROUP)
        for off in sorted(offsets):
            fdat.seek(off)
            _link    = self._read_uint64(fdat)
            size     = self._read_uint64(fdat)
            rec_type = fdat.read(8)
            var_dim  = (rec_type[-1:] == b'5')
            name     = self._read_str(fdat, 16)
            defname  = self._read_str(fdat, 16)
            # skip: IANames(80)+IAValue(20)+RANames(80)+RAValue(20)+SANames(80)+SAValue(80) = 360
            fdat.read(360)
            # now at off + 416
            if var_dim:
                cell_size = self._read_uint64(fdat)
            else:
                cell_size = size - 392 - 3 * self.ADDR_BYTES
            self._grp_data[name] = {
                'offset':    off,
                'var_dim':   var_dim,
                'def_name':  defname,
                'cell_size': cell_size,
            }

    # ------------------------------------------------------------------
    # T_len (number of time steps)
    # ------------------------------------------------------------------

    def get_n_timesteps(self, group_name: str) -> int:
        """Determine the number of time steps by scanning the pointer tree."""
        grp = self._grp_data.get(group_name)
        if grp is None:
            raise KeyError(f"Group '{group_name}' not found")

        if not grp['var_dim']:
            gdef = self._grp_defs.get(grp['def_name'], {})
            return gdef.get('size_dim', [1])[0]

        # Pointer tree starts at: offset + 392 + 4*8 = offset + 424
        ptr_start = grp['offset'] + 392 + 4 * self.ADDR_BYTES
        NIL = self.NIL

        with open(self.dat_path, 'rb') as fdat:
            fdat.seek(ptr_start)
            dim = 0
            nbyte = 3
            while nbyte >= 0:
                raw = fdat.read(256 * 8)
                ptrs = list(struct.unpack_from('<256Q', raw))
                k = -1
                for idx in range(255, -1, -1):
                    if ptrs[idx] != NIL:
                        k = idx
                        break
                if k < 0:
                    break
                if nbyte > 0:
                    dim += k * (256 ** nbyte)
                    fdat.seek(ptrs[k])
                else:
                    dim += k
                nbyte -= 1

        return dim

    # ------------------------------------------------------------------
    # Pointer tree navigation
    # ------------------------------------------------------------------

    def _navigate_ptr_tree(self, fdat, grp_offset, time_1based: int):
        """
        Walk the 4-level pointer tree to find the cell-data byte offset
        for the given 1-based time index. Returns None if pointer is NIL.
        """
        NIL = self.NIL
        lvl4_offset = grp_offset + 392 + 4 * self.ADDR_BYTES  # = grp_offset + 424

        t = time_1based
        vd = [t & 0xFF, (t >> 8) & 0xFF, (t >> 16) & 0xFF, (t >> 24) & 0xFF]

        fdat.seek(lvl4_offset)
        ptrs4 = struct.unpack_from('<256Q', fdat.read(256 * 8))
        p3 = ptrs4[vd[3]]
        if p3 == NIL:
            return None

        fdat.seek(p3)
        ptrs3 = struct.unpack_from('<256Q', fdat.read(256 * 8))
        p2 = ptrs3[vd[2]]
        if p2 == NIL:
            return None

        fdat.seek(p2)
        ptrs2 = struct.unpack_from('<256Q', fdat.read(256 * 8))
        p1 = ptrs2[vd[1]]
        if p1 == NIL:
            return None

        fdat.seek(p1)
        ptrs1 = struct.unpack_from('<256Q', fdat.read(256 * 8))
        cell_off = ptrs1[vd[0]]
        if cell_off == NIL:
            return None

        return cell_off

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def read_variable(self, group_name: str, element_name: str):
        """
        Read all time steps of element_name from group_name.
        Returns a numpy array shaped (T, ...) for VarDim groups.
        """
        grp = self._grp_data.get(group_name)
        if grp is None:
            raise KeyError(f"Group '{group_name}' not in .dat")

        gdef = self._grp_defs.get(grp['def_name'])
        if gdef is None:
            raise KeyError(f"Group def '{grp['def_name']}' not in .def")

        cell = self._cells.get(gdef['cel_name'])
        if cell is None:
            raise KeyError(f"Cell '{gdef['cel_name']}' not in .def")

        elm = self._elements.get(element_name)
        if elm is None:
            raise KeyError(f"Element '{element_name}' not in .def")

        # Byte offset of this element within a cell
        elm_offset = 0
        for ename in cell['elements']:
            if ename == element_name:
                break
            e = self._elements.get(ename)
            if e:
                elm_offset += e['size_elm']

        dtype     = self._get_dtype(elm['type'], elm['size_val'])
        elm_shape = tuple(elm['dims']) if elm['dims'] else (1,)
        elm_bytes = int(elm['size_elm'])

        with open(self.dat_path, 'rb') as fdat:
            if not grp['var_dim']:
                # Fixed-dim (e.g. map-const): data immediately after 416-byte header
                data_start = grp['offset'] + 416
                fdat.seek(data_start + elm_offset)
                raw = fdat.read(elm_bytes)
                arr = np.frombuffer(raw, dtype=dtype).copy()
                # NEFIS stores data in Fortran (column-major) order: first dim varies fastest
                return arr.reshape(elm_shape, order='F') if len(elm_shape) > 1 else arr

            # Variable-dim: navigate pointer tree for each time step
            T = self.get_n_timesteps(group_name)
            results = []
            for t in range(T):
                cell_off = self._navigate_ptr_tree(fdat, grp['offset'], t + 1)
                if cell_off is None:
                    results.append(np.full(elm_shape, np.nan, dtype=np.float64))
                    continue
                fdat.seek(cell_off + elm_offset)
                raw = fdat.read(elm_bytes)
                if len(raw) < elm_bytes:
                    results.append(np.full(elm_shape, np.nan, dtype=np.float64))
                    continue
                arr = np.frombuffer(raw, dtype=dtype).copy()
                # NEFIS stores data in Fortran (column-major) order: first dim varies fastest
                results.append(arr.reshape(elm_shape, order='F') if len(elm_shape) > 1 else arr)

            return np.array(results)

    @staticmethod
    def _get_dtype(type_str: str, size_val: int) -> np.dtype:
        t = type_str.strip()
        if t == 'REAL':
            return np.float32 if size_val == 4 else np.float64
        elif t in ('INTEGER', 'LOGICAL'):
            return np.int32 if size_val == 4 else np.int16
        elif t == 'COMPLEX':
            return np.complex64 if size_val == 8 else np.complex128
        else:
            return np.uint8

    def list_groups(self):
        return list(self._grp_data.keys())

    def list_elements(self, group_name):
        grp  = self._grp_data.get(group_name, {})
        gdef = self._grp_defs.get(grp.get('def_name', ''), {})
        cell = self._cells.get(gdef.get('cel_name', ''), {})
        return cell.get('elements', [])


# =============================================================================
# Delft3D DAT Converter  —  mirrors Delft3DConverter interface
# =============================================================================

class Delft3DDatConverter:
    """
    Converts a Delft3D binary NEFIS (.dat/.def) output to a Sandplover DataCube.

    Usage:
        converter = Delft3DDatConverter('trim-DV_run.dat').convert('output.nc', show_stats=True)

    Output variables:
      eta         = -DPS           bed elevation            (map-sed-series)
      water_depth = S1 + DPS       water depth              (map-series + map-sed-series)
      velocity    = sqrt(U1²+V1²)  speed at surface layer   (map-series)
      mud_frac    = MUDFRAC                                  (map-sed-series)
      sand_frac   = 1 - mud_frac

    Time axis: MORFT (morphological time, days) from map-infsed-serie
    Grid:      NMAX × MMAX from map-const
    """

    def __init__(self, dat_file_path: str, def_file_path: str = None):
        self.dat_path = dat_file_path
        if def_file_path is None:
            base = os.path.splitext(dat_file_path)[0]
            self.def_path = base + '.def'
        else:
            self.def_path = def_file_path

        self.reader     = None
        self.data_dict  = {}
        self.dimensions = {}
        self.cube       = None
        self._MORFT     = None

    # ------------------------------------------------------------------

    def open_files(self):
        """Parse NEFIS .dat/.def metadata."""
        print(f"Reading: {os.path.basename(self.dat_path)}")
        print(f"         {os.path.basename(self.def_path)}")
        self.reader = NEFISReader(self.dat_path, self.def_path)
        print(f"Groups found: {self.reader.list_groups()}")
        return self

    def inspect(self):
        """Print available groups and their elements."""
        if self.reader is None:
            self.open_files()
        for grp in self.reader.list_groups():
            T    = self.reader.get_n_timesteps(grp)
            elms = self.reader.list_elements(grp)
            print(f"  {grp:25s}  T={T:4d}  elements: {elms}")
        return self

    # ------------------------------------------------------------------

    def extract_variables(self):
        """Read binary data and compute output variables."""
        if self.reader is None:
            raise RuntimeError("Call open_files() first.")

        # ---- Grid dimensions ----
        NMAX = int(self.reader.read_variable('map-const', 'NMAX').flat[0])
        MMAX = int(self.reader.read_variable('map-const', 'MMAX').flat[0])
        print(f"Grid: NMAX={NMAX}, MMAX={MMAX}")

        # ---- Morphological time axis ----
        MORFT = self.reader.read_variable('map-infsed-serie', 'MORFT')
        MORFT = np.asarray(MORFT, dtype=np.float64).flatten()
        T_len = len(MORFT)
        print(f"Time steps: {T_len}, MORFT range: [{MORFT[0]:.4f}, {MORFT[-1]:.4f}] days")

        # ---- Bed elevation: eta = -DPS ----
        DPS = self._reshape_3d(
            self.reader.read_variable('map-sed-series', 'DPS'), T_len, NMAX, MMAX)
        eta = -DPS.astype(np.float64)
        print(f"eta (= -DPS): [{np.nanmin(eta):.4f}, {np.nanmax(eta):.4f}] m")

        # ---- Water depth: S1 + DPS ----
        S1 = self._reshape_3d(
            self.reader.read_variable('map-series', 'S1'), T_len, NMAX, MMAX)
        water_depth = S1.astype(np.float64) + DPS.astype(np.float64)
        print(f"water_depth: [{np.nanmin(water_depth):.4f}, {np.nanmax(water_depth):.4f}] m")

        # ---- Velocity magnitude (surface layer) ----
        U1 = self._reshape_vel(
            self.reader.read_variable('map-series', 'U1'), T_len, NMAX, MMAX)
        V1 = self._reshape_vel(
            self.reader.read_variable('map-series', 'V1'), T_len, NMAX, MMAX)
        velocity = np.sqrt(U1**2 + V1**2)
        print(f"velocity:    [{np.nanmin(velocity):.4f}, {np.nanmax(velocity):.4f}] m/s")

        # ---- Sediment fractions ----
        MUDFRAC = self._reshape_3d(
            self.reader.read_variable('map-sed-series', 'MUDFRAC'), T_len, NMAX, MMAX)
        MUDFRAC   = MUDFRAC.astype(np.float64)
        sand_frac = 1.0 - MUDFRAC
        print("Sediment fractions calculated")

        # Keep (T, NMAX, MMAX) = (T, x, y) — matches delft3d_converter.py convention
        # x = dim1 (size N=NMAX=227), y = dim2 (size M=MMAX=302)
        self.data_dict['eta']         = eta
        self.data_dict['water_depth'] = water_depth
        self.data_dict['velocity']    = velocity
        self.data_dict['mud_frac']    = MUDFRAC
        self.data_dict['sand_frac']   = sand_frac

        self._MORFT = MORFT
        self._NMAX  = NMAX
        self._MMAX  = MMAX
        print(f"Variables: {list(self.data_dict.keys())}")
        return self

    # ------------------------------------------------------------------

    @staticmethod
    def _reshape_3d(arr, T, NMAX, MMAX):
        arr = np.asarray(arr, dtype=np.float32)
        if arr.shape == (T, NMAX, MMAX):
            return arr
        try:
            return arr.reshape(T, NMAX, MMAX)
        except ValueError:
            raise ValueError(
                f"Cannot reshape array of shape {arr.shape} to ({T},{NMAX},{MMAX})")

    @staticmethod
    def _reshape_vel(arr, T, NMAX, MMAX):
        """
        Handle velocity arrays; extract surface (index 0) layer.
        Delft3D stores U1/V1 as (T, NMAX, MMAX, KMAX) when read via element dims.
        """
        arr = np.asarray(arr, dtype=np.float32)
        # (T, NMAX, MMAX, KMAX) — take surface layer (index 0 along KMAX axis)
        if arr.ndim == 4 and arr.shape[:3] == (T, NMAX, MMAX):
            return arr[:, :, :, 0]
        # (T, KMAX, NMAX, MMAX) — take surface layer (index 0 along KMAX axis)
        if arr.ndim == 4 and arr.shape[2:] == (NMAX, MMAX):
            return arr[:, 0, :, :]
        if arr.shape == (T, NMAX, MMAX):
            return arr
        # Try to infer KMAX and extract surface layer
        total = arr.size
        if total % (T * NMAX * MMAX) == 0:
            kmax = total // (T * NMAX * MMAX)
            return arr.reshape(T, kmax, NMAX, MMAX)[:, 0, :, :]
        return Delft3DDatConverter._reshape_3d(arr, T, NMAX, MMAX)

    # ------------------------------------------------------------------

    def generate_dimensions(self):
        """Build dimension coordinate arrays."""
        if not self.data_dict:
            raise RuntimeError("Call extract_variables() first.")
        first = next(iter(self.data_dict.values()))
        shape = first.shape   # (T, x=NMAX, y=MMAX)
        self.dimensions = {
            'time': self._MORFT,
            'x':    np.arange(1, shape[1] + 1, dtype=float),
            'y':    np.arange(1, shape[2] + 1, dtype=float),
        }
        print(f"Dimensions: time={shape[0]}, x={shape[1]}, y={shape[2]}")
        return self

    def create_datacube(self):
        """Assemble Sandplover DataCube."""
        if not self.data_dict:
            raise RuntimeError("Call extract_variables() first.")
        try:
            self.cube = DataCube(self.data_dict, dimensions=self.dimensions)
            print(f"DataCube created: {self.cube.shape} (time, x, y)")
            print(f"   Variables: {self.cube.variables}")
        except Exception as e:
            print(f"DataCube creation failed: {e}")
            self.cube = None
        return self

    def save_datacube(self, output_path, overwrite=True):
        """Save DataCube to NetCDF."""
        if self.cube is None:
            raise RuntimeError("Call create_datacube() first.")

        if os.path.exists(output_path):
            if overwrite:
                os.remove(output_path)
            else:
                raise FileExistsError(
                    f"Output file '{output_path}' exists and overwrite=False.")

        data_vars = {
            var: (['time', 'x', 'y'], self.cube[var].data)
            for var in self.cube.variables
        }
        coords = {
            'time': self.cube.dim0_coords,
            'x':    self.cube.dim1_coords,
            'y':    self.cube.dim2_coords,
        }

        ds = xr.Dataset(data_vars, coords=coords)
        ds.attrs['description']          = 'Sandplover DataCube from Delft3D NEFIS binary files'
        ds.attrs['source_dat']           = os.path.basename(self.dat_path)
        ds.attrs['source_def']           = os.path.basename(self.def_path)
        ds.attrs['eta_calculation']      = 'eta = -DPS (map-sed-series)'
        ds.attrs['water_depth_calc']     = 'water_depth = S1 + DPS'
        ds.attrs['velocity_calculation'] = 'magnitude = sqrt(U1^2 + V1^2), surface layer'
        ds.attrs['sediment_calculation'] = 'sand_frac = 1.0 - MUDFRAC'
        ds.attrs['time_units']           = 'morphological days (MORFT)'
        ds.attrs['created']              = str(pd.Timestamp.now())
        ds.attrs['note']                 = 'x=N-direction (NMAX), y=M-direction (MMAX), matches delft3d_converter.py convention'

        self._add_variable_attributes(ds)
        ds.to_netcdf(output_path)
        print(f"Saved: {output_path}")
        return self

    @staticmethod
    def _add_variable_attributes(ds):
        attrs_map = {
            'eta':         ('Bed elevation',      'm',             '-DPS'),
            'water_depth': ('Water depth',         'm',             'S1 + DPS'),
            'velocity':    ('Velocity magnitude',  'm/s',           'sqrt(U1^2+V1^2)'),
            'mud_frac':    ('Mud fraction',         'dimensionless', 'MUDFRAC'),
            'sand_frac':   ('Sand fraction',        'dimensionless', '1 - MUDFRAC'),
        }
        for var, (long_name, units, source) in attrs_map.items():
            if var in ds:
                ds[var].attrs.update(
                    {'long_name': long_name, 'units': units, 'source': source})

    def get_statistics(self):
        """Print statistics for all variables."""
        if self.cube is None:
            raise RuntimeError("Call create_datacube() first.")
        print("Variable Statistics:")
        print("-" * 50)
        for var in self.cube.variables:
            data = self.cube[var].data
            print(f"{var}:")
            print(f"  Shape: {data.shape}")
            print(f"  Range: [{np.nanmin(data):.4f}, {np.nanmax(data):.4f}]")
            print(f"  Mean:  {np.nanmean(data):.4f},  Std: {np.nanstd(data):.4f}")
        return self

    def convert(self, output_path=None, show_stats=False):
        """
        Run the full conversion pipeline.

        Parameters
        ----------
        output_path : str, optional
            Path to save the NetCDF DataCube. Skipped if None.
        show_stats : bool
            Print per-variable statistics after conversion.

        Returns
        -------
        self
        """
        self.open_files()
        self.extract_variables()
        self.generate_dimensions()
        self.create_datacube()
        if output_path:
            self.save_datacube(output_path)
        if show_stats:
            self.get_statistics()
        return self
