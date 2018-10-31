POCS Continuous Integration
================================

## Setup

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

#### Install gcloud

`gcloud` is a command line utility that lets you interact with many of the Google
cloud services. We will primarily use this to authenticate your account but this
is also used, for example, to upload images your PANOPTES unit takes.

See the gcloud [installation page](https://cloud.google.com/sdk/docs/#install_the_latest_cloud_tools_version_cloudsdk_current_version)
for easy install instructions.

#### Let Docker use gcloud

Docker needs to be able to use your `gcloud` login to pull the PANOPTES images. There
are some helper scripts to make this easier (from [here](https://cloud.google.com/container-registry/docs/advanced-authentication)):

```
gcloud auth configure-docker
```

#### Pull POCS container

```
 docker pull gcr.io/panoptes-survey/pocs:latest
```

#### Start the POCS image

```
docker run -it --name pocs gcr.io/panoptes-survey/pocs
```

The container will just run the bash shell, allowing you to work with POCS and all its dependencies. 

Note that all changes inside the container started by this command will disappear after
the container exits. Further examples will be added with persistent state.

## Test POCS

POCS comes with a testing suite that allows it to test that all of the software 
works and is installed correctly. Running the test suite by default will use simulators 
for all of the hardware and is meant to test that the software works correctly. 
Additionally, the testing suite can be run with various flags to test that attached 
hardware is working properly.

The tests live in `$POCS/pocs/tests` and `$POCS/peas/tests`.
