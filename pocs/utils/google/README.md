# PANOPTES Google Network

PANOPTES uses various google technologies in order to effectively
create a network of automated observatories. This includes basic 
image storage on google servers (called storage _buckets_) as well
as CloudSQL databases and other technologies.

## Prerequisites

To use the google network it is required that a few google software 
tools be installed. Detailed [instructions for Ubuntu](https://cloud.google.com/sdk/docs/downloads-apt-get) are provided.

> Todo: Add into the install script

## Register PANOPTES unit

To use these services your PANOPTES unit must first be registered 
with the network, which means you have been given an official unit_id 
designation (e.g. PAN001, PAN017, etc) and have also been given a 
_service account key_. Currently this process is manual, which means
if you need one you should ask the core [PANOPTES team](https://projectpanoptes.org/contact.html).

## Service account key

Your service account key will be named something like `panoptes-survey-pan001.json` and will be a simple text file. We will use the PAN001 key name as an example.

> :warning: **Warning** Your service account key is basically a password file and should be kept secret. Do not share the key with others or save in the git repository.

You should place this key in a hidden directory within `$PANDIR`.

```bash
cd $PANDIR

# Make a hidden directory
mkdir -p .keys  

# Move the key file to the hidden directory
mv <LOCATION_OF_DOWNLOADED_KEY_FILE>/panoptes-survey-pan001.json $PANDIR/.keys/
```

## Authenticating on PANOPTES' Google network

Once you have your service account key you can authenticate (log in) to the PANOPTES network once and never worry about it again!

The [instructions by google](https://cloud.google.com/sdk/gcloud/reference/auth/activate-service-account) provide detailed information but the basic command is:

```bash
gcloud auth activate-service-account \
	--project panotpes-survey \
	--key-file $PANDIR/.keys/panoptes-survey-pan001.json
```