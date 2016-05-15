#!/usr/bin/env python3

import subprocess


def main():
    pass

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Make a plot of the weather for a give date.")

    parser.add_argument("-d", "--date", "--start-date", type=str, dest="date", required=True, default=None,
                        help="Starting UT Date to plot. If no end-date is provided plots entire date")
    parser.add_argument("-d", "--end-date", type=str, dest="end_date", default=None,
                        help="Ending UT Date to plot, defaults to None, causing start-date to plot entire day.")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", default=False, help="Be verbose.")

    args = parser.parse_args()

    main(args.date)
