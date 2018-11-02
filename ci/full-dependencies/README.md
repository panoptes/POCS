POCS Continuous Integration Dependencies
========================================

This directory has tools for building a docker image with the dependencies needed
to run the POCS tests. It is not for running POCS on a scope, nor directly for
development.

## Setup

### Clone and install POCS

The following assumes you have a clone of the POCS git repo on your machine,
with the $POCS environment variable set to the location of the clone on
your machine (e.g. /var/panoptes/POCS).

### Docker

[Docker](https://www.docker.com/what-docker) is an application that lets you run existing
services, in this case POCS, on a kind of virtual machine. By running via Docker you
are guranteeing you are using a setup that works, saving you time on setup and 
other issues that you might run into doing a manual install.

Of course, this also means that you need to set up Docker. Additionally, you will
need to be able to log into our Google Docker container storage area so you can pull
down the existing image. The steps below should help you to get going.

#### Install Docker

Depending on what operating system you are using there are different ways of getting
Docker on your system. The Docker [installation page](https://www.docker.com/community-edition) 
should have all the answers you need.

## Build the image

Execute this command:

```
docker build --tag panoptes/build --file $POCS/ci/Dockerfile -- $POCS
```

