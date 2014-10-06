import os
import numpy as np
from pymbar.utils import ensure_type

try:
    root_dir = os.environ["PYMBAR_DATASETS"]
except KeyError:
    root_dir = os.environ["HOME"]

def get_sn(N_k):
    """Assuming the usual ordering of samples and states, guess the
    the state origin of each sample.
    
    Parameters
    ----------
    N_k : np.ndarray, dtype='int', shape=(n_states)
        The number of samples from each state.

    Returns
    -------
    s_n : np.ndarray, dtype=int, shape=(n_samples)
        The (guessed) state of origin of each state.  
    
    Notes
    -----
    The output MAY HAVE EMPTY STATES.
    """
    n_states = len(N_k)
    s_n = np.zeros(sum(N_k), 'int')
    k = 0
    for i in range(n_states):
        for n in range(N_k[i]):
            s_n[k] = i
            k += 1
    return s_n

def load_from_hdf(filename):
    """Load an HDF5 file that was created via save().
    Parameters
    ----------
    filename : str
        filename of HDF5
    
    Returns
    -------

    u_kn : np.ndarray, dtype='float', shape=(n_states, n_samples)
        Reduced potential energies
    N_k : np.ndarray, dtype='int', shape=(n_states)
        Number of samples taken from each state
    s_n : np.ndarray, optional, default=None, dtype=int, shape=(n_samples)
        The state of origin of each state.  If none, guess the state origins.
    
    """
    import tables
    f = tables.File(filename, 'r')
    u_kn = f.root.u_kn[:]
    N_k = f.root.N_k[:]
    s_n = f.root.s_n[:]
    f.close()
    return u_kn, N_k, s_n

def load_gas_data():
    name = "gas-properties"
    u_kn, N_k, s_n = load_from_hdf(os.path.join(root_dir, name, "%s.h5" % name))
    return name, u_kn, N_k, s_n

def load_8proteins_data():
    name = "8proteins"
    u_kn, N_k, s_n = load_from_hdf(os.path.join(root_dir, name, "%s.h5" % name))
    return name, u_kn, N_k, s_n

def save(name, u_kn, N_k, s_n=None):
    """Create an HDF5 dump of an existing MBAR job for later use / testing.
    
    Parameters
    ----------
    name : str
        Name of dataset
    u_kn : np.ndarray, dtype='float', shape=(n_states, n_samples)
        Reduced potential energies
    N_k : np.ndarray, dtype='int', shape=(n_states)
        Number of samples taken from each state
    s_n : np.ndarray, optional, default=None, dtype=int, shape=(n_samples)
        The state of origin of each state.  If none, guess the state origins.

    Notes
    -----
    The output HDF5 files should be readible by the helper funtions pymbar_datasets.py
    """
    import tables
    
    (n_states, n_samples) = u_kn.shape
    
    u_kn = ensure_type(u_kn, 'float', 2, "u_kn or Q_kn", shape=(n_states, n_samples))
    N_k = ensure_type(N_k, 'int64', 1, "N_k", shape=(n_states,))

    if s_n is None:
        s_n = get_sn(N_k)

    s_n = ensure_type(s_n, 'int64', 1, "s_n", shape=(n_samples,))

    hdf_filename = os.path.join("./", "%s.h5" % name)
    f = tables.File(hdf_filename, 'a')
    f.createCArray("/", "u_kn", tables.Float64Atom(), obj=u_kn, filters=tables.Filters(complevel=9, complib="zlib"))
    f.createCArray("/", "N_k", tables.Int64Atom(), obj=N_k, filters=tables.Filters(complevel=9, complib="zlib"))
    f.createCArray("/", "s_n", tables.Int64Atom(), obj=s_n, filters=tables.Filters(complevel=9, complib="zlib"))
    f.close()
