import openpathsampling as paths
from openpathsampling.numerics import SparseHistogram

from collections import Counter
import numpy as np

# should path histogram be moved to the generic histogram.py? Seems to be
# independent of the fact that this is actually OPS
class PathHistogram(SparseHistogram):
    """
    N-dim sparse histogram for trajectories.

    This allows features like interpolating between bins and normalizing the
    histogram to the number of trajectories.
    
    Parameters
    ----------
    left_bin_edges : array-like
        lesser side of the bin (for each direction)
    bin_widths : array-like
        bin (voxel) size
    interpolate : bool or string
        whether to interpolate missing bin visits. String value determines
        interpolation type (currently only "subdivide" allowed). Default
        True gives "subdivide" method, False gives no interpolation.
    per_traj : bool
        whether to normalize per trajectory (instead of per-snapshot)
    """
    def __init__(self, left_bin_edges, bin_widths, interpolate=True,
                 per_traj=True):
        super(PathHistogram, self).__init__(left_bin_edges=left_bin_edges, 
                                            bin_widths=bin_widths)
        if interpolate is True:
            interpolate = "subdivide"
        self.interpolate = interpolate
        self.per_traj = per_traj

    def interpolated_bins(self, old_pt, new_pt):
        """Interpolate between trajectory points.

        Parameters
        ----------
        old_pt : array-like of float
            previous point in CV space
        new_pt : array-like of float
            next point in CV space

        Returns
        -------
        list of array-like of int
            bins which interpolate between old_pt and new_pt (not including
            the bin that old_pt is found in)
        """
        # bins for this do not include the bin of the old point
        # TODO: add a way to have this handle periodic variables as well
        old_bin = self.map_to_bins(old_pt)
        new_bin = self.map_to_bins(new_pt)
        abs_dx = abs(np.asarray(new_bin) - np.asarray(old_bin))
        manhattan_distance = sum(abs_dx)
        bin_list = [new_bin]
        # if the manhattan_distance is 1, we're adjacent
        if manhattan_distance <= 1:
            return bin_list
        # otherwise, use one of the interpolation algos to find bins
        if self.interpolate == "subdivide":
            bin_list = self.subdivide_interpolation(start_pt=old_pt,
                                                    end_pt=new_pt,
                                                    start_bin=old_bin,
                                                    end_bin=new_bin)
        # TODO add other interpolation schemes. 
        return list(set(bin_list) - set([old_bin]))

    def subdivide_interpolation(self, start_pt, end_pt, start_bin, end_bin):
        """Interpolate between bins using recursive division.

        Note that this is probably not the very fastest possible algorithm,
        but an easy one to prove works in arbitrary dimensions.

        Paramters
        ---------
        start_pt : array-like of float
            initial point to interpolate from
        end_pt : array-like of float
            final point to interpolate to
        start_bin : array-like of int
            bin associated with initial point
        end_bin : array-like of int
            bin associated with final point

        Returns
        -------
        list of array-like of int :
            the bins associated with this path
        """
        delta = np.asarray(end_pt) - np.asarray(start_pt)
        mid_pt = start_pt + 0.5 * delta
        mid_bin = self.map_to_bins(mid_pt)
        # check for diagonal first 
        if np.all(abs(np.asarray(end_bin) - np.asarray(start_bin)) == 1):
            left_edges = self.left_bin_edges + self.bin_widths * end_bin
            test_array = (left_edges - start_pt) / delta
            
            if np.allclose(test_array, test_array[0], atol=1e-6):
                return [start_bin, end_bin]
            elif np.allclose(delta, [0.0]*len(delta), atol=1e-6):
                return [start_bin, end_bin]

        manhattan_dist_start = sum(abs(np.asarray(mid_bin) - 
                                       np.asarray(start_bin)))
        manhattan_dist_end = sum(abs(np.asarray(end_bin) - 
                                     np.asarray(mid_bin)))

        # how much work we have to do depends on what's already adjacent
        if start_bin == end_bin:
            return [end_bin]
        elif manhattan_dist_start == 1 and manhattan_dist_end == 1:
            return [start_bin, mid_bin, end_bin]
        # if we're in the same bin, only have one direction to go
        elif mid_bin == start_bin:
            return self.subdivide_interpolation(start_pt=mid_pt,
                                                end_pt=end_pt,
                                                start_bin=mid_bin,
                                                end_bin=end_bin)
        elif mid_bin == end_bin:
            return self.subdivide_interpolation(start_pt=start_pt,
                                                end_pt=mid_pt,
                                                start_bin=start_bin,
                                                end_bin=mid_bin)
        elif manhattan_dist_start == 1:
            return ([start_bin] + 
                    self.subdivide_interpolation(start_pt=mid_pt,
                                                 end_pt=end_pt,
                                                 start_bin=mid_bin,
                                                 end_bin=end_bin))
        elif manhattan_dist_end == 1:
            return ([end_bin] +
                    self.subdivide_interpolation(start_pt=start_pt,
                                                 end_pt=mid_pt,
                                                 start_bin=start_bin,
                                                 end_bin=mid_bin))
        else:
            start_side = self.subdivide_interpolation(start_pt=start_pt,
                                                      end_pt=mid_pt,
                                                      start_bin=start_bin,
                                                      end_bin=mid_bin)
            end_side = self.subdivide_interpolation(start_pt=mid_pt,
                                                    end_pt=end_pt,
                                                    start_bin=mid_bin,
                                                    end_bin=end_bin)
            return start_side + end_side

    def single_trajectory_counter(self, trajectory):
        """
        Calculate the counter (local histogram) for an unweighted trajectory

        Parameters
        ----------
        trajectory : list of array-like
            the reduced space trajectory

        Returns
        -------
        collections.Counter
            histogram counter for this trajectory
        """
        # make a list of every bin visited, possibly interpolating gaps
        bin_list = [self.map_to_bins(trajectory[0])]
        for fnum in range(len(trajectory)-1):
            if self.interpolate:
                bin_list += self.interpolated_bins(trajectory[fnum],
                                                   trajectory[fnum+1])
            else:
                bin_list += [self.map_to_bins(trajectory[fnum+1])]

        local_hist = Counter(bin_list)
        if self.per_traj:
            # keys only exist once, so the counter gives 1 if key present
            local_hist = Counter(local_hist.keys())
        return local_hist

    def add_data_to_histogram(self, trajectories, weights=None):
        """Adds data to the internal histogram counter.

        Parameters
        ----------
        trajectories : list of list of array-like
            input data
        weights : list or None
            weight associated with each datapoint. Default `None` is same
            weights for all

        Returns
        -------
        collections.Counter :
            copy of the current histogram counter
        """
        if weights is None:
            weights = [1.0] * len(trajectories)
        for (traj, w) in zip(trajectories, weights):
            self.add_trajectory(traj, w)
        return self._histogram.copy()

    def add_trajectory(self, trajectory, weight=1.0):
        """Add a single trajectory to internal counter, with given weight

        Parameters
        ----------
        trajectory : list of array-like
            the reduced space trajectory
        weight : float
            the weight of the trajectory. Default 1.0
        """
        local_hist = self.single_trajectory_counter(trajectory)
        local_hist = Counter({k : local_hist[k] * weight
                              for k in local_hist.keys()})
        if self._histogram is None:
            self._histogram = Counter({})
        self._histogram += local_hist
        self.count += weight


