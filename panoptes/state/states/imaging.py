"""@package panoptes.state.states
All the current PANOPTES states
"""
import time

from panoptes.state import state

class Imaging(state.PanoptesState):

    def setup(self, *args, **kwargs):
        self.outcomes = ['analyzing']
        self.exp_time = 240 * 60 # minutes * seconds
        self.interval = 10 # seconds

        self.tracking_file = 'foo.txt'

    def run(self):
        self.logger.info("Exposing for {} seconds".format(self.exp_time))

        counter = self.exp_time

        with open(self.tracking_file, 'w') as f:
            print("{}".format('*'*20),file=f, flush=True)

            while counter:
                alt = self.observatory.mount.serial_query('get_alt')
                az = self.observatory.mount.serial_query('get_az')

                pier_position = self.observatory.mount.pier_position()

                print("{}\t{}\tPier: {}".format(alt,az,pier_position),file=f, flush=True)

                time.sleep(self.interval)
                counter -= self.interval
                self.logger.info("Exposing for {} more seconds".format(counter))

        self.outcome = 'analyzing'
