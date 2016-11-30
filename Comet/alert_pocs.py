#!/usr/bin/env python

import sys
import voeventparse as vo
from voeventparse.tests.resources.datapaths import swift_bat_grb_pos_v2 as test_vo

import logging
logging.basicConfig(filename='script2.log',level=logging.INFO)
logger = logging.getLogger('notifier')
logger.handlers.append(logging.StreamHandler(sys.stdout))

from fourpiskytools.notify import Notifier

from pocs.utils.messaging import PanMessaging as pm

sender = pm('publisher', 6500)

test = True

def get_ra(c):

     h = int(c)
     m = abs(int((c-h)*60))
     s = round(abs(60*(abs((c-h)*60)-m)),3)

     hrs = str(int(h*24/100))
     
     ra = hrs + 'h' + str(m) + 'm' + str(s) + 's'
     
     return ra

def get_dec(c):
     
     d = int(c)
     m = abs(int((c-d)*60))
     s = round(abs(60*(abs((c-d)*60)-m)),3)

     deg = str(d)
     if c >= 0:
          deg = '+' + deg
     elif d < 1 and d >=0:
          deg = '-' + deg 
     
     dec = deg + 'h' + str(m) + 'm' + str(s) + 's'

     return dec

def get_time(t):

     time = str(t)[0:19]

     return time

if __name__ == '__main__':
     
     if test == False:
          v = sys.stdin.read()
     else:
          v = test_vo
     v_o = voeventparse.loads(v)

     c = vo.pull_astro_coords(v_o)
     t = vo.pull_isotime(v_o)
     name =  v.Who.Author.shortName

     coords = get_ra(c[0]) + ' ' + get_dec(c[1])

     time = get_time(t)

     sender.send_message('scheduler', {'message': 'add', 'targets': [{'target': name, 
                                                                      'position': coords, 
                                                                      'priority': 1000, 
                                                                      'expires_after': 10, 
                                                                      'exp_time': 120}]})


