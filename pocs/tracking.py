import os
import yaml

import numpy as np

import astropy.units as u

class TrackingModel(object):
    '''
    Model Parameters
    phi0: phase of worm at zero point of HA (u.radian)
    dH: change in hour angle for a single revolution of the worm (u.hourangle)
    PE0: Amplitude of PEC rate correction sin wave (u.arcsec)

    '''
    def __init__(self):
        self.path = os.path.join(os.path.expandvars('$POCS'), 'resources')
        self.filename = 'tracking_model.yaml'
        self.file = os.path.join(self.path, self.filename)
        self.load_model_parameters()
        self.R_sidereal = u.Quantity([15,0]*u.arcsec/u.second)


    def get_phi(self, H):
        phi = (H.value % self.dH.value) / self.dH.value * 2.*np.pi * u.radian
        return phi


    def R_PE(self, H):
        phi = self.get_phi(H)
        # PE = self.PE0 * np.sin(phi)
        R_PE = self.PE0 * np.cos(phi.to(u.radian).value) * 2.*np.pi/self.dT
        return u.Quantity([R_PE, 0*u.arcsec/u.second])


    def R_AD(self, H, D):
        return u.Quantity([0, 0]*u.arcsec/u.second)


    def get_tracking_rate(self, H, D):
        result = self.R_PE(H) + self.R_AD(H, D) + self.R_sidereal
        return result


    def store_model_parameters(self):
        parameters_dict = {'phi0': self.phi0.to(u.radian).value,
                           'dH': self.dH.to(u.hourangle).value,
                           'PE0': self.PE0.to(u.arcsec).value}
        if os.path.exists(self.file):
            os.remove(self.file)
        with open(self.file, 'w') as FO:
            FO.write(yaml.dump(parameters_dict))
            yaml.dump(parameters_dict)


    def load_model_parameters(self):
        with open(self.file, 'r') as FO:
            parameters_dict = yaml.load(FO)

        if 'phi0' in parameters_dict.keys():
            self.phi0 = parameters_dict['phi0']*u.radian
        else:
            self.phi0 = 0 * u.radian

        if 'dH' in parameters_dict.keys():
            self.dH = parameters_dict['dH']*u.hourangle
        else:
            self.dH = (8./60.) * u.hourangle
        self.dT = (self.dH / self.R_sidereal[0]).decompose()

        if 'PE0' in parameters_dict.keys():
            self.PE0 = parameters_dict['PE0']*u.arcsec
        else:
            self.PE0 = 40 * u.arcsec

        