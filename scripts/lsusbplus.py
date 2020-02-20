import os
import sys
from subprocess import Popen, PIPE
import fcntl

BASEDIR = 'cd /sys/devices/pci0000:00'
DataStorageMatrix = []
TemporaryDataStorageList = []

#Finding dev path and relating it to bus number and dev number
StartLocationProbe = BASEDIR + ' ; sudo find -maxdepth 2 -name "usb*"'
StartLocation = Popen(StartLocationProbe, shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
NEWBASEDIR = BASEDIR + ' ; cd ' + StartLocation[0] #I believe that on NUC usb1 holds information about all real devices, this entire section can be put in while loop to search for other usb directories if needed
SearchLocationProbe = NEWBASEDIR + ' ; find . -name "*-*:*"'
SearchLocations = Popen(SearchLocationProbe, shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
Num_Searches = len(SearchLocations)
i = Num_Searches
while i > 0:
   CurrentIndex = Num_Searches - i
   SearchLocation = NEWBASEDIR + ' ; cd ' + SearchLocations[CurrentIndex]
   DevPathProbe = SearchLocation + ' ; find -maxdepth 2 ! -name "tty"  -name "tty*"'
   DEVPATH = Popen(DevPathProbe, shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,close_fds=True).stdout.read().strip().decode('utf-8')
   if (DEVPATH == ""):
      i -= 1
      continue
   if (DEVPATH.startswith("./tty/")):
      PARSEDDEVPATH = DEVPATH.split("./tty/")
      PARSEDDEVPATH.remove("")
   if (DEVPATH != ""):
      if (DEVPATH.startswith("./tty/")):
         PARSEDDEVPATH = DEVPATH.split("./tty/")
      elif (DEVPATH.startswith("./tty")):
         PARSEDDEVPATH = DEVPATH.split("./")
      PARSEDDEVPATH.remove("")
      BUSNUMDEVNUMPROBE = SearchLocation + " ; cd .. ; cat busnum ; cat devnum"
      BUSNUMDEVNUM = Popen(BUSNUMDEVNUMPROBE, shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,close_fds=True).stdout.read().strip().decode('utf-8')
      TemporaryDataStorageList = BUSNUMDEVNUM.split("\n")
      TemporaryDataStorageList.insert(0, PARSEDDEVPATH[0])
      DataStorageMatrix.append(TemporaryDataStorageList)
   i -= 1

#Parsing lsusb for matching and reprinting

lsusb = Popen("lsusb", shell=True, bufsize=64, stdin=PIPE, stdout=PIPE,close_fds=True).stdout.read().strip().decode('utf-8')
lsusblines = lsusb.split("\n")
num_devices = len(lsusblines)
l = num_devices
DataStorageMatrixLength = len(DataStorageMatrix)
while l > 0:
   line = num_devices - l
   lineinformation = lsusblines[line].split(" ")
   devicelineinformation = lineinformation[3].split(":")
   bus = str(int(lineinformation[1]))
   dev = str(int(devicelineinformation[0]))
   #Pre-parsing lsusb output for cleaner dev path text insertion
   lsusblines[line] = lsusblines[line].split(": ")
   lsusblines[line][0] = lsusblines[line][0] + ": DevPath "
    k = DataStorageMatrixLength
   FoundScore = 0
   while k > 0:
      DataSet = DataStorageMatrixLength - k
      if (bus == DataStorageMatrix[DataSet][1] and dev == DataStorageMatrix[DataSet][2]):
         lsusblines[line][0] = lsusblines[line][0] + "\033[1;32;40m" + DataStorageMatrix[DataSet][0] + " \033[1;37;40m"
      elif (bus != DataStorageMatrix[DataSet][1] or dev != DataStorageMatrix[DataSet][2]):
         FoundScore += 1
      if ((bus != DataStorageMatrix[DataSet][1] or dev != DataStorageMatrix[DataSet][2]) and FoundScore == 4):
         lsusblines[line][0] = lsusblines[line][0] + "\033[1;31;40mno-path\033[1;37;40m "
      k -= 1
   l -= 1

#Print out that parsed info!
for x in lsusblines:
   print("")
   for y in x:
      print(y, end='')
print("")
