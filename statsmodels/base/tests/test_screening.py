# -*- coding: utf-8 -*-
"""
Created on Wed May 23 12:53:27 2018

Author: Josef Perktold

"""


import numpy as np
from numpy.testing import assert_allclose, assert_equal
import pandas as pd

from statsmodels.discrete.discrete_model import Poisson
from statsmodels.base._penalized import PenalizedMixin
from statsmodels.base._screening import VariableScreening


class PoissonPenalized(PenalizedMixin, Poisson):
    pass


def test_poisson_screening():
    # this is mostly a dump of my development notebook
    # number of exog candidates is reduced to 500 to reduce time
    np.random.seed(987865)

    nobs, k_vars = 100, 500
    k_nonzero = 5
    x = (np.random.rand(nobs, k_vars) + 1.* (np.random.rand(nobs, 1)-0.5)) * 2 - 1
    x *= 1.2

    x = (x - x.mean(0)) / x.std(0)
    x[:, 0] = 1
    beta = np.zeros(k_vars)
    idx_non_zero_true = [0, 100, 300, 400, 411]
    beta[idx_non_zero_true] = 1. / np.arange(1, k_nonzero + 1)
    beta = np.sqrt(beta)  # make small coefficients larger
    linpred = x.dot(beta)
    mu = np.exp(linpred)
    y = np.random.poisson(mu)

    xnames_true = ['var%4d' % ii for ii in idx_non_zero_true]
    xnames_true[0] = 'const'
    parameters = pd.DataFrame(beta[idx_non_zero_true], index=xnames_true, columns=['true'])

    xframe_true = pd.DataFrame(x[:, idx_non_zero_true], columns=xnames_true)
    res_oracle = Poisson(y, xframe_true).fit()
    parameters['oracle'] = res_oracle.params

    mod_initial = PoissonPenalized(y, np.ones(nobs), pen_weight=nobs * 5)
    base_class = Poisson

    screener = VariableScreening(mod_initial, base_class)
    exog_candidates = x[:, 1:]
    res_screen = screener.screen_exog(exog_candidates, maxiter=10)

    res_screen.idx_nonzero

    res_screen.results_final


    xnames = ['var%4d' % ii for ii in res_screen.idx_nonzero]
    xnames[0] = 'const'

    # smoke test
    res_screen.results_final.summary(xname=xnames)
    res_screen.results_pen.summary()
    assert_equal(res_screen.results_final.mle_retvals['converged'], True)

    ps = pd.Series(res_screen.results_final.params, index=xnames, name='final')
    parameters = parameters.join(ps, how='outer')

    assert_allclose(parameters['oracle'], parameters['final'], atol=5e-6)

def test_screen_iterated():
    np.random.seed(987865)

    nobs, k_nonzero = 100, 5

    x = (np.random.rand(nobs, k_nonzero - 1) +
         1.* (np.random.rand(nobs, 1) - 0.5)) * 2 - 1
    x *= 1.2
    x = (x - x.mean(0)) / x.std(0)
    x = np.column_stack((np.ones(nobs), x))

    beta = 1. / np.arange(1, k_nonzero + 1)
    beta = np.sqrt(beta)  # make small coefficients larger
    linpred = x.dot(beta)
    mu = np.exp(linpred)
    y = np.random.poisson(mu)

    common = x[:, 1:].sum(1)[:, None]

    x_nonzero = x

    def exog_iterator():
        k_vars = 100

        n_batches = 6
        for i in range(n_batches):
            x = (0.05 * common + np.random.rand(nobs, k_vars) +
                 1.* (np.random.rand(nobs, 1) - 0.5)) * 2 - 1
            x *= 1.2
            if i < k_nonzero - 1:
                # hide a nonezero
                x[:, 10] = x_nonzero[:, i + 1]
            x = (x - x.mean(0)) / x.std(0)
            yield x

    mod_initial = PoissonPenalized(y, np.ones(nobs), pen_weight=nobs * 500)
    base_class = Poisson
    screener = VariableScreening(mod_initial, base_class)
    screener.k_max_add = 30

    final = screener.screen_exog_iterator(exog_iterator())
    names = ['var0_10', 'var1_10', 'var2_10', 'var3_10']
    assert_equal(final.exog_final_names, names)
    idx_full = np.array([[ 0, 10],
                         [ 1, 10],
                         [ 2, 10],
                         [ 3, 10]], dtype=np.int64)
    assert_equal(final.idx_nonzero_batches, idx_full)
