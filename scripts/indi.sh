#!/bin/sh

mkfifo /tmp/indififo
indiserver -f /tmp/indififo &
echo start indi_gphoto_ccd -n \"Cam00\" > /tmp/indififo
# echo start indi_gphoto_ccd -n \"testguide\" > /tmp/indififo
# echo start indi_simulator_focus -n \"focus\" > /tmp/indififo
# echo start indi_eqmod_telescope -n \"EQ3\" > /tmp/indififo