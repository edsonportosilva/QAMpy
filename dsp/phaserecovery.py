#vim:fileencoding=utf-8
from __future__ import division, print_function
import arrayfire as af
import numpy as np
from .segmentaxis import segment_axis
from .theory import calculate_MQAM_symbols
from .signal_quality import calS0
from .dsp_cython import gen_unwrap

SYMBOLS_16QAM = calculate_MQAM_symbols(16)
NMAX = 4*1024**3

def viterbiviterbi_gen(N, E, M):
    """
    Viterbi-Viterbi blind phase recovery for an M-PSK signal

    Parameters
    ----------
    N : int
        number of samples to average over
    E : array_like
        the electric field of the signal
    M : int
        order of the M-PSK

    Returns
    -------
    Eout : array_like
        Field with compensated phases
    """
    E = E.flatten()
    L = len(E)
    phi = np.angle(E)
    E_raised = np.exp(1.j * phi)**M
    sa = segment_axis(E_raised, N, N - 1)
    phase_est = np.sum(sa, axis=1)
    phase_est = np.unwrap(np.angle(phase_est))
    if N % 2:
        E = E[(N - 1) / 2:L - (N - 1) / 2]
    else:
        E = E[N / 2 - 1:L - (N / 2)]
    #if M == 4: # QPSK needs pi/4 shift
    # need a shift by pi/M for constellation points to not be on the axis
    phase_est = phase_est - np.pi
    return E * np.exp(-1.j * phase_est / M)

def blindphasesearch_py(E, Mtestangles, symbols, N):
    angles = np.linspace(-np.pi/4, np.pi/4, Mtestangles, endpoint=False)
    EE = E[:,np.newaxis]*np.exp(1.j*angles)
    idx = np.zeros(len(E)-2*N, dtype=np.int)
    dist = (abs(EE[:2*N, :, np.newaxis]-symbols)**2).min(axis=2)
    idx[0] = dist.sum(axis=0).argmin(axis=0)
    for i in range(1,len(idx)):
        tmp = (abs(EE[N+i,:,np.newaxis]-symbols)**2).min(axis=1).reshape(1,Mtestangles)
        dist = np.concatenate([dist[1:], tmp])#(abs(EE[N+i,:,np.newaxis]-symbols)**2).min(axis=1)])
        idx[i] = dist.sum(axis=0).argmin(axis=0)
    ph = np.unwrap(angles[idx]*4)/4
    En = E[N:-N]*np.exp(1.j*ph)
    return En, ph

def afmavg(X, N, axis=0):
    cs = af.accum(X, dim=axis)
    return cs[N:] - cs[:-N]

def blindphasesearch_af(E, Mtestangles, symbols, N, precision=16):
    global NMAX
    if precision == 16:
        prec_dtype = np.complex128
    elif precision == 8:
        prec_dtype = np.complex64
    else:
        raise ValueError("Precision has to be either 16 for double complex or 8 for single complex")
    Nmax = NMAX//Mtestangles//symbols.shape[0]//16
    L = E.shape[0]
    #angles = np.linspace(-np.pi/4, np.pi/4, Mtestangles, endpoint=False)
    angles = np.arange(Mtestangles)*np.pi/2/Mtestangles
    EE = E[:,np.newaxis]*np.exp(1.j*angles)
    syms  = af.np_to_af_array(symbols.astype(prec_dtype).reshape(1,1,-1))
    if L <= Nmax+N:
        Eaf = af.np_to_af_array(EE.astype(prec_dtype))
        tmp = af.min(af.abs(af.broadcast(lambda x,y: x-y, Eaf[0:L,:], syms))**2, dim=2)
        cs = afmavg(tmp, 2*N, axis=0)
        val, idx = af.imin(cs, dim=1)
        idxnd = np.array(idx)
        #return E[N:-N]*np.exp(1.j*angles[np.array(idx)])
    else:
        K = L//Nmax
        R = L%Nmax
        if R < N:
            R = R+Nmax
            K -= 1
        Eaf = af.np_to_af_array(EE[0:Nmax+N].astype(np.complex128))
        idxnd = np.zeros(L-2*N, dtype=np.int32)
        tmp = af.min(af.abs(af.broadcast(lambda x,y: x-y, Eaf, syms))**2, dim=2)
        cs = afmavg(tmp, 2*N, axis=0)
        val, idx = af.imin(cs, dim=1)
        idxnd[0:Nmax-N] = np.array(idx)
        for i in range(1,K):
            Eaf = af.np_to_af_array(EE[i*Nmax-N:(i+1)*Nmax+N].astype(np.complex128))
            tmp = af.min(af.abs(af.broadcast(lambda x,y: x-y, Eaf, syms))**2, dim=2)
            cs = afmavg(tmp, 2*N, axis=0)
            val, idx = af.imin(cs, dim=1)
            idxnd[i*Nmax-N:(i+1)*Nmax-N] = np.array(idx)
        Eaf = af.np_to_af_array(EE[K*Nmax-N:K*Nmax+R].astype(np.complex128))
        tmp = af.min(af.abs(af.broadcast(lambda x,y: x-y, Eaf, syms))**2, dim=2)
        cs = afmavg(tmp, 2*N, axis=0)
        val, idx = af.imin(cs, dim=1)
        idxnd[K*Nmax-N:] = np.array(idx)
    angles_adj = np.unwrap(angles[idxnd]*4, discont=np.pi*6/4)/4
    #angles_adj = gen_unwrap(angles[idxnd], np.pi/16 , np.pi/2)
    #T = np.pi/2 * 3/4
    #angles_adj = T*np.unwrap(angles[idxnd]*2*np.pi/T)/(2*np.pi)
    En = E[N:-N]*np.exp(1.j*angles_adj)
    return En, angles_adj, angles[idxnd]


