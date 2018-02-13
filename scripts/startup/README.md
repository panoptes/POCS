These scripts support starting the PANOPTES software automatically
when the Linux computer that runs a PANOPTES starts or restarts.

First we need to have the PANOPTES environement variables set in all
the shells that are involved in running PANOPTES. The simplest
solution is to set them globally on the system. For example,
on Ubuntu:

```bash
sudo cp $POCS/scripts/startup/set_panoptes_env_vars.sh \
        /etc/profile.d/
sudo chmod +x /etc/profile.d/set_panoptes_env_vars.sh
```

This will then be executed when any user logs in. The exact means
of doing this varies on different versions of Unix/Linux.

Next, we need to arrange for `su_panoptes.sh` to be executed when
the operating system launches. First copy it to /etc:

```bash
sudo cp $POCS/scripts/startup/su_panoptes.sh \
        /etc/
sudo chmod +x /etc/su_panoptes.sh
```

Next, edit `/etc/rc.local`, adding a command to run `su_panoptes.sh`.
For example, adding it to the default Ubuntu `rc.local`:

```bash
#!/bin/sh -e
#
# rc.local
#
# This script is executed at the end of each multiuser runlevel.
# Make sure that the script will "exit 0" on success or any other
# value on error.
#
# In order to enable or disable this script just change the execution
# bits.
#
# By default this script does nothing.

/etc/su_panoptes.sh >> /tmp/su_panoptes.log 2>&1

exit 0
```
