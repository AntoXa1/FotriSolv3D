"""
Read Athena++ output data files.
"""

# Python modules
import numpy as np

#=========================================================================================

def tab(filename, headings=None, dimensions=1):
  """Read .tab files and return dict or array."""

  # Check for valid number of dimensions
  if dimensions != 1 and dimensions !=2 and dimensions != 3:
    raise AthenaError('Improper number of dimensions')

  # Read raw data
  with open(filename, 'r') as data_file:
    raw_data = data_file.readlines()

  # Organize data into array of numbers
  data_array = []
  first_line = True
  last_line_number = len(raw_data)
  line_number = 0
  for line in raw_data:
    line_number += 1
    if line.split()[0][0] == '#':  # comment line
      continue
    row = []
    col = 0
    for val in line.split():
      col += 1
      if col == 1:
        if first_line:
          i_min = int(val)
        if line_number == last_line_number:
          i_max = int(val)
      elif col == 3 and dimensions >= 2:
        if first_line:
          j_min = int(val)
        if line_number == last_line_number:
          j_max = int(val)
      elif col == 5 and dimensions == 3:
        if first_line:
          k_min = int(val)
        if line_number == last_line_number:
          j_max = int(val)
      else:
        row.append(float(val))
    first_line = False
    data_array.append(row)

  # Reshape array based on number of dimensions
  if dimensions == 1:
    j_min = j_max = 0
  if dimensions <= 2:
    k_min = k_max = 0
  array_shape = (k_max-k_min+1,j_max-j_min+1,i_max-i_min+1,len(row))
  data_array = np.reshape(data_array, array_shape)

  # Store separate variables as dictionary entries if headings given
  if headings is not None:
    data_dict = {}
    for n in range(len(headings)):
      data_dict[headings[n]] = data_array[:,:,:,n]
    return data_dict
  else:
    return data_array

#=========================================================================================

def vtk(filename):
  """Read .vtk files and return dict of arrays of data."""

  # Python module
  import struct

  # Read raw data
  with open(filename, 'r') as data_file:
    raw_data = data_file.read()

  # Skip header
  current_index = 0
  current_char = raw_data[current_index]
  while current_char == '#':
    while current_char != '\n':
      current_index += 1
      current_char = raw_data[current_index]
    current_index += 1
    current_char = raw_data[current_index]

  # Function for skipping though the file
  def skip_string(expected_string):
    expected_string_len = len(expected_string)
    if raw_data[current_index:current_index+expected_string_len] != expected_string:
      raise AthenaError('File not formatted as expected')
    return current_index+expected_string_len

  # Read metadata
  current_index = skip_string('BINARY\nDATASET RECTILINEAR_GRID\nDIMENSIONS ')
  end_of_line_index = current_index + 1
  while raw_data[end_of_line_index] != '\n':
    end_of_line_index += 1
  face_dimensions = map(int, raw_data[current_index:end_of_line_index].split(' '))
  current_index = end_of_line_index + 1

  # Function for reading interface locations
  def read_faces(letter, num_faces):
    identifier_string = '{0}_COORDINATES {1} float\n'.format(letter,num_faces)
    begin_index = skip_string(identifier_string)
    format_string = '>' + 'f'*num_faces
    end_index = begin_index + 4*num_faces
    vals = np.array(struct.unpack(format_string, raw_data[begin_index:end_index]))
    return vals,end_index+1

  # Read interface locations
  x_faces,current_index = read_faces('X', face_dimensions[0])
  y_faces,current_index = read_faces('Y', face_dimensions[1])
  z_faces,current_index = read_faces('Z', face_dimensions[2])

  # Prepare to read quantities defined on grid
  cell_dimensions = np.array([max(dim-1,1)
      for dim in face_dimensions])
  num_cells = cell_dimensions.prod()
  current_index = skip_string('CELL_DATA {0}\n'.format(num_cells))
  if raw_data[current_index:current_index+1] == '\n':
    current_index = skip_string('\n')  # extra newline inserted by join script
  data = {}

  # Function for reading scalar data
  def read_cell_scalars():
    begin_index = skip_string('SCALARS ')
    end_of_word_index = begin_index + 1
    while raw_data[end_of_word_index] != ' ':
      end_of_word_index += 1
    array_name = raw_data[begin_index:end_of_word_index]
    string_to_skip = 'SCALARS {0} float\nLOOKUP_TABLE default\n'.format(array_name)
    begin_index = skip_string(string_to_skip)
    format_string = '>' + 'f'*num_cells
    end_index = begin_index + 4*num_cells
    data[array_name] = struct.unpack(format_string, raw_data[begin_index:end_index])
    dimensions = tuple(cell_dimensions[::-1])
    data[array_name] = np.array(data[array_name]).reshape(dimensions)
    return end_index+1

  # Function for reading vector data
  def read_cell_vectors():
    begin_index = skip_string('VECTORS ')
    end_of_word_index = begin_index + 1
    while raw_data[end_of_word_index] != '\n':
      end_of_word_index += 1
    array_name = raw_data[begin_index:end_of_word_index]
    string_to_skip = 'VECTORS {0}\n'.format(array_name)
    array_name = array_name[:-6]  # remove ' float'
    begin_index = skip_string(string_to_skip)
    format_string = '>' + 'f'*num_cells*3
    end_index = begin_index + 4*num_cells*3
    data[array_name] = struct.unpack(format_string, raw_data[begin_index:end_index])
    dimensions = tuple(np.append(cell_dimensions[::-1],3))
    data[array_name] = np.array(data[array_name]).reshape(dimensions)
    return end_index+1

  # Read quantities defined on grid
  while current_index < len(raw_data):
    expected_string = 'SCALARS'
    expected_string_len = len(expected_string)
    if raw_data[current_index:current_index+expected_string_len] == expected_string:
      current_index = read_cell_scalars()
      continue
    expected_string = 'VECTORS'
    expected_string_len = len(expected_string)
    if raw_data[current_index:current_index+expected_string_len] == expected_string:
      current_index = read_cell_vectors()
      continue
    raise AthenaError('File not formatted as expected')
  return x_faces,y_faces,z_faces,data

