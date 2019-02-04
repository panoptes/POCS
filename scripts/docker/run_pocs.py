#!/usr/bin/env python3

from pocs.observatory import Observatory
from pocs.core import POCS
from pocs.utils import error


def main(simulator='all'):
    try:
        print("Setting up POCS")
        observatory = Observatory(simulator=simulator)
        pocs = POCS(observatory, messaging=True)
        pocs.initialize()
        print("POCS initialized")
        # pocs.run()
    except error.PanError as e:
        print('Problem setting up POCS: {}'.format(e))


if __name__ == '__main__':
    main()
