These scripts support starting the PANOPTES software automatically
when the Linux computer that runs a PANOPTES starts or restarts.
We assume here that you are logged in as user $PANUSER, and that user
$PANUSER has permissions to execute `sudo`.

# PANOPTES Environement Variables

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

If you've changed the location of the PANOPTES directories (e.g. if
log files are not stored in $PANDIR/logs), you'll need to edit that
script accordingly.

# Start PANOPTES Software on System Start

We intend for a PANOPTES telescope to run automatically, including after
reboots. We document these ways to achieve this:

* `@reboot` rule in crontab of user $PANUSER
* Execution by root during boot

## Crontab

[Crontab](https://linux.die.net/man/5/crontab) provides a means to run
a command line at various times. Some versions of crontab have support
for [`@reboot`](https://www.google.com/search?q=crontab+%40reboot) as
a *time* at which to run a command. If your system has this feature, it
is the easiest way to launch the PANOPTES software.
Add these lines to your ($PANUSER) crontab by executing the command
`crontab -e`, which will start an editor on your crontab file.

```bash
POCS=/var/panoptes/POCS
PANLOG=/var/panoptes/logs

# m h  dom mon dow   command
@reboot              /bin/bash --login $POCS/scripts/startup/tmux_launch.sh
*/5 *   *   *   *    /bin/bash --login python $POCS/scripts/plot_weather.py >> $PANLOG/plot_weather.log 2>&1
11  12  *   *   *    /bin/bash --login python $POCS/pocs/utils/data.py >> $PANLOG/update_data.log 2>&1
```

If your values for POCS and PANLOG don't match those show, please
edit them appropriately. Use the fully evaluated values (e.g. the
value produced by `echo $POCS` and by `echo $PANLOG`), as `cron`
does not expand variables in those lines.

Save the edited file and exit the editor.

Notice that each of these commands starts with `/bin/bash --login`. We
do this because `cron` does not run the commands in a shell with all
of the normal environment variables set, so we force that to happen.

## Execution by `root`

If necessary, you can modify the Linux boot scripts to start the
PANOPTES software. For that, we provide the script `su_panoptes.sh`.

First, copy that file to /etc:

```bash
sudo cp $POCS/scripts/startup/su_panoptes.sh \
        /etc/
sudo chmod +x /etc/su_panoptes.sh
```

Next, edit `/etc/rc.local`, adding a command to run `su_panoptes.sh`.
For example, adding it to the default Ubuntu `/etc/rc.local`:

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

As the default text says, you may need to enable that script to execute:

```bash
sudo chmod +x /etc/rc.local
```
