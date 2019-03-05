*************
POCS Overview
*************

The PANOPTES Observatory Control System (POCS) is the primary software
responsible for running a PANOPTES unit. POCS is implemented as a finite state
machine (described below) that has three primary responsibilities: 

* overall control of the unit for taking observations,
* relaying messages between various components of the system,
* and determining the operational safety of the unit.

POCS is designed such that under normal operating conditions the software is
initialized once and left running from day-to-day, with operation moving to a
sleeping state during daylight hours and observations resuming automatically
each night when POCS determines conditions are safe.

POCS is implemented as four separate logical layers, where increasing levels
of abstraction take place between each of the layers. These layers are the
low-level Core Layer, the Hardware Abstraction Layer, the Functional Layer,
and the high-level Decision Layer. 


.. note::
	.. image:: _static/pocs-graph.png

	**POCS software layers** Diagram of POCS software layers. Note that the
	items in yellow (Dome, Guider, and TheSkyX) are not typically used by PANOPTES
	observatories (note: PAN006 is inside an astrohaven dome).
	
	TheSkyX interface was added by the `Huntsman Telescope <https://twitter.com/AstroHuntsman>`_,
	which also uses POCS for control. They are included in the diagram as a 
	means of showing the flexibility of the Functional Layer to interact with
	components from the HAL.

====================
POCS Software Design
====================

Core Layer
----------

The Core Layer is the lowest level and is responsible for interacting directly 
with the hardware. For DSLR cameras this is accomplished by providing
wrappers around the existing `gphoto2 <http://www.gphoto.org/>`_ software
package. For PANOPTES, most other attached hardware works via direct RS-232
serial communication through a USB-to-Serial converter. A utility module was
written for common read/write operations that automatically handles details
associated with buffering, connection, etc. Support for TheSkyX was written 
into POCS for the `Huntsman Telescope <https://twitter.com/AstroHuntsman>`_. 
The overall goal of the Core Layer is to provide a consistent interface for 
modules written at the HAL level.

Hardware Abstraction Layer (HAL)
--------------------------------

The use of a HAL is widespread both in computing and robotics. In general, a
HAL is meant to hide low-level hardware and device specific details from
higher level programming [Elkady2012]_. Thus, while every camera ultimately
needs to support, for instance, a ``take_exptime(seconds=120)`` command, the
details of how a specific camera model is programmed to achieve that may be
very different. From the perspective of software at higher levels those
details are not important, all that is important is that all attached cameras
react appropriately to the ``take_exptime`` command.


While the Core Layer consists of one module per feature, the HAL implements a
Template Pattern [Gamma1993]_ wherein a base class provides an interface to
be used by higher levels and concrete classes are written for each specific
device type. For example, a base Mount class dictates an interface that
includes methods such as ``slew_to_home``, ``set_target_coordinates``, 
``slew_to_target``, ``park``, etc. The concrete implementation for the
iOptron mount then uses the Core Layer level RS-232 commands to issue the
specific serial commands needed to perform those functions. Likewise, a
Paramount ME II concrete implementation of the Mount class would use the Core
Layer interface to `TheSkyX <http://www.bisque.com/sc/pages/TheSkyX-Professional-Edition.aspx>`_
to implement those same methods. Thus, higher levels of the software can make
a call to ``mount.slew_to_target()`` and expect it to work regardless of the
particular mount type attached. 

Another advantage of this type of setup is that a concrete implementation of
a hardware simulator can be created to test higher-level software without
actually having physical devices attached, which is how much of the PANOPTES
testing framework is implemented [1]_.


Functional Layer
----------------

The Functional Layer is analogous to a traditional observatory: an 
Observatory has a location from which it operates, attached hardware which it 
uses to observe, a scheduler (a modified dispatch scheduler [Denny2004]_ in 
the case of PANOPTES) to select from the available target_list to form valid 
observations, etc.


The Observatory (i.e. the Functional Layer) is thus where most of the 
operations associated with taking observations actually happen. When the 
software is used interactively (as opposed to the usual automatic mode) it is 
with the Observatory that an individual would overwhelmingly interact.

The Functional Layer is also responsible for connecting to and initializing 
the attached hardware, specified by accompanying configuration files. The 
potential list of targets and the type of scheduler used are also loaded from 
a configuration file. The particular type of scheduler is agnostic to the 
Observatory, which simply calls ``scheduler.get_observation()`` such that the 
external scheduler can handle all the logic of choosing a target. In the 
figure listed above this is represented by the "Scheduler" and "Targets" that 
are input to the "Observatory."

Decision Layer
--------------

The Decision Layer is the highest level of the system and can be viewed as 
the "intelligence" layer. When using the software in interactive mode, the 
human user takes on the role of the Decision Layer while in automatic 
operations this is accomplished via an event-driven finite state machine 
(FSM). 

A state machine is a simple model of a system where that system can only 
exist in discrete conditions or modes. Those conditions or modes are called 
states. Typically states determine how the system reacts to input, either 
from a user or the environment. A state machine can exist solely in the 
software or the software can be representative of a physical model. For 
PANOPTES, the physical unit is the system and POCS models the condition of 
the hardware. The "finite" aspect refers to the fact that there are a limited 
and known number of states in which the system can exist.

Examples of PANOPTES states include: 

* ``sleeping``:     Occurs in daylight hours, the cameras are facing down, and themount is unresponsive to slew commands.
* ``observing``:    The cameras are exposing and the mount is tracking.
* ``scheduling``:   The mount is unparked, not slewing or tracking, it is dark, and the software is running through the scheduler.

PANOPTES states are named with verbs to represent the action the physical 
unit is currently performing.

POCS is designed to have a configurable state machine, with the highest level 
logic written in each state definition file. State definition files are meant 
to be simple as most of the details of the logic should exist in the 
functional layer. Students using POCS for educational purposes will most 
likely start with the state files. 

State machines are responsible for mapping inputs (e.g. ``get_ready``,
``schedule``, ``start_slewing``, etc.) to outputs, where the particular 
mapping depends on the current state [Lee2017]_. The mappings of input to 
output are governed by transition events [2]_.

State definitions and their transitions are defined external to POCS, 
allowing for multiple possible state machines that are agnostic to the layers 
below the Decision Layer. This external definition is similar to the 
"Scheduler" in the Functional Layer and is represented similarly in the 
figure above.

POCS is responsible for determining operational safety via a query of the 
weather station, determination of sun position, etc. The transition for each 
state has a set of conditions that must be satisfied in order for a 
successful transition to a new state to be accomplished and a requisite check 
for operational safety occurs before all transitions. If the system is 
determined to be unsafe the machine either transitions to the parking state 
or remains in the sleeping or ready state.

.. include:: pocs-alternatives.rst

.. [1] Writing hardware simulators, while helpful for testing purposes, can 
also add significant overhead to a project. For major projects such as the
LSST or TMT this is obviously a requirement. PANOPTES implements basic
hardware simulators for the mount and camera but full-scale hardware 
simulation of specific components has not yet been achieved.

.. [2] The Python FSM used by POCS is in fact called `transitions <https://github.com/tyarkoni/transitions>`_. 


.. [Elkady2012] Stuff
.. [Denny2004] Stuff
.. [Lee2017] Stuff
.. [Gamma1993] Stuff