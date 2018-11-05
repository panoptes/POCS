# Create an image with ONLY the astrometry index files we use,
# copied from the host. This allows us to work around the fact
# that astrometry.net has been rather unreliable (i.e. offline).
#
# To build:
#
#    docker build --tag panoptes/astrometry-indices \
#           --file "${POCS}/ci/astrometry-data/Dockerfile" \
#           -- "${PANDIR}/astrometry/data"

FROM scratch
COPY index-*.fits /var/panoptes/astrometry/data/
