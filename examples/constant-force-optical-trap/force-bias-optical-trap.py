"""
Example illustrating the application of MBAR to compute a 1D PMF from a series of force-clamp single-molecule experiments.

REFERENCE

    Woodside MT, Behnke-Parks WL, Larizadeh K, Travers K, Herschlag D, and Block SM.
    Nanomechanical measurements of the sequence-dependent folding landscapes of single
    nucleic acid hairpins. PNAS 103:6190, 2006.

"""

# =============================================================================================
# IMPORTS
# =============================================================================================
import subprocess
import time
from pathlib import Path

import numpy as np

import pymbar  # multistate Bennett acceptance ratio analysis (provided by pymbar)
from pymbar import timeseries  # timeseries analysis (provided by pymbar)

# =============================================================================================
# PARAMETERS
# =============================================================================================

PREFIX = "20R55_4T"  # for paper
# prefix = '10R50_4T'
# prefix = '25R50_4T'
# prefix = '30R50_4T'
DIRECTORY = Path("processed-data")
TEMPERATURE = 296.15  # temperature (in K)
NBINS = 50  # number of bins for 1D PMF
OUTPUT_DIRECTORY = Path("output")
PLOT_DIRECTORY = Path("plots")

# =============================================================================================
# CONSTANTS
# =============================================================================================

kB = 1.381e-23  # Boltzmann constant (in J/K)
pN_nm_to_kT = (1.0e-9) * (1.0e-12) / (kB * TEMPERATURE)  # conversion from nM pN to units of kT

# =============================================================================================
# SUBROUTINES
# =============================================================================================


def construct_nonuniform_bins(x_n, nbins):
    """Construct histogram using bins of unequal size to ensure approximately equal population in each bin.

    Parameters
    ----------
    x_n : 1D array of float
        x_n[n] is data point n

    Returns
    -------
    bin_left_boundary_i : 1D array of floats
        data in bin i will satisfy bin_left_boundary_i[i] <= x < bin_left_boundary_i[i+1]
    bin_center_i : 1D array of floats
        bin_center_i[i] is the center of bin i
    bin_width_i : 1D array of floats
        bin_width_i[i] is the width of bin i
    bin_n : 1D array of int32
        bin_n[n] is the bin index (in range(nbins)) of x_n[n]
    """

    # Determine number of samples.
    N = x_n.size

    # Get indices of elements of x_n sorted in order.
    sorted_indices = x_n.argsort()

    # Allocate storage for results.
    bin_left_boundary_i = np.zeros([nbins + 1])
    bin_right_boundary_i = np.zeros([nbins + 1])
    bin_center_i = np.zeros([nbins])
    bin_width_i = np.zeros([nbins])
    bin_n = np.zeros([N])

    # Determine sampled range, adding a little bit to the rightmost range to ensure no samples escape the range.
    x_min = x_n.min()
    x_max = x_n.max()
    x_max += (x_max - x_min) * 1.0e-5

    # Determine bin boundaries and bin assignments.
    for bin_index in range(nbins):
        # indices of first and last data points in this span
        first_index = int(float(N) / float(nbins) * float(bin_index))
        last_index = int(float(N) / float(nbins) * float(bin_index + 1))

        # store left bin boundary
        bin_left_boundary_i[bin_index] = x_n[sorted_indices[first_index]]

        # store assignments
        bin_n[sorted_indices[first_index:last_index]] = bin_index

    # set rightmost boundary
    bin_left_boundary_i[nbins] = x_max

    # Determine bin centers and widths
    for bin_index in range(nbins):
        bin_center_i[bin_index] = (
            bin_left_boundary_i[bin_index] + bin_left_boundary_i[bin_index + 1]
        ) / 2.0
        bin_width_i[bin_index] = (
            bin_left_boundary_i[bin_index + 1] - bin_left_boundary_i[bin_index]
        )

    return bin_left_boundary_i, bin_center_i, bin_width_i, bin_n


