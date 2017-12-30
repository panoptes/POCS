from datetime import datetime


class PID:

    '''
    Pseudocode from Wikipedia:

    previous_error = 0
    integral = 0
    start:
      error = setpoint - measured_value
      integral = integral + error*dt
      derivative = (error - previous_error)/dt
      output = Kp*error + Ki*integral + Kd*derivative
      previous_error = error
      wait(dt)
      goto start
    '''

    def __init__(self, Kp=2., Ki=0., Kd=1.,
                 set_point=None, output_limits=None,
                 max_age=None):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.Pval = None
        self.Ival = 0.0
        self.Dval = 0.0
        self.previous_error = None
        self.set_point = None
        if set_point:
            self.set_point = set_point
        self.output_limits = output_limits
        self.history = []
        self.max_age = max_age
        self.last_recalc_time = None
        self.last_interval = 0.

    def recalculate(self, value, interval=None,
                    reset_integral=False,
                    new_set_point=None):
        if new_set_point:
            self.set_point = float(new_set_point)
        if reset_integral:
            self.history = []
        if not interval:
            if self.last_recalc_time:
                now = datetime.utcnow()
                interval = (now - self.last_recalc_time).total_seconds()
            else:
                interval = 0.0

        # Pval
        error = self.set_point - value
        self.Pval = error

        # Ival
        for entry in self.history:
            entry[2] += interval
        for entry in self.history:
            if self.max_age:
                if entry[2] > self.max_age:
                    self.history.remove(entry)
        self.history.append([error, interval, 0])
        new_Ival = 0
        for entry in self.history:
            new_Ival += entry[0] * entry[1]
        self.Ival = new_Ival

        # Dval
        if self.previous_error:
            self.Dval = (error - self.previous_error) / interval

        # Output
        output = self.Kp * error + self.Ki * self.Ival + self.Kd * self.Dval
        if self.output_limits:
            if output > max(self.output_limits):
                output = max(self.output_limits)
            if output < min(self.output_limits):
                output = min(self.output_limits)
        self.previous_error = error

        self.last_recalc_time = datetime.utcnow()
        self.last_interval = interval

        return output

    def tune(self, Kp=None, Ki=None, Kd=None):
        if Kp:
            self.Kp = Kp
        if Ki:
            self.Ki = Ki
        if Kd:
            self.Kd = Kd
