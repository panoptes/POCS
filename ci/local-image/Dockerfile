# Creates a docker image for running or testing PANOPTES as a specified user.

FROM panoptes/full-dependencies

ARG user_name=
ARG user_id=
ARG group_name=
ARG group_id=

RUN groupadd -g $group_id $group_name && \
    useradd -u $user_id -g $group_id -d /home/$user_name $user_name && \
    echo "Changing ownership of $PANDIR from root to $user_name, which is REALLY slow."
# James measured this as 38 minutes on his laptop.
# This makes it likely that we need some ability to choose the user and
# group that execute the miniconda install.
RUN date && chown -R $user_id:$group_id $PANDIR && date

USER $user_id:$group_id

WORKDIR /home/$user_name

# Make sure expected files exist.
RUN [ -f .bashrc ]
RUN [ -f "${PANDIR}/set-panoptes-env.sh" ]

# Create the new .bashrc for the user.
RUN echo "# Added by PANOPTES install-dependencies.sh" > new.bashrc && \
    echo "source ${PANDIR}/set-panoptes-env.sh" >> new.bashrc && \
    cat .bashrc >> new.bashrc

RUN echo "Created new.bashrc:"
RUN cat new.bashrc
RUN rm .bashrc && mv new.bashrc .bashrc

WORKDIR $POCS

CMD ["/bin/bash"]
