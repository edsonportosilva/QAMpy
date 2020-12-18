# -*- coding: utf-8 -*-
#  This file is part of QAMpy.
#
#  QAMpy is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Foobar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with QAMpy.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2018 Jochen Schröder, Mikael Mazur
import numpy as np
from qampy import core
from qampy.core.impairments import rotate_field, add_awgn, add_modal_delay
import warnings

def apply_PMD(field, theta, t_dgd):
    """
    Apply PMD to a given input field

    Parameters
    ----------

    field : SignalObject
        input dual polarisation optical field (first axis is polarisation)

    theta : float
        angle of the principle axis to the observed axis

    t_dgd : float
        differential group delay between the polarisation axes

    Returns
    -------
    out  : SignalObject
       new dual polarisation field with PMD
    """
    return field.recreate_from_np_array(core.impairments.apply_PMD_to_field(field, theta, t_dgd, field.fs))

def apply_phase_noise(signal, df):
    """
    Add phase noise from local oscillators, based on a Wiener noise process.

    Parameters
    ----------

    signal  : array_like
        single polarisation signal

    df : float
        combined linewidth of local oscillators in the system

    Returns
    -------
    out : array_like
       output signal with phase noise

    """
    return core.impairments.apply_phase_noise(signal, df, signal.fs)

def change_snr(sig, snr):
    """
    Change the SNR of a signal assuming that the input signal is noiseless

    Parameters
    ----------
    sig : array_like
        the signal to change
    snr : float
        the desired signal to noise ratio in dB

    Returns
    -------
    sig : array_like
        output signal with given SNR
    """
    return core.impairments.change_snr(sig, snr, sig.fb, sig.fs)

def add_carrier_offset(sig, fo):
    """
    Add frequency offset to signal

    Parameters
    ----------
    sig : array_like
        signal input array
    df : float
        frequency offset

    Returns
    -------
    signal : array_like
        signal with added offset
    """
    return core.impairments.add_carrier_offset(sig, fo, sig.fs)

def add_dispersion(sig, D, L, wl0=1550e-9):
    """
    Add dispersion to a signal
    
    Parameters
    ----------
    sig : signal_object
        signal to operate on
    D : float
        Dispersion parameter in s/m/m
    L : float
        Length of the dispersion in m
    wl0 : float, optional
        Centre wavelength in m

    Returns
    -------
    sig_out : signal_object
        output signal with added dispersion
    """
    so = core.impairments.add_dispersion(sig, sig.fs, D, L, wl0=wl0)
    return sig.recreate_from_nparray(so)

def simulate_transmission(sig, snr=None, freq_off=None, lwdth=None, dgd=None, theta=np.pi/3.731, modal_delay=None, dispersion=None, roll_frame_sync=False):
    """
    Convenience function to simulate impairments on signal at once

    Parameters
    ----------
    sig : array_like
        input signal
    snr : flaat, optional
        desired signal-to-noise ratio of the signal. (default: None, don't change SNR)
    freq_off : float, optional
        apply a carrier offset to signal (default: None, don't apply offset)
    lwdth : float
        linewidth of the transmitter and LO lasers (default: None, infinite linewidth)
    dgd : float
        first-order PMD (differential group delay) (default: None, do not apply PMD)
    theta : float
        rotation angle to principle states of polarization
    modal_delay : array_like, optional
        add a delay given in N samples to the signal (default: None, do not add delay)
    dispersion: float, optional
        dispersion in s/m

    Returns
    -------
    signal : array_like
        signal with transmission impairments applied
    """
    if roll_frame_sync:
        if not (sig.nframes > 1):
            warnings.warn("Only single frame present, discontinuity introduced")
        sig = np.roll(sig,sig.pilots.shape[1],axis=-1)
    if lwdth is not None:
        sig = apply_phase_noise(sig, lwdth)
    if freq_off is not None:
        sig = add_carrier_offset(sig, freq_off)
    if snr is not None:
        sig = change_snr(sig, snr)
    if modal_delay is not None:
        sig = add_modal_delay(sig, modal_delay)
    if dispersion is not None:
        sig = add_dispersion(sig, D, 1)
    if dgd is not None:
        sig = apply_PMD(sig, theta, dgd)
    return sig