#TODO: some of this might be moved to a more generic TrajectoryHistogram,
#      allowing reuse between PathDensityHistogram and FreeEnergyHistogram
class PathDensityHistogram(PathHistogram):
    """Histogram for path density plot.

    Parameters
    ----------
    cvs : list of paths.CollectiveVariable
        the collective variables to define the reduced space
    left_bin_edges : array-like
        lesser side of the bin (for each direction)
    bin_widths : array-like
        bin (voxel) size
    interpolate : bool or string
        whether to interpolate missing bin visits. String value determines
        interpolation type (currently only "subdivide" allowed). Default
        True gives "subdivide" method, False gives no interpolation.
    """
    def __init__(self, cvs, left_bin_edges, bin_widths, interpolate=True):
        super(PathDensityHistogram, self).__init__(
            left_bin_edges=left_bin_edges, 
            bin_widths=bin_widths,
            interpolate=interpolate,
            per_traj=True
        )
        self.cvs = cvs

    def add_data_to_histogram(self, trajectories, weights=None):
        """Adds data to the internal histogram counter.

        Parameters
        ----------
        trajectories : list of :class:`.Trajectory` or :class:`.Trajectory`
            input data
        weights : list or None
            weight associated with each datapoint. Default `None` is same
            weights for all

        Returns
        -------
        collections.Counter :
            copy of the current histogram counter
        """
        if isinstance(trajectories, paths.Trajectory):
            trajectories = [trajectories]
        if weights is None:
            weights = [1.0] * len(trajectories)

        # TODO: add something so that we don't recalc the same traj twice
        for (traj, w) in zip(trajectories, weights):
            cv_traj = [cv(traj) for cv in self.cvs]
            self.add_trajectory(list(zip(*cv_traj)), w)

        return self._histogram.copy()

    def map_to_float_bins(self, trajectory):
        """Map trajectory to the bin value, without rounding bin number.

        Unlike the :class:`.SparseHistogram` version, this allows input of
        either a :class:`.Trajectory` (which is then mapped according to the
        PathDensityHistogram's collective variables), or a list of numbers,
        which is assumed to be the proper CV trajectory (and is the input
        for the sparse histogram version, too).

        Parameters
        ----------
        trajectory : list of array-like or :class:`.Trajectory`
            input trajectory or input CV-based trajectory

        Returns
        -------
        list of array-like :
            un-rounded bin value for each frame in the input trajectory
        """
        if isinstance(trajectory, paths.Trajectory):
            cv_traj = list(zip(*[cv(trajectory) for cv in self.cvs]))
        else:
            cv_traj = trajectory
        return super(PathDensityHistogram, self).map_to_float_bins(cv_traj)
