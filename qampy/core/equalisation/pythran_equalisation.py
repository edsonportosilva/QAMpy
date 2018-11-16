import numpy as np

def adapt_step(mu, err_p, err):
    if err.real*err_p.real > 0 and err.imag*err_p.imag > 0:
        return mu
    else:
        return mu/(1+mu*(err.real*err.real + err.imag*err.imag))

def apply_filter(E, wx):
    pols = E.shape[0]
    Ntaps = wx.shape[1]
    Xest = 0+0j
    for k in range(pols):
        for i in range(Ntaps):
            Xest += E[k, i]*np.conj(wx[k,i])
    return Xest

def apply_filter2(E, wx):
    return np.sum(E*np.conj(wx))

#pythran export train_eq(complex128[][], int, int, float64,
        # complex128[][], complex128(complex128, (complex128, complex128[])),
        # (complex128, complex128[]), bool)
def train_eq(E, TrSyms, os, mu, wx, errfct,  errfctprs, adaptive):
    Ntaps = wx.shape[1]
    pols = wx.shape[0]
    err = np.zeros(TrSyms, dtype=E.dtype)
    for i in range(TrSyms):
        X = E[:, i * os:i * os + Ntaps]
        Xest = np.sum(np.conj(wx) * X)
        Xest = apply_filter(X,  wx)
        err[i] = errfct(Xest, errfctprs)
        wx += mu * np.conj(err[i]) * X
        if adaptive and i > 0:
            mu = adapt_step(mu, err[i], err[i-1])
    return err, wx, mu


#pythran export capsule cma_error(complex128, (complex128, complex128[]))
def cma_error(Xest, prs):
    return (prs[0].real - abs(Xest)**2)*Xest

#pythran export capsule mcma_error(complex64, (complex128, complex128[]))
def mcma_error(Xest, prs):
    #return (prs[0].real - Xest.real**2)*Xest.real + (prs[0].imag - Xest.imag**2)*Xest.imag*1.j
    return prs[0].real*Xest.real - Xest.real**3 + 1j*(prs[0].imag*Xest.imag - Xest.imag**3)


#pythran export capsule sbd_error(complex128, (complex128, complex128[]))
def sbd_error(Xest, prs):
    R = prs[1][np.argmin(np.abs(Xest-prs[1]))]
    return (R.real - Xest.real)*abs(R.real) + (R.imag - Xest.imag)*1.j*abs(R.imag)
