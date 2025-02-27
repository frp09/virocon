"""
Models for the joint probability distribution.
"""

from abc import ABC, abstractmethod

import numpy as np

import scipy.integrate as integrate

from virocon.distributions import ConditionalDistribution
from virocon.intervals import NumberOfIntervalsSlicer

__all__ = ["GlobalHierarchicalModel"]


class MultivariateModel(ABC):
    """
    Abstract base class for MultivariateModel.
    
    Statistical model of multiple variables.
    
    """

    @abstractmethod
    def pdf(self, *args, **kwargs):
        """
        Probability density function.
        
        """
        pass

    @abstractmethod
    def cdf(self, *args, **kwargs):
        """
        Cumulative distribution function.
        
        """
        pass

    @abstractmethod
    def marginal_pdf(self, *args, **kwargs):
        """
        Marginal probability density function.
        
        """
        pass

    @abstractmethod
    def marginal_cdf(self, *args, **kwargs):
        """
        Marginal cumulative distribution function.
        
        """
        pass

    @abstractmethod
    def marginal_icdf(self, *args, **kwargs):
        """
        Marginal inverse cumulative distribution function.
        
        """
        pass

    @abstractmethod
    def draw_sample(self, *args, **kwargs):
        """
        Draw a random sample of length n.
       
        """
        pass


