from . import PanState

""" Parked State

The Parked state occurs in the following conditions:
    * Daytime
    * Bad Weather
    * System error

As such, the state needs to check for a number of conditions.
"""

class State(PanState):
    def main(self):
        

        return 'exit'
