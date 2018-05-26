These scripts support starting the PANOPTES software automatically
when the Linux computer that runs a PANOPTES starts or restarts.
We assume here that you are logged in as user $PANUSER, and that user
$PANUSER has permissions to execute `sudo`.

> Note: We use `tmux`, a [terminal
> multiplexer](https://en.wikipedia.org/wiki/Terminal_multiplexer),
> to run all of the software. This means that when the computer boots,
> it can create several virtual terminals, each running a separate
> program. Later, when you want to see what those programs are doing,
> you can login and attach to those terminals. With `tmux`, the command
> to do that is:
> ```bash
> tmux attach-session -t panoptes
> ```

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

When you are ready to have the telescope run automatically (i.e. have
done all the manual setup and alignment that you need to), follow one
of these steps to arrange for your telescope to run automatically after
reboot.

> Note: the EDITOR environment variable allows you to specify the
> editor used by commands such as `crontab`. `nano` is a simple editor
> that runs in almost any terminal window. On some systems, the
> default editor may be `vi` or `vim`, which are rather more difficult
> to use than `nano`, unless you're already familiar with them.

## Crontab

[Crontab](https://linux.die.net/man/5/crontab) provides a means to run
a command line at various times. Some versions of crontab have support
for [`@reboot`](https://www.google.com/search?q=crontab+%40reboot) as
a *time* at which to run a command. If your system has this feature,
it is the easiest way to launch the PANOPTES software.

You can test whether `@reboot` works by adding a rule that
leaves an indication of whether it works. For example:

```bash
@reboot touch /tmp/at-reboot-worked
```

Add the rule to your ($PANUSER) crontab by executing the command
`crontab -e`, which will start an editor on your crontab file. After
you add that rule at the end of the file, save the file and exit the
editor. You can confirm that it was added correctly by viewing the
file with the command `crontab -l`. Next, reboot the computer (e.g.
with the command `sudo shutdown -r now`), log back in, remove that
test rule, and see if `/tmp/at-reboot-worked` was created. If it was,
then `@reboot` works. Otherwise, skip the `@reboot` rule in the
steps that follow, and follow the instructions in 
__Execution by `root`__ after editing your crontab.

Add these lines to your ($PANUSER) crontab by executing the command
`crontab -e`:

```bash
POCS=/var/panoptes/POCS
PANLOG=/var/panoptes/logs

# m h  dom mon dow   command
@reboot              /bin/bash --login $POCS/scripts/startup/tmux_launch.sh >> $PANLOG/tmux_launch.cron-reboot.log 2>&1
*/5 *   *   *   *    /bin/bash --login $POCS/scripts/plot_weather.sh >> $PANLOG/plot_weather.cron.log 2>&1
11  12  *   *   *    /bin/bash --login $POCS/scripts/download_support_files.sh >> $PANLOG/download_support_files.cron.log 2>&1
```

If your values for POCS and PANLOG don't match those shown above, please
edit them appropriately. Use the fully evaluated values (e.g. the
value produced by `echo $POCS` and by `echo $PANLOG`), as `cron`
does not expand variables in those lines.

Save the edited file and exit the editor.

Notice that each of these commands starts with `/bin/bash --login`. We
do this because, by default, `cron` runs commands in a very minimal
environment with /bin/sh as the shell. This means that the PANOPTES
environment variables are not set, nor is the appropriate conda
environment activated. The `/bin/bash --login` selects the correct
shell and tells that shell to initialize its environment.

The other two rules are for generating a plot (image) of the
weather sensor data every 5 minutes and for updating astronomical
coordinate system data every day at 11 minutes after noon.

## Execution by `root`

If your crontab does not support the `@reboot` directive, you can modify
the Linux boot scripts to start the PANOPTES software. For that, we
provide the script `su_panoptes.sh`.

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

To edit the file, run this command:

```bash
sudo nano /etc/rc.local
```

As the default text says, you may need to enable that script to execute:

```bash
sudo chmod +x /etc/rc.local
```
