'''Loss functions for neural network models.
'''

import theano
import theano.tensor as TT

from . import util


def build(name, **kwargs):
    '''Construct an activation function by name.

    Parameters
    ----------
    name : str or :class:`Loss`
        The name of the type of loss function to build.
    kwargs : dict
        Additional named arguments to pass to the loss constructor.

    Returns
    -------
    loss : :class:`Loss`
        A neural network loss function instance.
    '''
    return Loss.build(name, **kwargs)


class Loss(util.Registrar(str('Base'), (), {})):
    '''A loss function for a neural network model.'''

    F_CONTAINERS = (TT.scalar, TT.vector, TT.matrix, TT.tensor3, TT.tensor4)
    I_CONTAINERS = (TT.iscalar, TT.ivector, TT.imatrix, TT.itensor3, TT.itensor4)

    def __init__(self, in_dim, out_dim=None, weighted=False):
        self.input = Loss.F_CONTAINERS[in_dim]()
        self.variables = [self.input]
        self.target = None
        if out_dim:
            self.target = Loss.F_CONTAINERS[out_dim]()
            self.variables.append(self.target)
        self.weight = None
        if weighted:
            self.weight = Loss.F_CONTAINERS[out_dim or in_dim]()
            self.variables.append(self.weight)

    def diff(self, output):
        '''Compute the symbolic output difference from our target.
        '''
        return output - (self.input if self.target is None else self.target)

    def __call__(self, output):
        '''Construct the computation graph for this loss function.
        '''
        raise NotImplementedError


class MeanSquaredError(Loss):
    '''Mean-squared-error (MSE) loss function.

    .. math::
       \begin{eqnarray*}
       \mathcal{L}(x, t) &=& \frac{1}{d} \|x - t\|_2^2 \\
                         &=& \frac{1}{d} \sum_{i=1}^d (x_i - t_i)^2
       \end{eqnarray*}
    '''

    __extra_registration_keys__ = ['MSE']

    def __call__(self, output):
        err = self.diff(output)
        if self.weight is not None:
            return (self.weight * err * err).sum() / self.weight.sum()
        return (err * err).mean()


class MeanAbsoluteError(Loss):
    '''Mean-absolute-error (MAE) loss function.

    .. math::
       \begin{eqnarray*}
       \mathcal{L}(x, t) &=& \frac{1}{d} \|x - t\|_1 \\
                         &=& \frac{1}{d} \sum_{i=1}^d |x_i - t_i|
       \end{eqnarray*}
    '''

    __extra_registration_keys__ = ['MAE']

    def __call__(self, output):
        err = self.diff(output)
        if self.weight is not None:
            return abs(self.weight * err).sum() / self.weight.sum()
        return abs(err).mean()


class Hinge(Loss):
    '''Hinge loss function.

    .. math::
       \mathcal{L}(x, t) = \begin{cases}
         x - t \mbox{ if } x > t \\ 0 \mbox{ otherwise} \end{cases}
    '''

    def __call__(self, output):
        err = TT.maximum(0, self.diff(output))
        if self.weight is not None:
            return (self.weight * err).sum() / self.weight.sum()
        return err.mean()


class CrossEntropy(Loss):
    '''Cross-entropy (XE) loss function.

    .. math::
       \mathcal{L}(x, t) = - \sum_{k=1}^K p(t=k) \log q(x=k)
    '''

    __extra_registration_keys__ = ['XE']

    def __init__(self, in_dim, out_dim, weighted=False):
        self.input = Loss.F_CONTAINERS[in_dim]()
        self.target = Loss.I_CONTAINERS[out_dim]()
        self.variables = [self.input, self.target]
        self.weight = None
        if weighted:
            self.weight = Loss.F_CONTAINERS[out_dim]()
            self.variables.append(self.weight)

    def __call__(self, output):
        k = output.shape[-1]
        n = TT.prod(output.shape)
        prob = output.reshape((-1, k))[
            TT.arange(n // k), self.target.reshape((-1, ))]
        nlp = -TT.log(TT.clip(prob, 1e-8, 1))
        if self.weight is not None:
            return (self.weight.reshape((-1, )) * nlp).sum() / self.weight.sum()
        return nlp.mean()

    def accuracy(self, output):
        '''Build a theano expression for computing the network accuracy.

        Parameters
        ----------
        outputs : dict mapping str to theano expression
            A dictionary of all outputs generated by the layers in this network.

        Returns
        -------
        acc : theano expression
            A theano expression representing the network accuracy.
        '''
        predict = TT.argmax(output, axis=-1)
        correct = TT.eq(predict, self.target)
        acc = correct.mean()
        if self.weight is not None:
            acc = (self.weight * correct).sum() / self.weight.sum()
        return acc
