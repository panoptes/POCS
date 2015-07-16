#!/bin/sh

echo "************** Updating System and Installing Requirements **************"

# Update packages
sudo apt-get update
sudo apt-get install -y aptitude

# Install additional useful software
echo "Installing some required software"
sudo aptitude install -y openssh-server build-essential git htop mongodb fftw3 fftw3-dev libatlas-base-dev libatlas-dev sextractor libplplot-dev

# Add Dialout Group
echo "Adding panoptes user to dialout group"
sudo adduser panoptes dialout

# This is ~300 MB so may take a while to download
echo "Getting Anaconda"
wget https://3230d63b5fc54e62148e-c95ac804525aac4b6dba79b00b39d1d3.ssl.cf1.rackcdn.com/Anaconda3-2.2.0-Linux-x86_64.sh

# After download, install with following command, choosing default options except the very
# last option, and say 'yes' to whether you want to append to your .bashrc
echo "Downloading conda"
bash Anaconda3-2.2.0-Linux-x86_64.sh

# Update the anaconda distribution
echo "Updating conda"
conda update conda

# Check your python version
echo "Checking python version"
python -V

echo "Updating gphoto2"
wget https://raw.githubusercontent.com/gonzalo/gphoto2-updater/master/gphoto2-updater.sh && chmod +x gphoto2-updater.sh && sudo ./gphoto2-updater.sh

# Get and install cdsclient
echo "Installing cdsclient"
wget http://cdsarc.u-strasbg.fr/ftp/pub/sw/cdsclient.tar.gz
tar -zxvf cdsclient.tar.gz && cd cdsclient-3.80/ && ./configure && make && sudo make install && cd $HOME

echo "Installing SCAMP"
wget http://www.astromatic.net/download/scamp/scamp-2.0.4.tar.gz
tar -zxvf scamp-2.0.4.tar.gz && cd scamp-2.0.4
./configure --with-atlas-libdir=/usr/lib/atlas-base --with-atlas-incdir=/usr/include/atlas --with-fftw-libdir=/usr/lib --with-fftw-incdir=/usr/include --with-plplot-libdir=/usr/lib --with-plplot-incdir=/usr/include/plplot
make && sudo make install

echo "Installing SWARP and astrometry.net"
sudo aptitude install -y install swarp astrometry.net

echo "Getting astrometry.net indicies"
cd /usr/share/data && sudo wget -A fits -m -l 1 -nd http://broiler.astrometry.net/~dstn/4100/


echo "************** Done with Requirements **************"
echo "************** Starting with Project Install **************"

# Make a directory for Project PANOPTES
echo "Creating project directories"
sudo mkdir -p /var/panoptes/data/               # Metadata (MongoDB)
sudo mkdir -p /var/panoptes/images/webcams/     # Images
sudo chown -R panoptes:panoptes /var/panoptes/
echo 'Adding environmental variable: PANDIR=/var/panoptes/'
echo 'export PANDIR=/var/panoptes/' >> ~/.bashrc
source ~/.bashrc

# Clone repos
echo "Grabbing POCS repo"
cd /var/panoptes && git clone https://github.com/panoptes/POCS.git
echo "Grabbing PACE repo"
cd /var/panoptes && git clone https://github.com/panoptes/PACE.git
echo "Grabbing PIAA repo"
cd /var/panoptes && git clone https://github.com/panoptes/PIAA.git

# Add a permanent variable to refer to project
echo 'Adding environmental variable: POCS=$PANDIR/POCS'
echo 'Adding environmental variable: PACE=$PANDIR/PACE'
echo 'Adding environmental variable: PIAA=$PANDIR/PIAA'
echo 'export POCS=$PANDIR/POCS' >> ~/.bashrc
echo 'export PACE=$PANDIR/PACE' >> ~/.bashrc
echo 'export PIAA=$PANDIR/PIAA' >> ~/.bashrc
source ~/.bashrc

echo "Installing required python modules"
pip install -r $POCS/requirements.txt

# Upgrade system
echo "Upgrading system"
sudo aptitude -y full-upgrade

# Reboot for fun
echo "Rebooting system"
sudo reboot
