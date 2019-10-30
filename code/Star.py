# @auto-fold regex /^\s*if/ /^\s*else/ /^\s*elif/ /^\s*def/
"""Star.py contains the Star class which contains the data regarding a star."""

import pickle
from contextlib import closing

import astropy.units as u
import scipy as sp
from astropy.coordinates import SkyCoord
from dustmaps.sfd import SFDQuery
from scipy.interpolate import RegularGridInterpolator

from Librarian import Librarian
from phot_utils import *


class Star:
    """Object that holds stellar magnitudes and other relevant information.

    Parameters
    ----------
    starname : str
        The name of the object. If ra and dec aren't provided nor is a
        list of magnitudes with associated uncertainties prvided, the search
        for stellar magnitudes will be done using the object's name instead.

    ra : float
        RA coordinate of the object in degrees.

    dec : float
        DEC coordinate of the object in degrees.

    get_plx : bool, optional
        Set to True in order to query Gaia DR2 for the stellar parallax.

    plx : float, optional
        The parallax of the star in case no internet connection is available
        or if no parallax can be found on Gaia DR2.

    plx_e : float, optional
        The error on the parallax.

    get_rad : bool, optional
        Set to True in order to query Gaia DR2 for the stellar radius, if
        available.

    rad : float, optional
        The radius of the star in case no internet connection is available
        or if no radius can be found on Gaia DR2.

    rad_e : float, optional
        The error on the stellar radius.

    get_temp : bool, optional
        Set to True in order to query Gaia DR2 for the effective temperature,
        if available.

    temp : float, optional
        The effective temperature of the star in case no internet connection
        is available or if no effective temperature can be found on Gaia DR2.

    temp_e : float, optional
        The error on the effective temperature.

    get_lum : bool, optional
        Set to True in order to query Gaia DR2 for the stellar luminosity,
        if available.

    lum : float, optional
        The stellar luminosity in case no internet connection
        is available or if no luminosity can be found on Gaia DR2.

    lum_e : float, optional
        The error on the stellar luminosity.

    mag_dict : dictionary, optional
        A dictionary with the filter names as keys (names must correspond to
        those in the filter_names attribute) and with a tuple containing the
        magnitude and error for that filter as the value. Provide in case no
        internet connection is available.

    coordinate_search : bool
        If True uses coordinates to search for the object in the catalogs.
        Else it uses the object's name.

    verbose : bool, optional
        Set to False to supress printed outputs.

    Attributes
    ----------
    catalogs : dict
        A dictionary with the Vizier catalogs of different surveys
        used to retrieve stellar magnitudes.

    full_grid : ndarray
        The full grid of fluxes.

    teff : ndarray
        The effective temperature axis of the flux grid.

    logg : ndarray
        The gravity axis of the flux grid

    z : ndarray, float
        If fixed_z is False, then z is the metallicity axis of the flux grid.
        Otherwise z has the same value as fixed_z

    starname : str
        The name of the object.

    ra : float
        RA coordinate of the object.

    dec : float
        DEC coordinate of the object.

    filters : ndarray
        An array containing the filters or bands for which there is
        archival photometry

    magnitudes : ndarray
        An array containing the archival magnitudes for the object.

    errors : ndarray
        An array containing the uncertainties in the magnitudes.

    wave : ndarray
        An array containing the wavelengths associated to the different
        filters retrieved.

    flux : ndarray
        An array containing the fluxes of the different retrieved magnitudes.

    grid : ndarray
        An array containing a grid with teff, logg and z if it's not fixed
        to be used for interpolation later.

    """

    # pyphot filter names: currently unused are U R I PS1_w

    filter_names = sp.array([
        '2MASS_H', '2MASS_J', '2MASS_Ks',
        'GROUND_JOHNSON_U', 'GROUND_JOHNSON_V', 'GROUND_JOHNSON_B',
        'GaiaDR2v2_G', 'GaiaDR2v2_RP', 'GaiaDR2v2_BP',
        'PS1_g', 'PS1_i', 'PS1_r', 'PS1_w', 'PS1_y',  'PS1_z',
        'SDSS_g', 'SDSS_i', 'SDSS_r', 'SDSS_u', 'SDSS_z',
        'WISE_RSR_W1', 'WISE_RSR_W2',
        'GALEX_FUV', 'GALEX_NUV'
    ])

    def __init__(self, starname, ra, dec,
                 get_plx=True, plx=None, plx_e=None,
                 get_rad=True, rad=None, rad_e=None,
                 get_temp=True, temp=None, temp_e=None,
                 get_lum=True, lum=None, lum_e=None,
                 mag_dict=None, coordinate_search=True, verbose=True):
        """See class docstring."""
        # MISC
        self.verbose = verbose
        if verbose:
            if plx is not None:
                print('Parallax input detected.', end=' ')
                print('Overriding coordinate search.')
            if rad is not None:
                print('Radius input detected.', end=' ')
                print('Overriding coordinate search.')
            if temp is not None:
                print('Temperature input detected.', end=' ')
                print('Overriding coordinate search.')
            if lum is not None:
                print('Luminosity input detected.', end=' ')
                print('Overriding coordinate search.')
            if mag_dict is not None:
                print('Input magnitudes detected.', end=' ')
                print('Overriding coordinate search.')

        self.get_rad = get_rad if rad is None else False
        self.get_plx = get_plx if plx is None else False
        self.get_temp = get_temp if temp is None else False
        self.get_lum = get_lum if lum is None else False
        self.get_mags = True if mag_dict is None else False

        # Star stuff
        self.starname = starname
        self.ra_dec_to_deg(ra, dec)

        # Lookup archival magnitudes, radius, temperature, luminosity
        # and parallax
        lookup = self.get_rad + self.get_temp + self.get_plx + self.get_mags
        if lookup:
            lib = Librarian(starname, self.ra, self.dec,
                            self.get_plx, self.get_rad,
                            self.get_temp, self.get_lum,
                            verbose)
            if self.get_plx:
                self.plx = lib.plx
                self.plx_e = lib.plx_e
            if self.get_rad:
                self.rad = lib.rad
                self.rad_e = lib.rad_e
            if self.get_temp:
                self.temp = lib.temp
                self.temp_e = lib.temp_e
            if self.get_lum:
                self.lum = lib.lum
                self.lum_e = lib.lum_e
            if self.get_mags:
                lib.get_magnitudes(coordinate_search)
                self.used_filters = lib.used_filters
                self.mags = lib.mags
                self.mag_errs = lib.mag_errs
        if not self.get_mags:
            filters = []
            self.used_filters = sp.zeros(self.filter_names.shape[0])
            self.mags = sp.zeros(self.filter_names.shape[0])
            self.mag_errs = sp.zeros(self.filter_names.shape[0])
            for k in mag_dict.keys():
                filt_idx = sp.where(k == self.filter_names)[0]
                self.used_filters[filt_idx] = 1
                self.mags[filt_idx] = mag_dict[k][0]
                self.mag_errs[filt_idx] = mag_dict[k][1]

                filters.append(k)
        self.filter_mask = sp.where(self.used_filters == 1)[0]

        # Get max Av
        sfd = SFDQuery()
        coords = SkyCoord(self.ra, self.dec, unit=(u.deg, u.deg), frame='icrs')
        ebv = sfd(coords)
        self.Av = ebv * self.mags[4]
        # Get the wavelength and fluxes of the retrieved magnitudes.
        wave, flux, flux_er, bandpass = extract_info(
            self.mags[self.filter_mask], self.mag_errs[self.filter_mask],
            self.filter_names[self.filter_mask])

        self.wave = sp.zeros(self.filter_names.shape[0])
        self.flux = sp.zeros(self.filter_names.shape[0])
        self.flux_er = sp.zeros(self.filter_names.shape[0])
        self.bandpass = sp.zeros((self.filter_names.shape[0], 2))

        for k in wave.keys():
            filt_idx = sp.where(k == self.filter_names)[0]
            self.wave[filt_idx] = wave[k]
            self.flux[filt_idx] = flux[k]
            self.flux_er[filt_idx] = flux_er[k]
            self.bandpass[filt_idx] = bandpass[k]

        self.calculate_distance()

    def ra_dec_to_deg(self, ra, dec):
        """Transform ra, dec from selected uniot to degrees."""
        if type(ra) == float and type(dec) == float:
            self.ra = ra
            self.dec = dec
            return
        c = SkyCoord(ra, dec, frame='icrs')

        self.ra = c.ra.deg
        self.dec = c.dec.deg
        pass

    def load_grid(self, model):
        """Load the model grid for interpolation."""
        # Grid stuff
        # self.full_grid = sp.loadtxt('../Datafiles/model_grid_fix.dat')
        if model.lower() == 'phoenix':
            gridname = 'model_grid_Phoenixv2.dat'
        if model.lower() == 'btsettl':
            gridname = 'model_grid_BT_Settl.dat'
        if model.lower() == 'ck04':
            gridname = 'model_grid_CK04.dat'
        self.full_grid = sp.loadtxt(gridname)
        self.teff = self.full_grid[:, 0]
        self.logg = self.full_grid[:, 1]
        self.z = self.full_grid[:, 2]
        if self.verbose:
            print('Grid ' + model + ' loaded.')

    def interpolate(self, out_name):
        """Create interpolation grids for later evaluation."""
        if self.verbose:
            print('Interpolating grids for filters:')
        interpolators = sp.zeros(self.filter_names.shape[0], dtype=object)
        ut = sp.unique(self.full_grid[:, 0])
        ug = sp.unique(self.full_grid[:, 1])
        uz = sp.unique(self.full_grid[:, 2])
        for ii, f in enumerate(self.filter_names):
            cube = sp.zeros((ut.shape[0], ug.shape[0], uz.shape[0]))
            if self.verbose:
                print(f)
            for i, t in enumerate(ut):
                t_idx = self.full_grid[:, 0] == t
                for j, g in enumerate(ug):
                    g_idx = self.full_grid[:, 1] == g
                    for k, z in enumerate(uz):
                        z_idx = self.full_grid[:, 2] == z
                        flx = self.full_grid[:, 3 + ii][t_idx * g_idx * z_idx]
                        insert = flx[0] if len(flx) == 1 else 0
                        cube[i, j, k] = insert
            filt_idx = sp.where(f == self.filter_names)[0]
            interpolators[filt_idx] = RegularGridInterpolator(
                (ut, ug, uz), cube, bounds_error=False)
        with closing(open(out_name + '.pkl', 'wb')) as jar:
            pickle.dump(interpolators, jar)

    def get_interpolated_flux(self, temp, logg, z, filt):
        """Interpolate the grid of fluxes in a given teff, logg and z.

        Parameters
        ----------
        temp : float
            The effective temperature.

        logg : float
            The superficial gravity.

        z : float
            The metallicity.

        filt : str
            The desired filter.

        Returns
        -------
        flux : float
            The interpolated flux at temp, logg, z for filter filt.

        """
        values = (temp, logg, z) if not self.fixed_z else (temp, logg)
        flux = self.interpolators[filt](values)
        return flux

    def calculate_distance(self):
        """Calculate distance using parallax in solar radii."""
        dist = 1 / (0.001 * self.plx)
        dist_e = dist * self.plx_e / self.plx
        self.dist = dist
        self.dist_e = dist_e
