"""This module contains a base class for bivariate copulas."""

import json
import warnings
from enum import Enum

import numpy as np
from scipy import stats

from copulas import NotFittedError, random_state
from copulas.bivariate.utils import split_matrix


class CopulaTypes(Enum):
    """Available copula families."""

    CLAYTON = 0
    FRANK = 1
    GUMBEL = 2
    INDEPENDENCE = 3


class Bivariate(object):
    """Base class for bivariate copulas.

    This class allows to instantiate all its subclasses and serves as a unique entry point for
    the bivariate copulas classes.

    >>> Bivariate(copula_type=CopulaTypes.FRANK).__class__
    copulas.bivariate.frank.Frank

    >>> Bivariate(copula_type='frank').__class__
    copulas.bivariate.frank.Frank


    Args:
        copula_type (Union[CopulaType, str]): Subtype of the copula.
        random_seed (Union[int, None]): Seed for the random generator.

    Attributes:
        copula_type(CopulaTypes): Family of the copula a subclass belongs to.
        _subclasses(list[type]): List of declared subclasses.
        theta_interval(list[float]): Interval of valid thetas for the given copula family.
        invalid_thetas(list[float]): Values that, even though they belong to
            :attr:`theta_interval`, shouldn't be considered valid.
        tau (float): Kendall's tau for the data given at :meth:`fit`.
        theta(float): Parameter for the copula.

    """

    copula_type = None
    _subclasses = []
    theta_interval = []
    invalid_thetas = []
    theta = None
    tau = None

    @classmethod
    def _get_subclasses(cls):
        """Find recursively subclasses for the current class object.

        Returns:
            list[Bivariate]: List of subclass objects.

        """
        subclasses = []
        for subclass in cls.__subclasses__():
            subclasses.append(subclass)
            subclasses.extend(subclass._get_subclasses())

        return subclasses

    @classmethod
    def subclasses(cls):
        """Return a list of subclasses for the current class object.

        Returns:
            list[Bivariate]: Subclasses for given class.

        """
        if not cls._subclasses:
            cls._subclasses = cls._get_subclasses()

        return cls._subclasses

    def __new__(cls, *args, **kwargs):
        """Create and return a new object.

        Returns:
            Bivariate: New object.
        """
        copula_type = kwargs.get('copula_type', None)
        if copula_type is None:
            return super(Bivariate, cls).__new__(cls)

        if not isinstance(copula_type, CopulaTypes):
            if (isinstance(copula_type, str) and copula_type.upper() in CopulaTypes.__members__):
                copula_type = CopulaTypes[copula_type.upper()]
            else:
                raise ValueError('Invalid copula type {}'.format(copula_type))

        for subclass in cls.subclasses():
            if subclass.copula_type is copula_type:
                return super(Bivariate, cls).__new__(subclass)

    def __init__(self, copula_type=None, random_seed=None):
        """Initialize Bivariate object.

        Args:
            copula_type (CopulaType or str): Subtype of the copula.
            random_seed (int or None): Seed for the random generator.
        """
        self.random_seed = random_seed

    def check_theta(self):
        """Validate the computed theta against the copula specification.

        This method is used to assert the computed theta is in the valid range for the copula.

        Raises:
            ValueError: If theta is not in :attr:`theta_interval` or is in :attr:`invalid_thetas`,

        """
        lower, upper = self.theta_interval
        if (not lower <= self.theta <= upper) or (self.theta in self.invalid_thetas):
            message = 'The computed theta value {} is out of limits for the given {} copula.'
            raise ValueError(message.format(self.theta, self.copula_type.name))

    def check_fit(self):
        """Assert that the model is fit and the computed `theta` is valid.

        Raises:
            NotFittedError: if the model is  not fitted.
            ValueError: if the computed theta is invalid.

        """
        if not self.theta:
            raise NotFittedError("This model is not fitted.")

        self.check_theta()

    def _compute_theta(self):
        """Compute theta, validate it and assign it to self."""
        self.theta = self.compute_theta()
        self.check_theta()

    def fit(self, X):
        """Fit a model to the data updating the parameters.

        Args:
            X(np.ndarray): Array of datapoints with shape (n,2).

        Return:
            None
        """
        U, V = split_matrix(X)
        self.tau = stats.kendalltau(U, V)[0]
        self._compute_theta()

    def to_dict(self):
        """Return a `dict` with the parameters to replicate this object.

        Returns:
            dict: Parameters of the copula.

        """
        return {
            'copula_type': self.copula_type.name,
            'theta': self.theta,
            'tau': self.tau
        }

    @classmethod
    def from_dict(cls, copula_dict):
        """Create a new instance from the given parameters.

        Args:
            copula_dict: `dict` with the parameters to replicate the copula.
              Like the output of `Bivariate.to_dict`

        Returns:
            Bivariate: Instance of the copula defined on the parameters.

        """
        instance = cls(copula_type=copula_dict['copula_type'])
        instance.theta = copula_dict['theta']
        instance.tau = copula_dict['tau']
        return instance

    def infer(self, X):
        """Take in subset of values and predicts the rest."""
        raise NotImplementedError

    def generator(self, t):
        r"""Compute the generator function for Archimedian copulas.

        The generator is a function :math:`\psi: [0,1]\times\Theta \rightarrow [0, \infty)`
        that given an Archimedian copula fulills:

        .. math:: C(u,v) = \psi^{-1}(\psi(u) + \psi(v))


        In a more generic way:

        .. math:: C(u_1, u_2, ..., u_n;\theta) = \psi^-1(\sum_0^n{\psi(u_i;\theta)}; \theta)

        """
        raise NotImplementedError

    def probability_density(self, X):
        r"""Compute probability density function for given copula family.

        The probability density(pdf) for a given copula is defined as:

        .. math:: c(U,V) = \frac{\partial^2 C(u,v)}{\partial v \partial u}

        Args:
            X(np.ndarray): Shape (n, 2).Datapoints to compute pdf.

        Returns:
            np.array: Probability density for the input values.

        """
        raise NotImplementedError

    def pdf(self, X):
        """Shortcut to :meth:`probability_density`."""
        return self.probability_density(X)

    def cumulative_distribution(self, X):
        """Compute the cumulative distribution function for the copula, :math:`C(u, v)`.

        Args:
            X(np.ndarray):

        Returns:
            numpy.array: cumulative probability

        """
        raise NotImplementedError

    def cdf(self, X):
        """Shortcut to :meth:`cumulative_distribution`."""
        return self.cumulative_distribution(X)

    def percent_point(self, y, V):
        """Compute the inverse of conditional cumulative density :math:`C(u|v)^{-1}`.

        Args:
            y(np.ndarray): value of :math:`C(u|v)`.
            V(np.ndarray): given value of V.

        Returns:
            np.ndarray: Percentiles for the given values.

        """
        raise NotImplementedError

    def ppf(self, y, V):
        """Shortcut to :meth:`percent_point`."""
        return self.percent_point(y, V)

    def partial_derivative(self, X, y=0):
        r"""Compute partial derivative of cumulative distribution.

        The partial derivative of the copula(CDF) is the value of the conditional probability.

         .. math:: F(v|u) = \frac{\partial C(u,v)}{\partial u}

        Args:
            X(np.ndarray)
            y(float)

        Returns:
            np.ndarray

        """
        raise NotImplementedError

    def partial_derivative_scalar(self, U, V, y=0):
        """Compute partial derivative :math:`C(u|v)` of cumulative density of single values."""
        self.check_fit()

        X = np.column_stack((U, V))
        return self.partial_derivative(X, y)

    @random_state
    def sample(self, n_samples):
        """Generate specified `n_samples` of new data from model.

        The sampled are generated using the inverse transform method `v~U[0,1],v~C^-1(u|v)`

        Args:
            n_samples (int): amount of samples to create.

        Returns:
            np.ndarray: Array of length `n_samples` with generated data from the model.

        """
        if self.tau > 1 or self.tau < -1:
            raise ValueError("The range for correlation measure is [-1,1].")

        v = np.random.uniform(0, 1, n_samples)
        c = np.random.uniform(0, 1, n_samples)

        u = self.percent_point(c, v)
        return np.column_stack((u, v))

    def compute_theta(self):
        """Compute theta parameter using Kendall's tau."""
        raise NotImplementedError

    @classmethod
    def select_copula(cls, X):
        r"""Select best copula function based on likelihood.

        Given out candidate copulas the procedure proposed for selecting the one
        that best fit to a dataset of pairs :math:`\{(u_j, v_j )\}, j=1,2,...n` , is as follows:

        1. Estimate the most likely parameter :math:`\theta` of each copula candidate for the given
           dataset.

        2. Construct :math:`R(z|\theta)`. Calculate the area under the tail for each of the copula
           candidates.

        3. Compare the areas: :math:`a_u` achieved using empirical copula against the ones
           achieved for the copula candidates. Score the outcome of the comparison from 3 (best)
           down to 1 (worst).

        4. Proceed as in steps 2- 3 with the lower tail and function :math:`L`.

        5. Finally the sum of empirical upper and lower tail functions is compared against
           :math:`R + L`. Scores of the three comparisons are summed and the candidate with the
           highest value is selected.

        Args:
            X(np.ndarray): Matrix of shape (n,2).

        Returns:
            copula: Best copula that fits for it.

        """
        from copulas.bivariate import select_copula  # noqa
        warnings.warn(
            '`Bivariate.select_copula` has been deprecated and will be removed in a later '
            'release. Please use `copulas.bivariate.select_copla` instead',
            DeprecationWarning
        )
        return select_copula(X)

    def save(self, filename):
        """Save the internal state of a copula in the specified filename.

        Args:
            filename(str): Path to save.

        Returns:
            None

        """
        content = self.to_dict()
        with open(filename, 'w') as f:
            json.dump(content, f)

    @classmethod
    def load(cls, copula_path):
        """Create a new instance from a file.

        Args:
            copula_path(str): Path to file with the serialized copula.

        Returns:
            Bivariate: Instance with the parameters stored in the file.

        """
        with open(copula_path) as f:
            copula_dict = json.load(f)

        return cls.from_dict(copula_dict)