def viterbiviterbi_qpsk(N, E):
    """
    Viterbi-Viterbi blind phase recovery for QPSK signal

    Parameters
    ----------
    N : int
        number of samples to average over
    E : array_like
        the electric field of the signal

    Returns
    -------
    Eout : array_like
        Field with compensated phases
    """
    return viterbiviterbi_gen(N, E, 4)


def viterbiviterbi_bpsk(N, E):
    """
    Viterbi-Viterbi for BPSK signal

    Parameters
    ----------
    N : int
        number of samples to average over
    E : array_like
        the electric field of the signal

    Returns
    -------
    Eout : array_like
        Field with compensated phases
    """
    return viterbiviterbi_gen(N, E, 2)


def __findmax_16QAM(rk, ci, vk):
    mkk = np.real(rk * np.conj(ci) * np.conj(vk) - abs(ci)**2 / 2)
    pk = np.argmax(mkk)
    return ci[pk]


def ML_phase_16QAM(X, Y, pix, piy, cfactor):
    """
    Maximum-likelihood phase recovery for 16-QAM signal
    using pilots for starting the estimator on a dual-pol 16 QAM signal.

    Parameters
    ----------
    X : array_like
        X polarisation of the input signal field
    Y : array_like
        Y polarisation of the input signal field
    pix : array_like
        Known pilot data (X polarisation)
    piy : array_like
        Known pilot data (Y polarisation)

    Returns
    -------
    RecoveredX : array_like
        Phase recovered signal field (X polarisation)
    RecoveredY : array_like
        Phase recovered signal field (Y polarisation)
    """
    N = len(X)
    cfactor = len(pix)
    pilotX = np.zeros(N, dtype=np.complex)
    pilotY = np.zeros(N, dtype=np.complex)
    pilotX[:cfactor] = pix
    pilotY[:cfactor] = piy
    pcoeX = np.zeros(N, dtype=np.complex)
    pcoeY = np.zeros(N, dtype=np.complex)
    pcoeX[:cfactor] = np.angle(np.conj(pilotX[:cfactor]) * X[:cfactor])
    pcoeY[:cfactor] = np.angle(np.conj(pilotY[:cfactor]) * Y[:cfactor])
    for k in range(cfactor, N):
        pcoeX[k] = np.angle(
            np.sum(np.conj(pilotX[k - cfactor:k]) * X[k - cfactor:k]))
        pcoeY[k] = np.angle(
            np.sum(np.conj(pilotY[k - cfactor:k]) * Y[k - cfactor:k]))
        pilotX[k] = __findmax_16QAM(X[k], SYMBOLS_16QAM,\
                    np.sum(np.conj(pilotX[k-cfactor:k])*X[k-cfactor:k])/\
                    np.sum(np.abs(pilotX[k-cfactor:k])**2))
        pilotY[k] = __findmax_16QAM(Y[k], SYMBOLS_16QAM,
                    np.sum(np.conj(pilotY[k-cfactor:k])*Y[k-cfactor:k])/\
                    np.sum(np.abs(pilotY[k-cfactor:k])**2))
    return X * np.exp(-1.j * pcoeX), Y * np.exp(-1.j * pcoeY)


