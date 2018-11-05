POCS Linux Package Dependencies
===============================

This directory has tools for building a docker image with the Linux packages
needed by POCS (i.e. those packages installed using apt and/or built and
installed into /usr/lib, etc.).
All operations are performed as 'root' in order to support installing into
/bin or /usr/bin.
Other images can then be layered on this which use other users (e.g. the
'panoptes' user for executing on scopes, or the local developer for local
testing.

## Build the image

Execute this command:

```
./docker-build.sh
```