class GlobalHierarchicalModel(MultivariateModel):
    """
    Hierarchical probabilistic model.
    
    Probabilistic model that covers the complete range of an environmental 
    variable ("global"), following a particular hierarchical dependence 
    structure. The factorization describes a hierarchy where a random 
    variable with index i can only depend upon random variables with 
    indices less than i [1]_ .
       
    Parameters
    ----------   
    dist_descriptions : dict
        Description of the distributions.
        
    Attributes
    ----------
    distributions : list
        The distributions used in the GlobalHierachicalModel.
    conditional_on : list
        Indicates the dependencies between the variables of the model. One 
        entry per distribution/dimension. Contains either None or int. If the 
        ith entry is None, the ith distribution is unconditional. If the ith 
        entry is an int j, the ith distribution depends on the jth dimension.
    interval_slicers : list
        One interval slicer per dimension. The interval slicer used for 
        slicing the intervals of the corresponding dimension, when necessary 
        during fitting.
    n_dim : int
        The number of dimensions, i.e. the number of variables of the model.
        
       
    References
    ----------
    .. [1] Haselsteiner, A.F.; Sander, A.; Ohlendorf, J.H.; Thoben, K.D. (2020)
        Global hierarchical models for wind and wave contours: physical
        interpretations of the dependence functions. OMAE 2020, Fort Lauderdale,
        USA. Proceedings of the 39th International Conference on Ocean, 
        Offshore and Arctic Engineering.
    
    Examples
    --------
    Create a Hs-Tz model and fit it to the available data. The following 
    example follows the methodology of OMAE2020 [1]_ . 
    
    Example 1.1: 
        
    Load the predefined OMAE 2020 model of Hs-Tz.
  
    >>> from virocon import (GlobalHierarchicalModel, get_OMAE2020_Hs_Tz, 
    ...                      read_ec_benchmark_dataset) 
    >>> data = read_ec_benchmark_dataset("datasets/ec-benchmark_dataset_D_1year.txt")
    >>> dist_descriptions, fit_descriptions, semantics = get_OMAE2020_Hs_Tz()
    >>> ghm = GlobalHierarchicalModel(dist_descriptions)
    >>> ghm.fit(data, fit_descriptions=fit_descriptions)
    
    Example 1.2: 
        
    Create the same OMEA 2020 model manually.
    
    >>> from virocon import (DependenceFunction, ExponentiatedWeibullDistribution,
    ...                      LogNormalDistribution, WidthOfIntervalSlicer) 
    
    >>> def _asymdecrease3(x, a, b, c):
    ...     return a + b / (1 + c * x)
    
    >>> def _lnsquare2(x, a, b, c):
    ...     return np.log(a + b * np.sqrt(np.divide(x, 9.81)))
    
    >>> bounds = [(0, None), 
    ...           (0, None), 
    ...           (None, None)]
    
    >>> sigma_dep = DependenceFunction(_asymdecrease3, bounds=bounds)
    >>> mu_dep = DependenceFunction(_lnsquare2, bounds=bounds)
    
    >>> dist_description_hs = {"distribution" : ExponentiatedWeibullDistribution(),
    ...                        "intervals" : WidthOfIntervalSlicer(width=0.5, 
    ...                                                            min_n_points=50)
    ...                       }
    
    >>> dist_description_tz = {"distribution" : LogNormalDistribution(),
    ...                        "conditional_on" : 0,
    ...                        "parameters" : {"sigma" : sigma_dep,
    ...                                        "mu": mu_dep,
    ...                                        },
    ...                       }

    
    >>> dist_descriptions = [dist_description_hs, dist_description_tz]
    
    >>> fit_description_hs = {"method" : "wlsq", "weights" : "quadratic"}
    >>> fit_descriptions = [fit_description_hs, None]
    
    >>> semantics = {"names" : ["Significant wave height", "Zero-crossing wave period"],
    ...              "symbols" : ["H_s", "T_z"],
    ...              "units" : ["m", "s"]
    ...              }
    
    >>> ghm = GlobalHierarchicalModel(dist_descriptions)
    >>> ghm.fit(data, fit_descriptions=fit_descriptions)
    
    """

    _dist_description_keys = {
        "distribution",
        "intervals",
        "conditional_on",
        "parameters",
    }

    def __init__(self, dist_descriptions):
        self.distributions = []
        self.conditional_on = []
        self.interval_slicers = []
        self.n_dim = len(dist_descriptions)
        self._check_dist_descriptions(dist_descriptions)
        for dist_desc in dist_descriptions:
            # dist_class = dist_desc["distribution"]
            dist = dist_desc["distribution"]
            self.interval_slicers.append(
                dist_desc.get("intervals", NumberOfIntervalsSlicer(n_intervals=10))
            )

            if "conditional_on" in dist_desc:
                self.conditional_on.append(dist_desc["conditional_on"])
                dist = ConditionalDistribution(dist, dist_desc["parameters"])
                self.distributions.append(dist)
            else:
                self.conditional_on.append(None)
                self.distributions.append(dist)

        if self.conditional_on[0] is not None:
            raise RuntimeError(
                "Illegal state encountered. The first dimension "
                "has to be independent, but was conditional on "
                f"{self.conditional_on[0]}."
            )

    def __repr__(self):
        name = "GlobalHierarchicalModel"
        dists = repr(self.distributions)
        # dists = dists.replace("), ", "),\n")
        cond_on = repr(self.conditional_on)

        return f"{name}(distributions={dists}, conditional_on={cond_on})"

    def _check_dist_descriptions(self, dist_descriptions):
        for i, dist_desc in enumerate(dist_descriptions):
            if not "distribution" in dist_desc:
                raise ValueError(
                    "Mandatory key 'distribution' missing in "
                    f"dist_description for dimension {i}"
                )

            if "conditional_on" in dist_desc and not "parameters" in dist_desc:
                raise ValueError(
                    "For conditional distributions the "
                    "dist_description key 'parameters' "
                    f"is mandatory but was missing for dimension {i}."
                )

            unknown_keys = set(dist_desc).difference(self._dist_description_keys)
            if len(unknown_keys) > 0:
                raise ValueError(
                    "Unknown key(s) in dist_description for "
                    f"dimension {i}."
                    f"Known keys are {self._dist_description_keys}, "
                    f"but found {unknown_keys}."
                )

    def _split_in_intervals(self, data, dist_idx, conditioning_idx):
        slicer = self.interval_slicers[conditioning_idx]
        conditioning_data = data[:, conditioning_idx]
        interval_slices, interval_centers, interval_boundaries = slicer.slice_(
            conditioning_data
        )

        dist_data = [data[int_slice, dist_idx] for int_slice in interval_slices]

        return dist_data, interval_centers, interval_boundaries

    def _check_and_fill_fit_desc(self, fit_descriptions):
        default_fit_desc = {"method": "mle", "weights": None}
        if fit_descriptions is None:
            fit_descriptions = [default_fit_desc for i in range(self.n_dim)]

        else:
            if len(fit_descriptions) != self.n_dim:
                raise ValueError(
                    "fit_description must have one entry per dimension, but "
                    f"a length of {len(fit_descriptions)} != {self.n_dim} was found."
                )

            for i in range(len(fit_descriptions)):
                if fit_descriptions[i] is None:
                    fit_descriptions[i] = default_fit_desc
                else:
                    if not "method" in fit_descriptions[i]:
                        raise ValueError(
                            "Mandatory key 'method' missing in "
                            f"fit_description for dimension {i}."
                        )
                    if not "weights" in fit_descriptions[i]:
                        fit_descriptions[i]["weights"] = None

        return fit_descriptions

    def fit(self, data, fit_descriptions=None):
        """
        Fit joint model to data.
        
        Method of estimating the parameters of a probability distribution to
        given data.
        
        Parameters
        ----------
        data : array-like
            The data that should be used to fit the joint model. 
            Shape: (number of realizations, n_dim)
        fit_description : dict
            Description of the fit method. Defaults to None.

        """

        data = np.array(data)

        fit_descriptions = self._check_and_fill_fit_desc(fit_descriptions)

        if data.shape[-1] != self.n_dim:
            raise ValueError(
                "The dimension of data does not match the "
                "dimension of the model. "
                f"The model has {self.n_dim} dimensions, "
                f"but the data has {data.shape[-1]} dimensions."
            )

        for i in range(self.n_dim):
            dist = self.distributions[i]
            conditioning_idx = self.conditional_on[i]
            fit_method = fit_descriptions[i]["method"]
            weights = fit_descriptions[i]["weights"]

            if conditioning_idx is None:
                dist.fit(data[:, i], fit_method, weights)
            else:
                (
                    dist_data,
                    conditioning_data,
                    conditioning_interval_boundaries,
                ) = self._split_in_intervals(data, i, conditioning_idx)
                # dist data  is a list of ndarray
                # and conditioning_data is a list of interval points
                dist.fit(
                    dist_data,
                    conditioning_data,
                    conditioning_interval_boundaries,
                    fit_method,
                    weights,
                )

            self.distributions[
                i
            ] = dist  # TODO is the writeback necessary? -> probably not

    def pdf(self, x):
        """
        Probability density function.
        
        Parameters
        ----------
        x : array_like
            Points at which the pdf is evaluated.
            Shape: (n, n_dim), where n is the number of points at which the 
            pdf should be evaluated.
            
        """

        # Ensure that x is a 2D numpy array.
        x = np.array(x)
        if x.ndim == 1:
            x = np.array([x])

        x = np.asarray_chkfinite(x)
        fs = np.empty_like(x)

        fs[:, 0] = self.distributions[0].pdf(x[:, 0])

        for i in range(1, self.n_dim):
            if self.conditional_on[i] is None:
                fs[:, i] = self.distributions[i].pdf(x[:, i])
            else:
                cond_idx = self.conditional_on[i]
                fs[:, i] = self.distributions[i].pdf(x[:, i], given=x[:, cond_idx])

        return np.prod(fs, axis=-1)

    def cdf(self, x):
        """
        Cumulative distribution function.
        
        Parameters
        ----------
        x : array_like
            Points at which the cdf is evaluated.
            Shape: (n, n_dim), where n is the number of points at which the 
            cdf should be evaluated.
        
        """

        # Ensure that x is a 2D numpy array.
        x = np.array(x)
        if x.ndim == 1:
            x = np.array([x])

        x = np.asarray_chkfinite(x)

        n_dim = self.n_dim
        integral_order = list(range(n_dim))

        def get_integral_func():
            arg_order = integral_order

            def integral_func(*args):
                assert len(args) == n_dim
                # sort arguments as expected by pdf (the models order)
                x = np.array(args)[np.argsort(arg_order)].reshape((1, n_dim))
                return self.pdf(x)

            return integral_func

        lower_integration_limits = [0] * n_dim

        integral_func = get_integral_func()

        p = np.empty(len(x))
        for i in range(len(x)):

            integration_limits = [
                (lower_integration_limits[j], x[i, j]) for j in range(n_dim)
            ]

            p[i], error = integrate.nquad(integral_func, integration_limits)

        return p

    def marginal_pdf(self, x, dim):
        """
        Marginal probability density function.
                
        Parameters
        ----------
        x : array_like
            Points at which the pdf is evaluated.
            Shape: 1-dimensional
        dim : int
            The dimension for which the marginal is calculated.
   
        """

        # x = x.reshape((-1, 1))
        if self.conditional_on[dim] is None:
            # the distribution is not conditional -> it is the marginal
            return self.distributions[dim].pdf(x)

        # the distribution is conditional
        # thus we integrate over the joint pdf to get the marginal

        # TODO check size of x

        n_dim = self.n_dim
        integral_order = list(range(n_dim))
        del integral_order[dim]  # we do not integrate over the dim'th variable
        integral_order = integral_order[::-1]  # we integrate over last dimensions first

        # scipy.integrate.nquad expects one argument per dimension
        # thus we have to wrap the (joint) pdf
        def get_integral_func():
            arg_order = integral_order + [dim]

            def integral_func(*args):
                assert len(args) == n_dim
                # sort arguments as expected by pdf (the models order)
                # arguments = list(args)[:-1]
                # arguments.append(args[-1][0])
                x = np.array(args)[np.argsort(arg_order)].reshape((1, n_dim))
                return self.pdf(x)

            return integral_func

        # TODO make limits a property of the distributions?
        # "for var in integral_order append limits"
        # but for now we simplify that all vars have the same limits
        limit = (0, np.inf)
        limits = [limit] * (n_dim - 1)

        f = np.empty_like(x)
        integral_func = get_integral_func()
        for i, x_i in enumerate(x):
            result, _ = integrate.nquad(integral_func, ranges=limits, args=[x_i])
            f[i] = result
        return f

    def marginal_cdf(self, x, dim):

        """
        Marginal cumulative distribution function.
                
        Parameters
        ----------
        x : array_like
            Points at which the cdf is evaluated.
            Shape: 1-dimensional
        dim : int
            The dimension for which the marginal is calculated.
  
        """

        # x = x.reshape((-1, 1))
        if self.conditional_on[dim] is None:
            # the distribution is not conditional -> it is the marginal
            return self.distributions[dim].cdf(x)

        # the distribution is conditional
        # thus we integrate over the joint pdf to get the marginal pdf
        # and then integrate the marginal pdf to get the marginal cdf

        # TODO check size of x

        n_dim = self.n_dim
        integral_order = list(range(n_dim))
        del integral_order[dim]
        integral_order = integral_order[::-1]  # we integrate over last dimensions first
        integral_order = integral_order + [
            dim
        ]  # finally we integrate over the dim'th var

        # scipy.integrate.nquad expects one argument per dimension
        # thus we have to wrap the (joint) pdf
        def get_integral_func():
            arg_order = integral_order

            def integral_func(*args):
                assert len(args) == n_dim
                # sort arguments as expected by pdf (the models order)
                # arguments = list(args)[:-1]
                # arguments.append(args[-1][0])
                x = np.array(args)[np.argsort(arg_order)].reshape((1, n_dim))
                return self.pdf(x)

            return integral_func

        # TODO make limits (or lower limit) a property of the distributions?
        limit = (0, np.inf)
        limits = [limit] * (n_dim - 1)

        F = np.empty_like(x)
        integral_func = get_integral_func()
        for i, x_i in enumerate(x):
            result, _ = integrate.nquad(integral_func, ranges=limits + [(0, x_i)])
            F[i] = result
        return F

    def marginal_icdf(self, p, dim, precision_factor=1):

        """
        Marginal inverse cumulative distribution function.
        
        Estimates the marginal icdf by drawing a Monte-Carlo sample.
                        
        Parameters
        ----------
        p : array_like
            Probabilities for which the icdf is evaluated.
            Shape: 1-dimensional
        dim : int
            The dimension for which the marginal is calculated.
        precision_factor : float
            Precision factor that determines the size of the sample to draw. 
            A sample is drawn of which on average precision_factor * 100 
            realizations exceed the quantile. Minimum sample size is 100000.
            Defaults to 1.0
   
        """

        p = np.array(p)

        if self.conditional_on[dim] is None:
            # the distribution is not conditional -> it is the marginal
            return self.distributions[dim].icdf(p)

        p_min = np.min(p)
        p_max = np.max(p)
        nr_exceeding_points = 100 * precision_factor
        p_small = np.min([p_min, 1 - p_max])
        n = int((1 / p_small) * nr_exceeding_points)
        n = max([n, 100000])
        sample = self.draw_sample(n)
        x = np.quantile(sample[:, dim], p)
        return x

    def draw_sample(self, n):
        """
        Draw a random sample of size n.
        
        Parameters
        ----------
        n : int
            Sample size.
       
        """

        samples = np.zeros((n, self.n_dim))
        for i in range(self.n_dim):
            cond_idx = self.conditional_on[i]
            dist = self.distributions[i]
            if cond_idx is None:
                samples[:, i] = dist.draw_sample(n)
            else:
                conditioning_values = samples[:, cond_idx]
                samples[:, i] = dist.draw_sample(1, conditioning_values)

        return samples
