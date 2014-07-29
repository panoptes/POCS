# -*- coding: utf-8 -*-
""" @package Panoptes

POCS is a the Panoptes Observatory Control System

* Documentation: http://panoptes-pocs.readthedocs.org/
* Source Code: https://github.com/panoptes/POCS
"""
import os
import yaml

import panoptes.utils.logger as logger
import panoptes.utils.config as config
import panoptes.utils.error as error

import panoptes.observatory as observatory
import panoptes.state.statemachine as sm


# Panoptes Class
# This class is a driver program that holds a :py:class:`panoptes.Observatory`
#

@logger.has_logger
@config.has_config
class Panoptes(object):

    def __init__(self):
        # Setup utils
        self.logger.info('*' * 80)
        self.logger.info('Initializing panoptes unit')

        # Sanity check out config
        self._check_config()

        # Create our observatory, which does the bulk of the work
        self.observatory = observatory.Observatory()

        self.state_table = self._load_state_table()

        # Get our state machine
        self.state_machine = self._setup_state_machine()


    def _check_config(self):
        if 'base_dir' not in self.config:
            raise error.InvalidConfig('base_dir must be specified in config_local.yaml')

        if 'name' in self.config:
            self.logger.info('Welcome {}'.format(self.config.get('name')))

        if 'mount' not in self.config:
            raise error.MountNotFound('Mount must be specified in config')

        if 'state_machine' not in self.config:
            raise error.InvalidConfig('State Table must be specified in config')


    def _load_state_table(self):
        # Get our state table
        state_table_name = self.config.get('state_machine', 'simple_state_table')
        
        state_table_file = "{}/resources/state_table/{}.yaml".format(self.config.get('base_dir'),state_table_name)

        state_table = dict()

        try:
            with open(state_table_file, 'r') as f:
                state_table = yaml.load(f.read())
        except OSError as err:
            raise error.InvalidConfig('Problem loading state table yaml file: {}'.format(err))        
        except:
            raise error.InvalidConfig('Problem loading state table yaml file: {}'.format())        

        return state_table


    def _setup_state_machine(self):
        """
        Sets up the state machine including defining all the possible states.
        """
        # Create the machine
        machine = sm.StateMachine(self.observatory, self.state_table)

        return machine


if __name__ == '__main__':
    panoptes = Panoptes()
    panoptes.logger.info("Panoptes created. Starting session")
