# Authors : Alexandre Gramfort, gramfort@nmr.mgh.harvard.edu (2011)
#           Denis A. Engemann <d.engemann@fz-juelich.de>
# License : BSD 3-clause

import numpy as np

from ..parallel import parallel_func
from ..fiff.proj import make_projector_info
from ..fiff.pick import pick_types
from ..utils import logger, verbose


@verbose
def compute_raw_psd(raw, tmin=0, tmax=np.inf, picks=None,
                    fmin=0, fmax=np.inf, NFFT=2048, n_jobs=1,
                    plot=False, proj=False, verbose=None):
    """Compute power spectral density with multi-taper

    Parameters
    ----------
    raw : instance of Raw
        The raw data.
    picks : None or array of integers
        The selection of channels to include in the computation.
        If None, take all channels.
    fmin : float
        Min frequency of interest
    fmax : float
        Max frequency of interest
    NFFT : int
        The length of the tapers ie. the windows. The smaller
        it is the smoother are the PSDs.
    n_jobs : int
        Number of CPUs to use in the computation.
    plot : bool
        Plot each PSD estimates
    proj : bool
        Apply SSP projection vectors
    verbose : bool, str, int, or None
        If not None, override default verbose level (see mne.verbose).

    Returns
    -------
    psd : array of float
        The PSD for all channels
    freqs: array of float
        The frequencies
    """
    start, stop = raw.time_as_index([tmin, tmax])
    if picks is not None:
        data, times = raw[picks, start:(stop + 1)]
    else:
        data, times = raw[:, start:(stop + 1)]

    if proj:
        proj, _ = make_projector_info(raw.info)
        if picks is not None:
            data = np.dot(proj[picks][:, picks], data)
        else:
            data = np.dot(proj, data)

    NFFT = int(NFFT)
    Fs = raw.info['sfreq']

    logger.info("Effective window size : %0.3f (s)" % (NFFT / float(Fs)))

    import pylab as pl
    parallel, my_psd, n_jobs = parallel_func(pl.psd, n_jobs)
    fig = pl.figure()
    out = parallel(my_psd(d, Fs=Fs, NFFT=NFFT) for d in data)
    if not plot:
        pl.close(fig)
    freqs = out[0][1]
    psd = np.array(zip(*out)[0])

    mask = (freqs >= fmin) & (freqs <= fmax)
    freqs = freqs[mask]
    psd = psd[:, mask]

    return psd, freqs


def _compute_psd(data, fmin, fmax, Fs, n_fft, psd):
    """Compute the PSD"""
    out = [psd(d, Fs=Fs, NFFT=n_fft) for d in data]
    psd = np.array(zip(*out)[0])
    freqs = out[0][1]
    mask = (freqs >= fmin) & (freqs <= fmax)
    freqs = freqs[mask]
    return psd[:, mask], freqs


@verbose
def compute_epochs_psd(epochs, picks=None, fmin=0, fmax=np.inf, n_fft=256,
                       n_jobs=1, verbose=None):
    """Compute power spectral density with multi-taper

    Parameters
    ----------
    epochs : instance of Epochss
        The epochs.
    tmin : float
        Min time instant to consider
    tmax : float
        Max time instant to consider
    picks : None or array of integers
        The selection of channels to include in the computation.
        If None, take all channels.
    fmin : float
        Min frequency of interest
    fmax : float
        Max frequency of interest
    n_fft : int
        The length of the tapers ie. the windows. The smaller
        it is the smoother are the PSDs.
    n_jobs : int
        Number of CPUs to use in the computation.
    verbose : bool, str, int, or None
        If not None, override default verbose level (see mne.verbose).

    Returns
    -------
    psds : ndarray (n_epochs, n_channels, n_freqs)
        The power spectral densities.
    freqs : ndarray (n_freqs)
        The frequencies.
    """

    n_fft = int(n_fft)
    Fs = epochs.info['sfreq']
    if picks is None:
        picks = pick_types(epochs.info, meg=True, eeg=True, exclude='bads')

    logger.info("Effective window size : %0.3f (s)" % (n_fft / float(Fs)))
    psds = []
    import matplotlib.pyplot as plt
    parallel, my_psd, n_jobs = parallel_func(_compute_psd, n_jobs)
    fig = plt.figure()  # threading will induce errors otherwise
    out = parallel(my_psd(data[picks], fmin, fmax, Fs, n_fft, plt.psd)
                   for data in epochs)
    plt.close(fig)
    psds, freqs = zip(*out)

    return np.array(psds), freqs[0]
