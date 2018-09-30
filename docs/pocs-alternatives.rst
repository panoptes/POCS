=================
POCS Alternatives
=================

A primary software adage is to avoid "recreating the wheel" and while 
automated OCS systems are not unique, an initial review found that none of the
available systems were suitable to the PANOPTES goals outlined in the 
`PANOPTES Overview <panoptes-overview.html>`_. First, all software that
required license fees or was not otherwise free (of cost) and open (to 
modification) was not applicable. Second, software was examined in 
terms of its ability to handle the hardware and observing requirements of a 
PANOPTES unit. Third, the ease-of-use of the software was determined,
both in terms of installation and usage as well as in ability to serve as a 
learning tool. Three popular alternatives to the POCS ecosystem were 
identified. A brief summary of each is given along with reasons for rejection
(in alphabetical order):

INDI
----

`INDI <http://www.indilib.org>`_ (Instrument-Neutral-Distributed-Interface) 
consists of both a protocol for agnostic hardware control and a library that 
implements that protocol in a server/client architecture. INDI is written 
specifically as an astronomical tool and seems to be used exclusively within
astronomical applications. The code base is written almost exclusively in 
C/C++ and the software is thus static and requires compilation in order to 
run. The software is released under a GPLv2 license and undergoes active 
development and maintenance.

The basic idea behind INDI is that hardware (CCDs, domes, mounts, etc.) is 
described (via drivers) according to the INDI protocol such that an INDI 
server can communicate between that hardware and a given front-end client 
(software used by the astronomer which can either be interactive or 
automated) using standard Inter-process Communication (ICP) protocols 
regardless of the particular details of the hardware.

This is in fact an ideal setup for a project like PANOPTES and INDI was 
initially used as a base design, with POCS serving primarily as an INDI 
client and a thin-wrapper around the server. However, because of the lack of 
suitable drivers for the chosen mount as well as complications with the 
camera driver and the implementation of the server software, this approach 
was eventually abandoned. It should be noted, however, that the server/client
architecture and the agnostic hardware implementation in both POCS and INDI 
means that the eventual adoption of INDI should be largely straight-forward. 
Should a group choose to implement this approach in the future, much of the 
hardware specifications contained within POCS could be relegated to INDI, 
allowing POCS to be a specific implementation of an INDI server/client 
interaction. The specific details of POCS (state-based operation, scheduling
details, data organization and analysis) would remain largely unchanged.

ROS / OpenROCS
--------------

`ROS <http://www.ros.org>`_ (Robotic Operating System) is a set of software 
libraries and various other scripts designed to control robotic components. 
The idea is similar to INDI but ROS is designed to work with robotic hardware 
in general and has no specific association with astronomy. ROS has a 
widespread community and significant adoption within the robotics
community, specifically concerning industrial automation. In addition to 
simple hardware control, ROS also implements various robotics-specific 
algorithms, such as those associated with machine vision, movement, robotic 
geometry (self-awareness of spatial location of various components of the 
robot), and more. The specific design goals of ROS relate to its use as a 
library for "large-scale integrative robotics research" for "complex" systems [73]. The library is designed to be multi-lingual (with respect to 
programming languages) via the exchange of language-agnostic message. The 
entire library consists of a number of packages and modules that require 
specific management policies (although these can be integrated with the 
host-OS system package manager).

ROS is primarily designed to be used in large-scale applications and 
industrial automation and was thus found to be unsuitable for the design 
goals of PANOPTES. Specifically, the package management overhead made the 
system overly complex when compared with the needs of PANOPTES. While there 
are certainly some examples of small-scale robotics implementations available 
on the website13 for ROS, the adoption of the software as a basis for 
PANOPTES would have required significant overhead merely to understand the 
basic operations of POCS. Working with the system was thus seen as too 
complex for non-professionals and students.

However, the advantages of the messaging processing system used by ROS were 
immediately obvious and initially the messaging system behind the PANOPETS 
libraries was based directly on the ROS messaging packages. Unfortunately, 
because of the complexity of maintaining some of the ROS subpackages without 
adoption of the overall software suite this path was eventually abandoned. 

The core ideas behind the messaging system (which are actually fairly generic 
in nature) have nevertheless been retained. More recently others have pursued 
the use of ROS specifically for use within autonomous observatories. While 
the authors report success, the lack of available code and 
`documentation <http://wiki.ros.org>`_ make the software not worth pursuing in light of the fact that POCS had already undergone significant development 
before the paper was made available. 

Details about the code are sparse within the paper and the corresponding `website <https://redmine.ice.csic.es/projects/openrocs>`_
(accessed 2017-01-24) doesn’t offer additional details.

RTS2
----

`RTS2 <https://rts2.org>`_ is a fairly mature project that was originally developed for the BART telescope for autonomous gamma ray burst (GRB) 
followup. The overall system is part of the `GLORIA Project <http://gloria-project.eu/publications-and-more>`_,
which has some shared goals with the PANOPTES network but is aimed at more 
professional-level telescopes and observatories18. The software implements a 
client/server system and hardware abstraction layer similar to INDI. The 
software base is primarily written in C++ and released under a LGPL-3.0 
license and is under active development. RTS2 further includes logical 
control over the system, which includes things such as scheduling, 
plate-solving, metadata tracking, etc.

The primary reason for not pursuing RTS2 as the base for PANOPTES was due to 
the desire to employ Python as the dominant language. While RTS2 could 
provide for the operational aspects of PANOPTES it was not seen as suitable 
for the corresponding educational aspects.
