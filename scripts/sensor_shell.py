#!/usr/bin/env python
import cmd

from peas.webcams import Webcams


class PanSensorShell(cmd.Cmd):
    """ A simple command loop for the sensors. """
    intro = 'Welcome to PanSenorShell! Type ? for help'
    prompt = 'PAN > '
    webcams = None

    def do_load_webcams(self, *arg):
        print("Loading webcams")
        self.webcams = Webcams()

    def do_start_webcams(self, *arg):
        if self.webcams is None:
            self.do_load_webcams()

        print("Starting webcam capture")
        self.webcams.start_capturing()

    def do_stop_webcams(self, *arg):
        print("Stopping webcam capture")
        self.webcams.stop_capturing()

    def do_exit(self, *arg):
        print("Shutting down")
        self.do_stop_webcams()

        print("Bye! Thanks!")
        return True

if __name__ == '__main__':
    PanSensorShell().cmdloop()