# =============================================================================================
# MAIN
# =============================================================================================


def main():
    # read biasing forces for different trajectories
    filename = DIRECTORY / PREFIX + ".forces"
    with open(filename) as infile:
        elements = infile.readline().split()
        K = len(elements)  # number of biasing forces
        biasing_force_k = np.zeros(
            [K]
        )  # biasing_force_k[k] is the constant external biasing force used to collect trajectory k (in pN)
        for k in range(K):
            biasing_force_k[k] = np.float(elements[k])
    print("biasing forces (in pN) = ", biasing_force_k)

    # Determine maximum number of snapshots in all trajectories.
    filename = DIRECTORY / PREFIX + ".trajectories"
    # TODO: Do this without `wc`
    T_max = int(subprocess.getoutput(f"wc -l {filename}").split()[0]) + 1

    # Allocate storage for original (correlated) trajectories
    T_k = np.zeros([K], int)  # T_k[k] is the number of snapshots from umbrella simulation k`
    # x_kt[k,t] is the position of snapshot t from trajectory k (in nm)
    x_kt = np.zeros([K, T_max])

    # Read the trajectories.
    filename = DIRECTORY / PREFIX + ".trajectories"
    print(f"Reading {filename}...")
    with open(filename) as infile:
        for line in infile:
            elements = line.split()
            for k in range(K):
                t = T_k[k]
                x_kt[k, t] = np.float(elements[k])
                T_k[k] += 1

    # Create a list of indices of all configurations in kt-indexing.
    mask_kt = np.zeros([K, T_max], dtype=bool)
    for k in range(0, K):
        mask_kt[k, 0 : T_k[k]] = True
    # Create a list from this mask.
    all_data_indices = np.where(mask_kt)

    # Construct equal-frequency extension bins
    print("binning data...")
    bin_kt = np.zeros([K, T_max], int)
    bin_left_boundary_i, bin_center_i, bin_width_i, bin_assignments = construct_nonuniform_bins(
        x_kt[all_data_indices], NBINS
    )
    bin_kt[all_data_indices] = bin_assignments

    # Compute correlation times.
    N_max = 0
    g_k = np.zeros([K])
    for k in range(K):
        # Compute statistical inefficiency for extension timeseries
        g = timeseries.statistical_inefficiency(x_kt[k, 0 : T_k[k]], x_kt[k, 0 : T_k[k]])
        # store statistical inefficiency
        g_k[k] = g
        print(
            f"timeseries {k + 1:d} : g = {g:.1f}, {int(np.floor(T_k[k] / g)):.0f} "
            f"uncorrelated samples (of {T_k[k]:d} total samples)"
        )
        N_max = max(N_max, int(np.ceil(T_k[k] / g)) + 1)

    # Subsample trajectory position data.
    x_kn = np.zeros([K, N_max])
    bin_kn = np.zeros([K, N_max])
    N_k = np.zeros([K], int)
    for k in range(K):
        # Compute correlation times for potential energy and chi timeseries.
        indices = timeseries.subsample_correlated_data(x_kt[k, 0 : T_k[k]])
        # Store subsampled positions.
        N_k[k] = len(indices)
        x_kn[k, 0 : N_k[k]] = x_kt[k, indices]
        bin_kn[k, 0 : N_k[k]] = bin_kt[k, indices]

    # Set arbitrarynp.zeros for external biasing potential.
    x0_k = np.zeros([K])  # x position corresponding to zero of potential
    for k in range(K):
        x0_k[k] = x_kn[k, 0 : N_k[k]].mean()
    print("x0_k = ", x0_k)

    # Compute bias energies in units of kT.
    # u_kln[k,l,n] is the reduced (dimensionless) relative potential energy of snapshot n from umbrella simulation k evaluated at umbrella l
    u_kln = np.zeros([K, K, N_max])
    for k in range(K):
        for l in range(K):
            # compute relative energy difference from sampled state to each other state
            # U_k(x) = F_k x
            # where F_k is external biasing force
            # (F_k pN) (x nm) (pN /
            # u_kln[k,l,0:N_k[k]] = - pN_nm_to_kT * (biasing_force_k[l] - biasing_force_k[k]) * x_kn[k,0:N_k[k]]
            u_kln[k, l, 0 : N_k[k]] = -pN_nm_to_kT * biasing_force_k[l] * (
                x_kn[k, 0 : N_k[k]] - x0_k[l]
            ) + pN_nm_to_kT * biasing_force_k[k] * (x_kn[k, 0 : N_k[k]] - x0_k[k])

    # DEBUG
    start_time = time.time()

    # Initialize MBAR.
    print("Running MBAR...")
    # TODO: method is uncertainty_method now, but there's no "adaptive" strategy!
    # Which one is it? "approximate", "svd", or "svd-ew"?
    mbar = pymbar.MBAR(
        u_kln, N_k, verbose=True, uncertainty_method="adaptive", relative_tolerance=1.0e-10
    )

    # Compute unbiased energies (all biasing forces are zero).
    # u_kn[k,n] is the reduced potential energy without umbrella restraints of snapshot n of umbrella simulation k
    u_kn = np.zeros([K, N_max])
    for k in range(K):
        #    u_kn[k,0:N_k[k]] = - pN_nm_to_kT * (0.0 - biasing_force_k[k]) * x_kn[k,0:N_k[k]]
        u_kn[k, 0 : N_k[k]] = 0.0 + pN_nm_to_kT * biasing_force_k[k] * (
            x_kn[k, 0 : N_k[k]] - x0_k[k]
        )

    # Compute PMF in unbiased potential (in units of kT).
    print("Computing PMF...")
    results = mbar.compute_pmf(u_kn, bin_kn, NBINS)
    f_i = results["f_i"]
    df_i = results["df_i"]
    # compute estimate of PMF including Jacobian term
    pmf_i = f_i + np.log(bin_width_i)
    # Write out unbiased estimate of PMF
    print("Unbiased PMF (in units of kT)")
    print(f"{'bin':8s} {'f':8s} {'df':8s} {'pmf':8s} {'width':8s}")
    for i in range(NBINS):
        print(
            f"{bin_center_i[i]:8.3f} {f_i[i]:8.3f} {df_i[i]:8.3f} {pmf_i[i]:8.3f} {bin_width_i[i]:8.3f}"
        )

    filename = OUTPUT_DIRECTORY / "pmf-unbiased.out"
    with open(filename, "w") as outfile:
        for i in range(NBINS):
            outfile.write("{:8.3f} {:8.3f} {:8.3f}\n".format(bin_center_i[i], pmf_i[i], df_i[i]))

    # DEBUG
    stop_time = time.time()
    elapsed_time = stop_time - start_time
    print(f"analysis took {elapsed_time:f} seconds")

    # compute observed and expected histograms at each state
    for l in range(K):
        # compute PMF at state l
        results = mbar.compute_pmf(u_kln[:, l, :], bin_kn, NBINS)
        f_i = results["f_i"]
        df_i = results["df_i"]
        # compute estimate of PMF including Jacobian term
        pmf_i = f_i + np.log(bin_width_i)
        # center pmf
        pmf_i -= pmf_i.mean()
        # compute probability distribution
        p_i = np.exp(-f_i + f_i.min())
        p_i /= p_i.sum()
        # compute observed histograms, filtering to within [x_min,x_max] range
        N_i_observed = np.zeros([NBINS])
        dN_i_observed = np.zeros([NBINS])
        for t in range(T_k[l]):
            bin_index = bin_kt[l, t]
            N_i_observed[bin_index] += 1
        N = N_i_observed.sum()
        # estimate uncertainties in observed counts
        for bin_index in range(NBINS):
            dN_i_observed[bin_index] = np.sqrt(
                g_k[l] * N_i_observed[bin_index] * (1.0 - N_i_observed[bin_index] / float(N))
            )
        # compute expected histograms
        N_i_expected = float(N) * p_i
        # only approximate, since correlations df_i df_j are neglected
        dN_i_expected = np.sqrt(float(N) * p_i * (1.0 - p_i))
        # plot
        print("state {:d} ({:f} pN)".format(l, biasing_force_k[l]))
        for bin_index in range(NBINS):
            print(
                "{:8.3f} {:10f} {:10f} +- {:10f}".format(
                    bin_center_i[bin_index],
                    N_i_expected[bin_index],
                    N_i_observed[bin_index],
                    dN_i_observed[bin_index],
                )
            )

        # Write out observed bin counts
        filename = OUTPUT_DIRECTORY / "counts-observed-{:d}.out".format(l)
        with open(filename, "w") as outfile:
            for i in range(NBINS):
                outfile.write(
                    "{:8.3f} {:16f} {:16f}\n".format(
                        bin_center_i[i], N_i_observed[i], dN_i_observed[i]
                    )
                )

        # write out expected bin counts
        filename = OUTPUT_DIRECTORY / "counts-expected-{:d}.out".format(l)
        with open(filename, "w") as outfile:
            for i in range(NBINS):
                outfile.write(
                    "{:8.3f} {:16f} {:16f}\n".format(
                        bin_center_i[i], N_i_expected[i], dN_i_expected[i]
                    )
                )

        # compute PMF from observed counts
        indices = np.where(N_i_observed > 0)[0]
        pmf_i_observed = np.zeros([NBINS])
        dpmf_i_observed = np.zeros([NBINS])
        pmf_i_observed[indices] = -np.log(N_i_observed[indices]) + np.log(bin_width_i[indices])
        pmf_i_observed[indices] -= pmf_i_observed[indices].mean()  # shift observed PMF
        dpmf_i_observed[indices] = dN_i_observed[indices] / N_i_observed[indices]
        # write out observed PMF
        filename = OUTPUT_DIRECTORY / "pmf-observed-{:d}.out".format(l)
        with open(filename, "w") as outfile:
            for i in indices:
                outfile.write(
                    "{:8.3f} {:8.3f} {:8.3f}\n".format(
                        bin_center_i[i], pmf_i_observed[i], dpmf_i_observed[i]
                    )
                )

        # Write out unbiased estimate of PMF
        pmf_i -= pmf_i[indices].mean()  # shift to align with observed
        filename = OUTPUT_DIRECTORY / f"pmf-expected-{l:d}.out"
        with open(filename, "w") as outfile:
            for i in range(NBINS):
                outfile.write(
                    "{:8.3f} {:8.3f} {:8.3f}\n".format(bin_center_i[i], pmf_i[i], df_i[i])
                )

        # make gnuplot plots
        # TODO: Adapt to matplotlib
        biasing_force = biasing_force_k[l]
        filename = PLOT_DIRECTORY / f"pmf-comparison-{l:d}.eps"
        gnuplot_input = f"""
    set term postscript color solid
    set output "{filename:s}"
    set title "{PREFIX:s} - {biasing_force:.}2f pN"
    set xlabel "extension (nm)"
    set ylabel "potential of mean force (kT)"
    plot "{OUTPUT_DIRECTORY:s}/pmf-expected-{l:d}.out" u 1:2:3 with yerrorbars t "MBAR optimal estimate", "{output_directory:s}/pmf-observed-{l:d}.out" u 1:2:3 with yerrorbars t "observed from single experiment"
    """

        gnuplot_input_filename = PLOT_DIRECTORY / "gnuplot.in"
        with open(gnuplot_input_filename, "w") as f:
            f.write(gnuplot_input)

        output = subprocess.getoutput(f"gnuplot < {gnuplot_input_filename}")
        output = subprocess.getoutput(f"epstopdf {filename}")
