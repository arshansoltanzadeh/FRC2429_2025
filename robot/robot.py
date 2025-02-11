#!/usr/bin/env python3

import typing
import wpilib
import commands2

from robotcontainer import RobotContainer
from subsystems.led import Led  # allows indexing of LED colors

if wpilib.RobotBase.isSimulation():
    wpilib.DriverStation.silenceJoystickConnectionWarning(True)

class MyRobot(commands2.TimedCommandRobot):
    """
    Our default robot class, pass it to wpilib.run

    Command v2 robots are encouraged to inherit from TimedCommandRobot, which
    has an implementation of robotPeriodic which runs the scheduler for you
    """

    autonomousCommand: typing.Optional[commands2.Command] = None

    def robotInit(self) -> None:
        """
        This function is run when the robot is first started up and should be used for any
        initialization code.
        """

        # Instantiate our RobotContainer.  This will perform all our button bindings, and put our
        # autonomous chooser on the dashboard.
        self.container = RobotContainer()

    def disabledInit(self) -> None:
        """This function is called once each time the robot enters Disabled mode."""
        self.disabled_counter = 0

    def disabledPeriodic(self) -> None:
        """This function is called periodically when disabled"""
        if self.disabled_counter % 100 == 0:
            if wpilib.DriverStation.isFMSAttached():
                alliance_color = wpilib.DriverStation.getAlliance()
                if alliance_color is not None:
                    if alliance_color == wpilib.DriverStation.Alliance.kRed:
                        self.container.led.set_indicator(Led.Indicator.kHOTBOW)
                    elif alliance_color == wpilib.DriverStation.Alliance.kBlue:
                        self.container.led.set_indicator(Led.Indicator.kCOOLBOW)
                    else:
                        self.container.led.set_indicator(Led.Indicator.kPOLKA)
            else:
                self.container.led.set_indicator(Led.Indicator.kRAINBOW)
            # print(f"Alliance: {wpilib.DriverStation.getAlliance()}, FMS Attached: {wpilib.DriverStation.isFMSAttached()}")
        self.disabled_counter += 1

    def autonomousInit(self) -> None:
        """This autonomous runs the autonomous command selected by your RobotContainer class."""

        self.container.set_start_time()  # putting this after the scheduler is bad

        self.autonomousCommand = self.container.get_autonomous_command()

        if self.autonomousCommand:
            self.autonomousCommand.schedule()

    def autonomousPeriodic(self) -> None:
        """This function is called periodically during autonomous"""

    def teleopInit(self) -> None:

        self.container.set_start_time()  # putting this after the scheduler is bad

        # This makes sure that the autonomous stops running when
        # teleop starts running. If you want the autonomous to
        # continue until interrupted by another command, remove
        # this line or comment it out.
        if self.autonomousCommand:
            self.autonomousCommand.cancel()

    def teleopPeriodic(self) -> None:
        """This function is called periodically during operator control"""

    def testInit(self) -> None:
        # Cancels all running commands at the start of test mode
        commands2.CommandScheduler.getInstance().cancelAll()

    def robotPeriodic(self) -> None:
        wpilib.SmartDashboard.putString("robot mode", self.container.get_robot_mode().value)
        return super().robotPeriodic()


if __name__ == "__main__":
    wpilib.run(MyRobot)
