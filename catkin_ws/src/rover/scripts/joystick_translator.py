#!/usr/bin/env python

# Copyright 2017 Open Source Robotics Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import rospy
from rover.msg import Control
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist

from config import Config

#######################################
## Logitech G920 with Pedal and Shift

# Steering
STEERING_AXIS = 0   # left 1 --> center 0 --> right -1

# Speed control
BUTTON_A = 0        # speed step down
BUTTON_B = 1        # steering step up
BUTTON_X = 2        # steering step down
BUTTON_Y = 3        # speed step up


# Throttle and Brake
THROTTLE_AXIS = 1   # release -1 --> press 1
BRAKE_AXIS = 2      # release -1 --> press 1
BRAKE_POINT = -0.9  # consider brake is applied if value is greater than this.

# Gear shift
# to be neutral, bothe SHIFT_FORWARD & SHIFT_REVERSE must be 0
SHIFT_FORWARD = 14     # forward 1
SHIFT_REVERSE = 15     # reverse 1

# Max speed and steering factor
MAX_THROTTLE_FACTOR = 20
MAX_STEERING_FACTOR = 20
# Default speed and steering factor : 
INIT_THROTTLE_FACTOR = Config.config['scale_factor_throttle']
INIT_STERRING_FACTOR = Config.config['scale_factor_steering']

# Small value
SMALL_VALUE = 0.0001

class Translator:
    def __init__(self):
        self.sub = rospy.Subscriber("joy", Joy, self.callback)
        self.pub = rospy.Publisher('rover', Control, queue_size=20)
        self.pub4mavros = rospy.Publisher(Config.config['mavros_cmd_vel_topic'], Twist, queue_size=20)

        self.last_published_time = rospy.get_rostime()
        self.last_published = None
        self.timer = rospy.Timer(rospy.Duration(1./20.), self.timer_callback)

        self.throttle_factor = INIT_THROTTLE_FACTOR
        self.steering_factor = INIT_STERRING_FACTOR
        
    def timer_callback(self, event):
        if self.last_published and self.last_published_time < rospy.get_rostime() + rospy.Duration(1.0/20.):
            self.callback(self.last_published)

    def callback(self, message):
        rospy.logdebug("joy_translater received axes %s",message.axes)
        command = Control()
        command.header = message.header

        # Throttle speed control
        if message.buttons[BUTTON_Y] == 1:
            self.throttle_factor = self.throttle_factor + 1 if self.throttle_factor < MAX_THROTTLE_FACTOR else MAX_THROTTLE_FACTOR
        if message.buttons[BUTTON_A] == 1:
            self.throttle_factor = self.throttle_factor - 1 if self.throttle_factor > 1 else 1

        # Steering speed control
        if message.buttons[BUTTON_B] == 1:
            self.steering_factor = self.steering_factor + 1 if self.steering_factor < MAX_STEERING_FACTOR else MAX_STEERING_FACTOR
        if message.buttons[BUTTON_X] == 1:
            self.steering_factor = self.sterring_factor - 1 if self.steering_factor > 1 else 1

        if message.axes[BRAKE_AXIS] > BRAKE_POINT:
		    command.brake = 1.0
        
        # Note: init value of axes are all zeros
        # --> problem with -1 to 1 range values like brake
        if message.axes[BRAKE_AXIS] > -1*SMALL_VALUE and message.axes[BRAKE_AXIS] < SMALL_VALUE:
		    command.brake = 0.0

        if message.axes[THROTTLE_AXIS] >= 0:
            command.throttle = message.axes[THROTTLE_AXIS]
            command.brake = 0.0
        else:
            command.throttle = 0.0
        
        if message.buttons[SHIFT_FORWARD] == 1:
            command.shift_gears = Control.FORWARD
        elif message.buttons[SHIFT_REVERSE] == 1:
            command.shift_gears = Control.REVERSE
        elif message.buttons[SHIFT_FORWARD] == 0 and message.buttons[SHIFT_REVERSE] == 0 :
            command.shift_gears = Control.NEUTRAL
        else:
            command.shift_gears = Control.NO_COMMAND

        command.steer = message.axes[STEERING_AXIS]

        # scale throttle and steering 
        command.throttle = command.throttle*self.throttle_factor
        command.steer = command.steer*self.steering_factor

        command4mavros = Twist()
        if command.shift_gears == Control.FORWARD:
            command4mavros.linear.x = command.throttle
            command4mavros.linear.y = command.steer
        #elif command.shift_gears == Control.REVERSE:
        #    command4mavros.linear.x = -command.throttle
        #    command4mavros.linear.y = command.steer
        else:
            command4mavros.linear.x = 0
            command4mavros.linear.y = 0

        self.pub4mavros.publish(command4mavros)
        
        self.last_published = message
        self.pub.publish(command)

if __name__ == '__main__':
    rospy.init_node('joystick_translator')
    t = Translator()
    rospy.spin()
