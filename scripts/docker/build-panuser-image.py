#!/usr/bin/env python3
#
# Script to create a docker image with the specified user and group
# created and set to the USER; also makes that user name the value of
# the PANUSER environment. This is typically either the current
# user (developer or CI case) or a user called panoptes for automated
# execution on a unit. The user must exist on the host computer.

import argparse
import grp
import os
import pwd
import shutil
import subprocess
import sys
import tempfile


def generate_dockerfile(base_image='ubuntu:18.04',
                        user_name='panoptes',
                        user_id=None,
                        group_name='panoptes',
                        group_id=None,
                        pandir=None,
                        command='/bin/bash'):
    if not isinstance(user_id, int):
        user_id = ''
    if not isinstance(group_id, int):
        group_id = ''

    dockerfile = f"""
FROM {base_image}

LABEL author="Developers for PANOPTES project"
LABEL url="https://github.com/panoptes/POCS"

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PANUSER {user_name}

# Create user PANUSER ({user_name}).

COPY create-panoptes-user.sh /workdir/
RUN PANUSER={user_name} PANUSER_ID={user_id} \\
    PANGROUP={group_name or ''} PANGROUP_ID={group_id} \\
    NO_PASSWORD=true \\
    /workdir/create-panoptes-user.sh && \\
    rm -rf /workdir
"""
    if pandir:
        dockerfile += f"""

# Set PANDIR and create the directory, owned by PANUSER.

ENV PANDIR {pandir}
RUN mkdir -p {pandir}
RUN chown -R {user_name}:{group_name or user_name} {pandir}
WORKDIR {pandir}
"""
    dockerfile += f"""

USER {user_name}
CMD {command}
"""
    return dockerfile


def getusername():
    uid = os.getuid()
    entry = pwd.getpwuid(uid)
    return entry.pw_name


def main():
    parser = argparse.ArgumentParser(description='Create docker image for the specified user.')
    parser.add_argument(
        '--user',
        dest='user_name',
        type=str,
        default=(os.environ.get('PANUSER') or getusername()),
        help=('Name of the PANUSER in the image. '
              'If specified, the user must exist.'))
    parser.add_argument(
        '--group',
        dest='group_name',
        type=str,
        help=('Primary group of the user PANUSER in the image. '
              'If specified, the group must exist.'))
    parser.add_argument(
        '--pandir',
        dest='pandir',
        type=str,
        default=(os.environ.get('PANDIR') or '/var/panoptes'),
        help='Root directory of PANOPTES software and data.')
    parser.add_argument(
        '--base-image',
        dest='base_image',
        type=str,
        default='ubuntu:18.04',
        help='Base image from which to create this image.')
    parser.add_argument(
        '--command',
        dest='command',
        type=str,
        default='/bin/bash',
        help='Command to run when the image is launched in a container.')
    parser.add_argument('--tag', dest='tag', type=str, help='Tag to apply to the created image.')
    parser.add_argument('--verbose', '-v', action='store_true')

    args = parser.parse_args()

    def arg_error(msg):
        print(msg, '\n', file=sys.stderr)
        parser.print_help(file=sys.stderr)
        sys.exit(1)

    try:
        pwent = pwd.getpwnam(args.user_name)
        user_name = pwent.pw_name
        user_id = pwent.pw_uid
        group_id = pwent.pw_gid
    except KeyError:
        arg_error(f'User with name "{args.user_name}" not found.')

    if args.group_name:
        try:
            grent = grp.getgrnam(args.group_name)
            assert args.group_name == grent.gr_name
            group_name = grent.gr_name
            group_id = grent.gr_gid
        except KeyError:
            arg_error(f'Group with name "{args.group_name}" not found.')
    else:
        # Not putting a try-except here because a KeyError implies that
        # something is wrong with the pwd and grp lookups, not with the
        # user's input.
        grent = grp.getgrgid(group_id)
        assert group_id == grent.gr_gid
        group_name = grent.gr_name

    if args.pandir:
        if not os.path.isabs(args.pandir):
            arg_error(f'PANOPTES directory must be an absolute path, not: {args.pandir}')
        pandir = args.pandir
    else:
        pandir = None

    dockerfile = generate_dockerfile(
        base_image=args.base_image,
        user_name=user_name,
        user_id=user_id,
        group_name=group_name,
        group_id=group_id,
        pandir=pandir,
        command=args.command)
    if args.verbose:
        print('Using this dockerfile:')
        print('#' * 80)
        print(dockerfile)
        print('#' * 80)

    tag = args.tag or f'panuser-{user_name}'

    with tempfile.TemporaryDirectory() as tmpdir:
        with open(os.path.join(tmpdir, 'Dockerfile'), 'w') as f:
            f.write(dockerfile)
        create_script = os.path.join(os.environ['POCS'], 'scripts', 'install',
                                     'create-panoptes-user.sh')
        shutil.copy(create_script, tmpdir)
        build_args = ['docker', 'build', '--tag', tag, tmpdir]
        if args.verbose:
            print('Running command:', build_args)
            sys.exit(subprocess.call(build_args, timeout=3600))
        result = subprocess.run(
            build_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=3600)

    if result.returncode == 0:
        os.system(f'docker image ls {tag}')
        sys.exit(0)
    print('docker build failed with status', result.returncode)
    print('docker build output:')
    print(result.stdout)


if __name__ == '__main__':
    main()