def partition_16QAM(E):
    r"""Partition a 16-QAM signal into the inner and outer circles.

    Separates a 16-QAM signal into the inner and outer rings, which have
    different phase orientations. Detailed in _[1].

    Parameters
    ----------
        E : array_like
            electric field of the signal

    Returns
    -------
        class1_mask : array_like
            A mask designating the class 1 symbols which are the smallest and
            largest rings.
        class2_mask : array_like
            A mask designating the class 2 symbols which lie on the middle ring

    References
    ----------
    .. [1] R. Muller and D. D. A. Mello, “Phase-offset estimation for
       joint-polarization phase-recovery in DP-16-QAM systems,” Photonics
       Technol. Lett. …, vol. 22, no. 20, pp. 1515–1517, 2010.
    """

    S0 = calS0(E, 1.32)
    inner = (np.sqrt(S0 / 5) + np.sqrt(S0)) / 2.
    outer = (np.sqrt(9 * S0 / 5) + np.sqrt(S0)) / 2.
    Ea = abs(E)
    class1_mask = (Ea < inner) | (Ea > outer)
    class2_mask = ~class1_mask
    return class1_mask, class2_mask


def ff_Phase_recovery_16QAM(E, Nangles, Nsymbols):
    phi = np.linspace(0, np.pi, Nangles)
    N = len(E)
    d = (abs(E[:, np.newaxis, np.newaxis] * np.exp(1.j * phi)[:, np.newaxis] -
             SYMBOLS_16QAM)**2).min(axis=2)
    phinew = np.zeros(N - Nsymbols, dtype=np.float)
    for k in range(Nsymbols, N - Nsymbols):
        phinew[k] = phi[np.sum(d[k - Nsymbols:k + Nsymbols], axis=0).argmin()]
    return E[Nsymbols:] * np.exp(1.j * phinew)


def QPSK_partition_phase_16QAM(Nblock, E):
    r"""16-QAM blind phase recovery using QPSK partitioning.

    A blind phase estimator for 16-QAM signals based on partitioning the signal
    into 3 rings, which are then phase estimated using traditional V-V phase
    estimation after Fatadin et al _[1].

    Parameters
    ----------
        Nblock : int
            number of samples in an averaging block
        E : array_like
            electric field of the signal

    Returns
    -------
        E_rec : array_like
            electric field of the signal with recovered phase.

    References
    ----------
    .. [1] I. Fatadin, D. Ives, and S. Savory, “Laser linewidth tolerance
       for 16-QAM coherent optical systems using QPSK partitioning,”
       Photonics Technol. Lett. IEEE, vol. 22, no. 9, pp. 631–633, May 2010.

    """
    dphi = np.pi / 4 + np.arctan(1 / 3)
    L = len(E)
    # partition QPSK signal into qpsk constellation and non-qpsk const
    c1_m, c2_m = partition_16QAM(E)
    Sx = np.zeros(len(E), dtype=np.complex128)
    Sx[c2_m] = (E[c2_m] * np.exp(1.j * dphi))**4
    So = np.zeros(len(E), dtype=np.complex128)
    So[c2_m] = (E[c2_m] * np.exp(1.j * -dphi))**4
    S1 = np.zeros(len(E), dtype=np.complex128)
    S1[c1_m] = (E[c1_m])**4
    E_n = np.zeros(len(E), dtype=np.complex128)
    phi_est = np.zeros(len(E), dtype=np.float64)
    for i in range(0, L, Nblock):
        S1_sum = np.sum(S1[i:i + Nblock])
        Sx_tmp = np.min(
            [S1_sum - Sx[i:i + Nblock], S1_sum - So[i:i + Nblock]],
            axis=0)[c2_m[i:i + Nblock]]
        phi_est[i:i + Nblock] = np.angle(S1_sum + Sx_tmp.sum())
    phi_est = np.unwrap(phi_est) / 4 - np.pi / 4
    return (E * np.exp(-1.j * phi_est))[:(L // Nblock) * Nblock]
