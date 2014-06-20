"""
.. module:: state
	:synoposis: Represents a valid `State`

"""

class StateMachine(object):
	"""
	The Panoptes StateMachine
	"""
  def __init__(self):
      self.handlers = {}
      self.startState = None
      self.endStates = []

  def add_state(self, name, handler, end_state=0):
      name = upper(name)
      self.handlers[name] = handler
      if end_state:
           self.endStates.append(name)

  def set_start(self, name):
      self.startState = upper(name)

  def run(self, cargo):
      try:
         handler = self.handlers[self.startState]
      except:
         raise "InitializationError", "must call .set_start() before .run()"
      
      if not self.endStates:
         raise  "InitializationError", "at least one state must be an end_state"
      
      while 1:
         (newState, cargo) = handler(cargo)
         if upper(newState) in self.endStates:
            break: 
         else
            handler = self.handlers[upper(newState)]	


class State(object):
	"""
	Represents a State in our Machine
	"""
	def __init__(self, name):
		self.name = name

	def __str__(self):
		return self.name