#=========================================================================================

def athdf(filename, data=None, quantities=None, dtype=np.float32, level=None,
    subsample=False, fast_restrict=False, vol_func=None, vol_params=None,
    center_func_1=None, center_func_2=None, center_func_3=None):
  """Read .athdf files and populate dict of arrays of data."""

  # Python modules
  import sys
  import warnings
  import h5py

  # Open file
  with h5py.File(filename, 'r') as f:

    # Extract size information
    max_level = f.attrs['MaxLevel']
    if level is None:
      level = max_level
    block_size = f.attrs['MeshBlockSize']
    root_grid_size = f.attrs['RootGridSize']
    nx1 = root_grid_size[0] * 2**level if block_size[0] > 1 else 1
    nx2 = root_grid_size[1] * 2**level if block_size[1] > 1 else 1
    nx3 = root_grid_size[2] * 2**level if block_size[2] > 1 else 1

    lx1 = nx1 / block_size[0]
    lx2 = nx2 / block_size[1]
    lx3 = nx3 / block_size[2]
    num_extended_dims = (nx1 > 1) + (nx2 > 1) + (nx3 > 1)

    # Set volume function for preset coordinates if needed
    coord = f.attrs['Coordinates']; 
    
    print(" ============== \n", coord)

    if level < max_level and not subsample and not fast_restrict and vol_func is None:
      x1_rat = f.attrs['RootGridX1'][2]
      x2_rat = f.attrs['RootGridX2'][2]
      x3_rat = f.attrs['RootGridX3'][2]
      if coord == 'cartesian' or coord == 'minkowski' or coord == 'tilted' \
          or coord == 'sinusoidal':
        if (nx1 == 1 or x1_rat == 1.0) and (nx2 == 1 or x2_rat == 1.0) and \
            (nx3 == 1 or x3_rat == 1.0):
          fast_restrict = True
        else:
          vol_func = lambda xm,xp,ym,yp,zm,zp: (xp-xm) * (yp-ym) * (zp-zm)
      elif coord == 'cylindrical':
        if nx1 == 1 and (nx2 == 1 or x2_rat == 1.0) and (nx3 == 1 or x3_rat == 1.0):
          fast_restrict = True
        else:
          vol_func = lambda rm,rp,phim,phip,zm,zp: (rp**2-rm**2) * (phip-phim) * (zp-zm)
      elif coord == 'spherical_polar' or coord == 'schwarzschild':
        if nx1 == 1 and nx2 == 1 and (nx3 == 1 or x3_rat == 1.0):
          fast_restrict = True
        else:
          vol_func = lambda rm,rp,thetam,thetap,phim,phip: \
              (rp**3-rm**3) * abs(np.cos(thetam)-np.cos(thetap)) * (phip-phim)
      elif coord == 'kerr-schild':
        if nx1 == 1 and nx2 == 1 and (nx3 == 3 or x3_rat == 1.0):
          fast_restrict = True
        else:
          a = vol_params[0]
          def vol_func(rm, rp, thetam, thetap, phim, phip):
            cosm = np.cos(thetam)
            cosp = np.cos(thetap)
            return \
                ((rp**3-rm**3) * abs(cosm-cosp) + a**2 * (rp-rm) * abs(cosm**3-cosp**3)) \
                * (phip-phim)
      else:
        raise AthenaError('Coordinates not recognized')

    # Set cell center functions for preset coordinates
    if center_func_1 is None:
      if coord == 'cartesian' or coord == 'minkowski' or coord == 'tilted' \
          or coord == 'sinusoidal' or coord == 'kerr-schild':
        center_func_1 = lambda xm,xp : 0.5*(xm+xp)
      elif coord == 'cylindrical':
        center_func_1 = lambda xm,xp : 2.0/3.0 * (xp**3-xm**3) / (xp**2-xm**2)
      elif coord == 'spherical_polar':
        center_func_1 = lambda xm,xp : 3.0/4.0 * (xp**4-xm**4) / (xp**3-xm**3)
      elif coord == 'schwarzschild':
        center_func_1 = lambda xm,xp : (0.5*(xm**3+xp**3)) ** 1.0/3.0
      else:
        raise AthenaError('Coordinates not recognized')
    if center_func_2 is None:
      if coord == 'cartesian' or coord == 'cylindrical' or coord == 'minkowski' \
          or coord == 'tilted' or coord == 'sinusoidal' or coord == 'kerr-schild':
        center_func_2 = lambda xm,xp : 0.5*(xm+xp)
      elif coord == 'spherical_polar':
        def center_func_2(xm, xp):
          sm = np.sin(xm)
          cm = np.cos(xm)
          sp = np.sin(xp)
          cp = np.cos(xp)
          return (sp-xp*cp - sm+xm*cm) / (cm-cp)
      elif coord == 'schwarzschild':
        center_func_2 = lambda xm,xp : np.arccos(0.5*(np.cos(xm)+np.cos(xp)))
      else:
        raise AthenaError('Coordinates not recognized')
    if center_func_3 is None:
      if coord == 'cartesian' or coord == 'cylindrical' or coord == 'spherical_polar' \
          or coord == 'minkowski' or coord == 'tilted' or coord == 'sinusoidal' \
          or coord == 'schwarzschild' or coord == 'kerr-schild':
        center_func_3 = lambda xm,xp : 0.5*(xm+xp)
      else:
        raise AthenaError('Coordinates not recognized')

    # Check output level compared to max level in file
    if level < max_level and not subsample and not fast_restrict:
      warnings.warn('Exact restriction being used: performance severely affected; see' \
          + ' documentation', AthenaWarning)
      sys.stderr.flush()
    if level > max_level:
      warnings.warn('Requested refinement level higher than maximum level in file: all' \
          + ' cells will be prolongated', AthenaWarning)
      sys.stderr.flush()

    # Check that subsampling and/or fast restriction will work if needed
    if level < max_level and (subsample or fast_restrict):
      max_restrict_factor = 2**(max_level-level)
      for current_block_size in block_size:
        if current_block_size != 1 and current_block_size%max_restrict_factor != 0:
          raise AthenaError('Block boundaries at finest level must be cell boundaries' \
              + ' at desired level for subsampling or fast restriction to work')

    # Create list of all quantities if none given
    file_quantities = f.attrs['VariableNames'][:]
    coord_quantities = ('x1f', 'x2f', 'x3f', 'x1v', 'x2v', 'x3v')
    if data is not None:
      quantities = data.values()
    elif quantities is None:
      quantities = file_quantities
    else:
      for q in quantities:
        if q not in file_quantities and q not in coord_quantities:
          possibilities = '", "'.join(file_quantities)
          possibilities = '"' + possibilities + '"'
          error_string = 'Quantity not recognized: file does not include "{0}" but does' \
              + ' include {1}'
          raise AthenaError(error_string.format(q,possibilities))
    quantities = [str(q) for q in quantities if q not in coord_quantities]

    # Get metadata describing file layout
    num_blocks = f.attrs['NumMeshBlocks']
    dataset_names = f.attrs['DatasetNames'][:]
    dataset_sizes = f.attrs['NumVariables'][:]
    dataset_sizes_cumulative = np.cumsum(dataset_sizes)
    variable_names = f.attrs['VariableNames'][:]

    print("variable_names = ",  variable_names)

    levels = f['Levels'][:]
    logical_locations = f['LogicalLocations'][:]
    quantity_datasets = []
    quantity_indices = []
    for q in quantities:
      var_num = np.where(variable_names == q)[0][0]
      dataset_num = np.where(dataset_sizes_cumulative > var_num)[0][0]
      if dataset_num == 0:
        dataset_index = var_num
      else:
        dataset_index = var_num - dataset_sizes_cumulative[dataset_num-1]
      quantity_datasets.append(dataset_names[dataset_num])
      quantity_indices.append(dataset_index)

    # Locate fine block for coordinates in case of slice
    fine_block = np.where(levels == max_level)[0][0]
    x1m = f['x1f'][fine_block,0]
    x1p = f['x1f'][fine_block,1]
    x2m = f['x2f'][fine_block,0]
    x2p = f['x2f'][fine_block,1]
    x3m = f['x3f'][fine_block,0]
    x3p = f['x3f'][fine_block,1]

    # Prepare arrays for data and bookkeeping
    if data is not None:
      for q in quantities:
        data[q].fill(0.0)
    else:
      data = {}
      for q in quantities:
        data[q] = np.zeros((nx3, nx2, nx1), dtype=dtype)
    if not subsample and not fast_restrict and max_level > level:
      restricted_data = np.zeros((lx3, lx2, lx1), dtype=bool)

    # Populate coordinate arrays
    nx_vals = (nx1, nx2, nx3)
    center_funcs = (center_func_1, center_func_2, center_func_3)
    for d,nx,center_func in zip(range(1, 4), nx_vals, center_funcs):
      if nx == 1:
        xm = (x1m, x2m, x3m)[d-1]
        xp = (x1p, x2p, x3p)[d-1]
        data['x'+repr(d)+'f'] = np.array([xm, xp])
      else:
        xmin = f.attrs['RootGridX'+repr(d)][0]
        xmax = f.attrs['RootGridX'+repr(d)][1]
        xrat_root = f.attrs['RootGridX'+repr(d)][2]
        if (xrat_root == 1.0):
          data['x'+repr(d)+'f'] = np.linspace(xmin, xmax, nx+1)
        else:
          xrat = xrat_root ** (1.0 / 2**level)
          data['x'+repr(d)+'f'] = \
              xmin + (1.0-xrat**np.arange(nx+1)) / (1.0-xrat**nx) * (xmax-xmin)
      data['x'+repr(d)+'v'] = np.empty(nx)
      for i in range(nx):
        data['x'+repr(d)+'v'][i] = \
            center_func(data['x'+repr(d)+'f'][i], data['x'+repr(d)+'f'][i+1])

    # Go through blocks in data file
    for block_num in range(num_blocks):

      # Extract location information
      block_level = levels[block_num]
      block_location = logical_locations[block_num,:]

      # Prolongate coarse data and copy same-level data
      if block_level <= level:

        # Calculate scale (number of copies per dimension)
        s = 2**(level-block_level)

        # Calculate fine-level begin indices
        il = block_location[0] * block_size[0] * s if nx1 > 1 else 0
        jl = block_location[1] * block_size[1] * s if nx2 > 1 else 0
        kl = block_location[2] * block_size[2] * s if nx3 > 1 else 0

        # Calculate fine-level end indices
        iu = il + block_size[0] * s if nx1 > 1 else 1
        ju = jl + block_size[1] * s if nx2 > 1 else 1
        ku = kl + block_size[2] * s if nx3 > 1 else 1

        # Assign values
        for q,dataset,index in zip(quantities, quantity_datasets, quantity_indices):
          block_data = f[dataset][index,block_num,:]
          if s > 1:
            if nx1 > 1:
              block_data = np.repeat(block_data, s, axis=2)
            if nx2 > 1:
              block_data = np.repeat(block_data, s, axis=1)
            if nx3 > 1:
              block_data = np.repeat(block_data, s, axis=0)
          data[q][kl:ku,jl:ju,il:iu] = block_data

      # Restrict fine data
      else:

        # Apply subsampling
        if subsample:

          # Calculate scale (fine-level stride)
          s = 2**(block_level-level)

          # Calculate coarse-level begin indices
          il = block_location[0] * block_size[0] / s if nx1 > 1 else 0
          jl = block_location[1] * block_size[1] / s if nx2 > 1 else 0
          kl = block_location[2] * block_size[2] / s if nx3 > 1 else 0

          # Calculate coarse-level end indices
          iu = il + block_size[0] / s if nx1 > 1 else 1
          ju = jl + block_size[1] / s if nx2 > 1 else 1
          ku = kl + block_size[2] / s if nx3 > 1 else 1

          # Calculate fine-level offsets (nearest cell at or below center)
          o1 = s/2 - 1 if nx1 > 1 else 0
          o2 = s/2 - 1 if nx2 > 1 else 0
          o3 = s/2 - 1 if nx3 > 1 else 0

          # Assign values
          for q,dataset,index in zip(quantities, quantity_datasets, quantity_indices):
            data[q][kl:ku,jl:ju,il:iu] = f[dataset][index,block_num,o1::s,o2::s,o3::s]

        # Apply fast (uniform Cartesian) restriction
        elif fast_restrict:

          # Calculate scale (fine-level stride)
          s = 2**(block_level-level)

          # Calculate coarse-level begin indices
          il = block_location[0] * block_size[0] / s if nx1 > 1 else 0
          jl = block_location[1] * block_size[1] / s if nx2 > 1 else 0
          kl = block_location[2] * block_size[2] / s if nx3 > 1 else 0

          # Calculate coarse-level end indices
          iu = il + block_size[0] / s if nx1 > 1 else 1
          ju = jl + block_size[1] / s if nx2 > 1 else 1
          ku = kl + block_size[2] / s if nx3 > 1 else 1

          # Calculate fine-level offsets
          io_vals = range(s) if nx1 > 1 else (0,)
          jo_vals = range(s) if nx2 > 1 else (0,)
          ko_vals = range(s) if nx3 > 1 else (0,)

          # Assign values
          for q,dataset,index in zip(quantities, quantity_datasets, quantity_indices):
            for ko in ko_vals:
              for jo in jo_vals:
                for io in io_vals:
                  data[q][kl:ku,jl:ju,il:iu] \
                      += f[dataset][index,block_num,ko::s,jo::s,io::s]
            data[q][kl:ku,jl:ju,il:iu] /= s**num_extended_dims

        # Apply exact (volume-weighted) restriction
        else:

          # Calculate scale
          s = 2**(block_level-level)

          # Calculate fine-level indices
          ir_vals = np.arange(block_size[0])
          jr_vals = np.arange(block_size[1])
          kr_vals = np.arange(block_size[2])

          # Calculate coarse-level indices
          i_vals = (ir_vals + (nx1 > 1) * block_location[0] * block_size[0]) / s
          j_vals = (jr_vals + (nx2 > 1) * block_location[1] * block_size[1]) / s
          k_vals = (kr_vals + (nx3 > 1) * block_location[2] * block_size[2]) / s

          # Accumulate values
          for k,kr in zip(k_vals, kr_vals):
            if nx3 > 1:
              x3m = f['x3f'][block_num,kr]
              x3p = f['x3f'][block_num,kr+1]
            for j,jr in zip(j_vals, jr_vals):
              if nx2 > 1:
                x2m = f['x2f'][block_num,jr]
                x2p = f['x2f'][block_num,jr+1]
              for i,ir in zip(i_vals, ir_vals):
                if nx1 > 1:
                  x1m = f['x1f'][block_num,ir]
                  x1p = f['x1f'][block_num,ir+1]
                vol = vol_func(x1m, x1p, x2m, x2p, x3m, x3p)
                for q,dataset,index in \
                    zip(quantities, quantity_datasets, quantity_indices):
                  data[q][k,j,i] += f[dataset][index,block_num,kr,jr,ir] * vol
          loc1 = (nx1 > 1 ) * block_location[0] / s
          loc2 = (nx2 > 1 ) * block_location[1] / s
          loc3 = (nx3 > 1 ) * block_location[2] / s
          restricted_data[loc3,loc2,loc1] = True

    # Remove volume factors from restricted data
    if level < max_level and not subsample and not fast_restrict:
      for loc3 in range(lx3):
        for loc2 in range(lx2):
          for loc1 in range(lx1):
            if restricted_data[loc3,loc2,loc1]:
              il = loc1 * block_size[0]
              jl = loc2 * block_size[1]
              kl = loc3 * block_size[2]
              iu = il + block_size[0]
              ju = jl + block_size[1]
              ku = kl + block_size[2]
              for k in range(kl, ku):
                if nx3 > 1:
                  x3m = data['x3f'][k]
                  x3p = data['x3f'][k+1]
                for j in range(jl, ju):
                  if nx2 > 1:
                    x2m = data['x2f'][j]
                    x2p = data['x2f'][j+1]
                  for i in range(il, iu):
                    if nx1 > 1:
                      x1m = data['x1f'][i]
                      x1p = data['x1f'][i+1]
                    vol = vol_func(x1m, x1p, x2m, x2p, x3m, x3p)
                    for q in quantities:
                      data[q][k,j,i] /= vol

  return data

#=========================================================================================

class AthenaError(RuntimeError):
  """General exception class for Athena++ read functions."""
  pass

class AthenaWarning(RuntimeWarning):
  """General warning class for Athena++ read functions."""
  pass
