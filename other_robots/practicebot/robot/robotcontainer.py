from dataclasses import field
import math
import time, enum
from pathplannerlib.pathfinders import LocalADStar
from pathplannerlib.pathfinding import Pathfinding
from pathplannerlib.path import PathConstraints
import wpilib
import commands2
from commands2.button import Trigger
from wpimath.geometry import Pose2d
from commands.drive_by_joystick_swerve import DriveByJoystickSwerve
from commands.reset_gyro import ResetGyro
from commands.reset_field_centric import ResetFieldCentric
from commands.drive_by_apriltag_swerve import DriveByApriltagSwerve
import constants

from pathplannerlib.auto import AutoBuilder, PathPlannerAuto
from pathplannerlib.path import PathPlannerPath

from subsystems.lower_crank import LowerCrank

from commands.move_lower_arm_by_network_tables import MoveLowerArmByNetworkTables
from subsystems.swerve import Swerve

wpilib.DriverStation.silenceJoystickConnectionWarning(True)

class RobotContainer:
    """
    This class is where the bulk of the robot should be declared. Since Command-based is a
    "declarative" paradigm, very little robot logic should actually be handled in the :class:`.Robot`
    periodic methods (other than the scheduler calls). Instead, the structure of the robot (including
    subsystems, commands, and button mappings) should be declared here.
    """

    def __init__(self) -> None:

        self.start_time = time.time()

        # The robot's subsystems
        # self.lower_crank = LowerCrank(container=self) # I don't want to test without a sim yet
        self.swerve = Swerve()

        self.configure_joysticks()
        self.bind_driver_buttons()
        self.swerve.setDefaultCommand(DriveByJoystickSwerve(
            container=self,
            swerve=self.swerve,
            controller=self.driver_command_controller,
            rate_limited=constants.k_swerve_rate_limited
        ))

        if not constants.k_swerve_only:
            self.bind_operator_buttons()
            self.bind_keyboard_buttons()

        # self.configure_swerve_bindings()
        
        self.initialize_dashboard()

        Pathfinding.setPathfinder(LocalADStar())

        # swerve driving

        # initialize the turret
        # commands2.ScheduleCommand(TurretInitialize(container=self, turret=self.turret, samples=50)).initialize()
        # testing

    def set_start_time(self):  # call in teleopInit and autonomousInit in the robot
        self.start_time = time.time()

    def get_enabled_time(self):  # call when we want to know the start/elapsed time for status and debug messages
        return time.time() - self.start_time

    def configure_joysticks(self):
        """
        Use this method to define your button->command mappings. Buttons can be created by
        instantiating a :GenericHID or one of its subclasses (Joystick or XboxController),
        and then passing it to a JoystickButton.
        """
        # The driver's controller
        self.driver_command_controller = commands2.button.CommandXboxController(constants.k_driver_controller_port)
        self.triggerA = self.driver_command_controller.a()
        self.triggerB = self.driver_command_controller.b()
        self.triggerX = self.driver_command_controller.x()
        self.triggerY = self.driver_command_controller.y()
        self.triggerLB = self.driver_command_controller.leftBumper()
        self.triggerRB = self.driver_command_controller.rightBumper()
        self.triggerBack = self.driver_command_controller.back()
        self.triggerStart = self.driver_command_controller.start()
        self.triggerUp = self.driver_command_controller.povUp()
        self.triggerDown = self.driver_command_controller.povDown()
        self.triggerLeft = self.driver_command_controller.povLeft()
        self.triggerRight = self.driver_command_controller.povRight()

        self.copilot_controller = commands2.button.CommandXboxController(1)
        self.copilot_controller = commands2.button.CommandXboxController(1) 

        # co-pilot controller
        """
        self.co_driver_controller = wpilib.XboxController(constants.k_co_driver_controller_port)
        self.co_buttonA = JoystickButton(self.co_driver_controller, 1)
        self.co_buttonB = JoystickButton(self.co_driver_controller, 2)
        self.co_buttonX = JoystickButton(self.co_driver_controller, 3)
        self.co_buttonY = JoystickButton(self.co_driver_controller, 4)
        self.co_buttonLB = JoystickButton(self.co_driver_controller, 5)
        self.co_buttonRB = JoystickButton(self.co_driver_controller, 6)
        self.co_buttonBack = JoystickButton(self.co_driver_controller, 7)
        self.co_buttonStart = JoystickButton(self.co_driver_controller, 8)
        self.co_buttonUp = POVButton(self.co_driver_controller, 0)
        self.co_buttonDown = POVButton(self.co_driver_controller, 180)
        self.co_buttonLeft = POVButton(self.co_driver_controller, 270)
        self.co_buttonRight = POVButton(self.co_driver_controller, 90)
        self.co_buttonLeftAxis = AxisButton(self.co_driver_controller, 2)
        self.co_buttonRightAxis = AxisButton(self.co_driver_controller, 3)
        """

    def initialize_dashboard(self):
        # wpilib.SmartDashboard.putData(MoveLowerArmByNetworkTables(container=self, crank=self.lower_crank))
        # lots of putdatas for testing on the dash
        pass

    def bind_driver_buttons(self):
        self.triggerX.whileTrue(AutoBuilder.followPath(PathPlannerPath.fromPathFile("test path")))
        self.triggerX.onTrue(commands2.PrintCommand("starting pathplanner auto"))
        self.triggerX.onFalse(commands2.PrintCommand("ending pathplanner auto"))

        pathfinding_constraints = PathConstraints(
                maxVelocityMps=0.5,
                maxAccelerationMpsSq=3,
                maxAngularVelocityRps=math.radians(90),
                maxAngularAccelerationRpsSq=math.degrees(720),
                nominalVoltage=12
        )

        self.triggerA.whileTrue(
                AutoBuilder.pathfindToPoseFlipped(
                    pose=Pose2d(15, 4, 0),
                    constraints=pathfinding_constraints
                )
        )

        # self.triggerX.whileTrue(PathPlannerAuto("test"))
        self.triggerB.onTrue(ResetFieldCentric(container=self, swerve=self.swerve, angle=0))

        self.triggerLB.whileTrue(DriveByApriltagSwerve(container=self, swerve=self.swerve, id=6, target_angle=0))
        pass

    def bind_operator_buttons(self):
        pass

    def bind_keyboard_buttons(self):
        # for convenience, and just in case a controller goes down
        pass

    def get_autonomous_command(self):
        return commands2.InstantCommand(lambda: print(f"starting auto from alliance station {wpilib.DriverStation.getAlliance()}")).andThen(AutoBuilder.followPath(PathPlannerPath.fromPathFile("test path")))
        # return self.autonomous_chooser.getSelected()
