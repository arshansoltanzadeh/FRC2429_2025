from enum import Enum
import math
from os import confstr
from threading import Condition
import time
from commands2.printcommand import PrintCommand
from pathplannerlib.commands import PathfindingCommand
import rev
import wpilib
import commands2
from wpimath import controller
from wpimath.geometry import Pose2d
from wpimath.units import degreesToRadians
from ntcore import NetworkTableInstance

import constants

from pathplannerlib.pathfinders import LocalADStar
from pathplannerlib.pathfinding import Pathfinding
from pathplannerlib.path import PathConstraints
from pathplannerlib.auto import AutoBuilder, NamedCommands
from pathplannerlib.path import PathPlannerPath

from commands.drive_by_distance_swerve import DriveByVelocitySwerve
from commands.go_to_coral_station import GoToCoralStation
from commands.go_to_stow import GoToStow
from commands.go_to_reef_position import GoToReefPosition
from commands.score import Score
from commands.sequential_scoring import SequentialScoring
from commands.drive_by_apriltag_swerve import DriveByApriltagSwerve
from commands.drive_by_joystick_swerve import DriveByJoystickSwerve
from commands.move_elevator import MoveElevator
from commands.move_pivot import MovePivot
from commands.move_wrist import MoveWrist
from commands.run_intake import RunIntake
from commands.set_leds import SetLEDs
from commands.reset_field_centric import ResetFieldCentric

from subsystems import swerve_constants
from subsystems.robot_state import RobotState
from subsystems.swerve import Swerve
from subsystems.elevator import Elevator
from subsystems.pivot import Pivot
from subsystems.intake import Intake
from subsystems.led import Led
from subsystems.wrist import Wrist
from subsystems.climber import Climber
from subsystems.vision import Vision

from autonomous.leave_then_score_1 import LeaveThenScore
from commands.drive_by_joystick_swerve import DriveByJoystickSwerve
from commands.move_elevator import MoveElevator
from commands.move_pivot import MovePivot
from commands.move_wrist import MoveWrist
from commands.run_intake import RunIntake
from commands.set_leds import SetLEDs
from commands.move_climber import MoveClimber

from commands.go_to_position import GoToPosition
from commands.follow_trajectory import FollowTrajectory
from commands.intake_sequence import IntakeSequence
from commands.reset_field_centric import ResetFieldCentric
from commands.move_wrist_swap import MoveWristSwap

from trajectory import CustomTrajectory
# from commands.score import Score
# from commands.drive_by_joystick_subsystem import DriveByJoystickSubsystem

class RobotContainer:
    """
    This class is where the bulk of the robot should be declared. Since Command-based is a
    "declarative" paradigm, very little robot logic should actually be handled in the :class:`.Robot`
    periodic methods (other than the scheduler calls). Instead, the structure of the robot (including
    subsystems, commands, and button mappings) should be declared here.
    """

    # set robot modes
    class RobotMode(Enum):  # use this instead of intake results directly because we want to be able to override intake results for testing and emergencies
        EMPTY = "e"
        HAS_CORAL = "c"
        HAS_ALGAE = "a"

    def set_robot_mode(self, mode: RobotMode):  # because we can't assign inside lambdas
        self.robot_mode = mode

    def get_robot_mode(self) -> RobotMode:
        return self.robot_mode
    
    def is_robot_mode(self, mode: RobotMode) -> bool:
        return self.robot_mode == mode

    # set scoring mode

    def __init__(self) -> None:

        self.start_time = time.time()

        # The robot's subsystems
        # self.lower_crank = LowerCrank(container=self) # I don't want to test without a sim yet
        self.swerve = Swerve()
        self.elevator = Elevator()
        self.pivot = Pivot()
        self.wrist = Wrist(self.pivot, self.elevator)
        self.climber = Climber()
        self.intake = Intake()
        self.vision = Vision()
        self.robot_state = RobotState(self)  # currently has a callback that LED can register, but
        self.led = Led(self)  # may want LED last because it may want to know about other systems

        self.configure_joysticks()
        self.bind_driver_buttons()


        self.swerve.setDefaultCommand(DriveByJoystickSwerve(
            container=self,
            swerve=self.swerve,
            controller=self.driver_command_controller,
            # field_oriented=False,
            rate_limited=constants.k_swerve_rate_limited
        ))

        if not constants.k_swerve_only:
            self.configure_codriver_joystick()
            self.bind_codriver_buttons()
            self.bind_keyboard_buttons()
            if constants.k_use_bbox:
                self.bind_button_box()

        self.register_commands()

        self.initialize_dashboard()

        Pathfinding.setPathfinder(LocalADStar())

        self.robot_mode = self.RobotMode.EMPTY

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
        self.trigger_L_trigger = self.driver_command_controller.leftTrigger(0.5)
        self.triggerBack = self.driver_command_controller.back()
        self.triggerStart = self.driver_command_controller.start()
        self.triggerUp = self.driver_command_controller.povUp()
        self.triggerDown = self.driver_command_controller.povDown()
        self.triggerLeft = self.driver_command_controller.povLeft()
        self.triggerRight = self.driver_command_controller.povRight()

        self.copilot_controller = commands2.button.CommandXboxController(1)
        self.copilot_controller = commands2.button.CommandXboxController(1) 

    def configure_codriver_joystick(self):

        print("configuring codriver joystick")

        def stick_between_degree_angles(angle_a, angle_b, stick_x, stick_y) -> bool:
            """
            returns whether the stick is between angle a (lower limit) and angle b (higher limit).
            0 <= a < b <= 360. Returns true if stick angle = a, but false if stick angle = b.
            cannot handle wraparound for now (how is there no method for this)
            """
            angle_a = math.radians(angle_a)
            angle_b = math.radians(angle_b)

            stick_angle = math.atan2(stick_x, stick_y)
            if stick_angle < 0:
                stick_angle = math.tau + stick_angle  # compensate because atan returns -180 to 180 but we want 0 to 360

            return (angle_a <= stick_angle and stick_angle < angle_b)

        self.co_pilot_command_controller = commands2.button.CommandXboxController(constants.k_co_driver_controller_port)  # 2024 way
        
        self.co_trigger_right_stick_between_0_60_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(0, 60,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_right_stick_between_60_120_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(60, 120,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_right_stick_between_120_180_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(120, 180,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_right_stick_between_180_240_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(180, 240,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_right_stick_between_240_300_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(240, 300,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_right_stick_between_300_360_deg = commands2.button.Trigger(lambda: stick_between_degree_angles(300, 360,
                                                                            self.co_pilot_command_controller.getRightX(),
                                                                            self.co_pilot_command_controller.getRightY()))

        self.co_trigger_a = self.co_pilot_command_controller.a()  # 2024 way
        self.co_trigger_b = self.co_pilot_command_controller.b()
        self.co_trigger_y = self.co_pilot_command_controller.y()
        self.co_trigger_x = self.co_pilot_command_controller.x()
        self.co_trigger_rb = self.co_pilot_command_controller.rightBumper()
        self.co_trigger_lb = self.co_pilot_command_controller.leftBumper()
        self.co_trigger_r = self.co_pilot_command_controller.povRight()
        self.co_trigger_l = self.co_pilot_command_controller.povLeft()
        self.co_trigger_u = self.co_pilot_command_controller.povUp()
        self.co_trigger_d = self.co_pilot_command_controller.povDown()

        self.co_trigger_l_trigger = self.co_pilot_command_controller.leftTrigger(0.2)
        self.co_trigger_r_trigger = self.co_pilot_command_controller.rightTrigger(0.2)
        self.co_trigger_start = self.co_pilot_command_controller.start()
        self.co_trigger_back = self.co_pilot_command_controller.back()

        self.co_trigger_r_stick_positive_x = self.co_pilot_command_controller.axisGreaterThan(4, 0.5)
        self.co_trigger_r_stick_negative_x = self.co_pilot_command_controller.axisLessThan(4, -0.5)
        self.co_trigger_r_stick_positive_y = self.co_pilot_command_controller.axisGreaterThan(5, 0.5)
        self.co_trigger_r_stick_negative_y = self.co_pilot_command_controller.axisLessThan(5, -0.5)

    def initialize_dashboard(self):
        # wpilib.SmartDashboard.putData(MoveLowerArmByNetworkTables(container=self, crank=self.lower_crank))
        # lots of putdatas for testing on the dash
        # COMMANDS FOR GUI (ROBOT DEBUGGING) - 20250224 CJH
        self.led_mode_chooser = wpilib.SendableChooser()
        [self.led_mode_chooser.addOption(key, value) for key, value in self.led.modes_dict.items()]  # add all the indicators
        self.led_mode_chooser.onChange(listener=lambda selected_value: commands2.CommandScheduler.getInstance().schedule(
            SetLEDs(container=self, led=self.led, mode=selected_value)))
        wpilib.SmartDashboard.putData('LED Mode', self.led_mode_chooser)
        self.led_indicator_chooser = wpilib.SendableChooser()
        [self.led_indicator_chooser.addOption(key, value) for key, value in self.led.indicators_dict.items()]  # add all the indicators
        self.led_indicator_chooser.onChange(listener=lambda selected_value: commands2.CommandScheduler.getInstance().schedule(
            SetLEDs(container=self, led=self.led, indicator=selected_value)))
        wpilib.SmartDashboard.putData('LED Indicator', self.led_indicator_chooser)

        wpilib.SmartDashboard.putData('SetSuccess', SetLEDs(container=self, led=self.led, indicator=Led.Indicator.kSUCCESS))
        wpilib.SmartDashboard.putData('MoveElevator', MoveElevator(container=self, elevator=self.elevator, mode='absolute'))
        wpilib.SmartDashboard.putData('MovePivot', MovePivot(container=self, pivot=self.pivot, mode='absolute'))
        wpilib.SmartDashboard.putData('SequentialScore', SequentialScoring(container=self))
        wpilib.SmartDashboard.putData('move wrist to -90 deg', MoveWrist(container=self, radians=math.radians(-90), timeout=4))
        wpilib.SmartDashboard.putData('move wrist to 0 deg', MoveWrist(container=self, radians=math.radians(0), timeout=4))
        wpilib.SmartDashboard.putData('move wrist to 90 deg', MoveWrist(container=self, radians=math.radians(90), timeout=4))

        waypoints = {
            0: {'elevator': 0.21, 'pivot': 90, 'wrist': 0, 'intake': 0},  # start 
            1: {'elevator': 1.1, 'pivot': 90, 'wrist': 0, 'intake': 0},  # get to scoring wrist
            2: {'elevator': 0.8, 'pivot': 50, 'wrist': 90, 'intake': 3},  # return home with wrist safe
        }

        # waypoints = {
        #     0: {'elevator': 0.21, 'pivot': 90, 'wrist': 0, 'intake': 2},  # start
        #     0.25: {'elevator': 0.3, 'pivot': 90, 'wrist': 0, 'intake': 2},  # start
        #     0.5: {'elevator': 0.5, 'pivot': 70, 'wrist': 0, 'intake': 2},  # get to safe wrist
        #     1: {'elevator': 1.2, 'pivot': 50, 'wrist': 90, 'intake': 2},  # get to scoring wrist while raising elevator
        #     1.5: {'elevator': 1.17, 'pivot': 40, 'wrist': 90, 'intake': -3},  # move pivot while scoring
        #     2.5: {'elevator': 0.2, 'pivot': 70, 'wrist': 0, 'intake': 0},  # return home with wrist safe
        #     3.0: {'elevator': 0.2, 'pivot': 90, 'wrist': 0, 'intake': 0},  # come down to bottom
        # }
        #
        l3_trajectory = CustomTrajectory(waypoints, 2)
        wpilib.SmartDashboard.putData('l3 trajectory', FollowTrajectory(container=self, current_trajectory=l3_trajectory, wait_to_finish=True))
        wpilib.SmartDashboard.putData('MoveElevatorTop', MoveElevator(container=self, elevator=self.elevator, mode='specified', height=constants.ElevatorConstants.k_max_height-0.005 ))
        wpilib.SmartDashboard.putData('MoveElevatorUp', MoveElevator(container=self, elevator=self.elevator, mode='incremental', height=0.1 ))
        wpilib.SmartDashboard.putData('MoveElevatorDown', MoveElevator(container=self, elevator=self.elevator, mode='incremental', height=-0.1))
        wpilib.SmartDashboard.putData('MovePivotUp', MovePivot(container=self, pivot=self.pivot, mode='incremental', angle=10))
        wpilib.SmartDashboard.putData('MovePivotDown', MovePivot(container=self, pivot=self.pivot, mode='incremental', angle=-10))
        wpilib.SmartDashboard.putData('MoveWristUp', MoveWrist(container=self, incremental=True, radians=degreesToRadians(10), timeout=0.2))
        wpilib.SmartDashboard.putData('MoveWristDown', MoveWrist(container=self, incremental=True, radians=degreesToRadians(-10), timeout=0.2))
        wpilib.SmartDashboard.putData('IntakeOn', RunIntake(container=self, intake=self.intake, value=6, stop_on_end=False))
        wpilib.SmartDashboard.putData('IntakeOff', RunIntake(container=self, intake=self.intake, value=0, stop_on_end=False))
        wpilib.SmartDashboard.putData('IntakeReverse', RunIntake(container=self, intake=self.intake, value=-6, stop_on_end=False))
        wpilib.SmartDashboard.putData('GoToStow', GoToStow(container=self))


        wpilib.SmartDashboard.putData('Move climber up', MoveClimber(self, self.climber, 'incremental', math.radians(5)))
        wpilib.SmartDashboard.putData('Move climber down', MoveClimber(self, self.climber, 'incremental', math.radians(-5)))

        # quick way to test all scoring positions from dashboard
        self.score_test_chooser = wpilib.SendableChooser()
        [self.score_test_chooser.addOption(key, value) for key, value in self.robot_state.targets_dict.items()]  # add all the indicators
        self.score_test_chooser.onChange(
            listener=lambda selected_value: commands2.CommandScheduler.getInstance().schedule(
                commands2.cmd.runOnce(lambda: self.robot_state.set_target(target=selected_value))))
        wpilib.SmartDashboard.putData('RobotScoringMode', self.score_test_chooser)

    def bind_driver_buttons(self):

        self.triggerB.onTrue(ResetFieldCentric(container=self, swerve=self.swerve, angle=0))

        self.triggerX.whileTrue(AutoBuilder.buildAuto("testt"))
        self.triggerX.onTrue(commands2.PrintCommand("starting pathplanner auto"))
        self.triggerX.onFalse(commands2.PrintCommand("ending pathplanner auto"))

        # this is for field centric
        #self.triggerLB.whileTrue(DriveByApriltagSwerve(container=self, swerve=self.swerve, target_heading=0))

        # button A for intake
        # left trigger for outtake

        self.triggerA.whileTrue(GoToCoralStation(container=self).andThen(
            RunIntake(container=self, intake=self.intake, value=-3, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False)))

        self.triggerA.onFalse(RunIntake(container=self, intake=self.intake, value=0, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False).andThen(
            GoToStow(container=self)))

        self.trigger_L_trigger.onTrue(
                GoToReefPosition(container=self, level=2, wrist_setpoint_decider=math.radians(90)).andThen(
                    Score(container=self)
                    )
                )
        

    def bind_codriver_buttons(self):

        print("Binding codriver buttons")

        self.co_trigger_a()

        #  leo's way: make a command that goes to any position. specify the position in command construction.
            # => a command object for each position
        # cory's way: make a command that goes to any position. specify the position in another subsystem that this command looks at.
            # => one command object and one subsystem
            # now we need a command object for each position to tell that subsystem where to go
            # but we can change setpoints outside of construct-time

        # self.co_trigger_a.whileTrue(SequentialScoring(container=self))

        self.co_trigger_a.onTrue(commands2.PrintCommand("we don't hvae a good l1 position yet"))
        
        self.co_trigger_b.onTrue(GoToReefPosition(container=self, level=2, wrist_setpoint_decider=self.robot_state))

        self.co_trigger_x.onTrue(GoToReefPosition(container=self, level=3, wrist_setpoint_decider=self.robot_state))

        self.co_trigger_y.onTrue(GoToReefPosition(container=self, level=4, wrist_setpoint_decider=self.robot_state))

        # trigger on true: go to the position, start intake
        # trigger on false: go to stow, stop intake

        self.co_trigger_d.or_(self.co_trigger_l).whileTrue(GoToCoralStation(container=self).andThen(
            RunIntake(container=self, intake=self.intake, value=constants.IntakeConstants.k_coral_intaking_voltage, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False)))

        self.co_trigger_d.or_(self.co_trigger_l).onFalse(RunIntake(container=self, intake=self.intake, value=0, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False).andThen(
            GoToStow(container=self)))

        self.co_trigger_u.or_(self.co_trigger_r).whileTrue(GoToStow(container=self))


        self.co_trigger_lb.whileTrue(RunIntake(container=self, intake=self.intake, value=-6, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=True))
        
        self.co_trigger_rb.onTrue(Score(container=self))

        self.co_trigger_r_stick_negative_y.onTrue(MoveWrist(container=self, radians=math.radians(0), timeout=4))

        self.co_trigger_r_stick_positive_x.onTrue(MoveWristSwap(self, self.wrist))  # this seems backwards but is not because y-axis is inverted

        self.co_trigger_r_stick_negative_x.onTrue(MoveWristSwap(self, self.wrist))

        self.co_trigger_r_trigger.whileTrue(MoveClimber(self, self.climber, ""))

        # self.co_trigger_a.onTrue(MoveClimber(container=self, climber=self.climber, mode='climbing', wait_to_finish=True))

        # self.co_trigger_a.onTrue( # when trigger A is pressed, if we have coral, go to l1; else if we have algae, go to processor; else go to ground
        #         commands2.ConditionalCommand(
        #             onTrue=GoToPosition(container=self, position="l1"),
        #
        #             onFalse=commands2.ConditionalCommand(
        #                 onTrue=GoToPosition(container=self, position="processor"),
        #                 onFalse=IntakeSequence(container=self, position="ground"),
        #                 condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_ALGAE
        #             ),
        #
        #             condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_CORAL
        #         )
        # )
        #
        # self.co_trigger_b.onTrue(
        #         commands2.ConditionalCommand(
        #             onTrue=GoToPosition(container=self, position="l2"),
        #             onFalse=IntakeSequence(container=self, position="ground"), # can make either a or b into a different position if needed for algae and coral
        #             condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_CORAL
        #         )
        # )
        #
        # self.co_trigger_x.onTrue(
        #         commands2.ConditionalCommand(
        #             onTrue=GoToPosition(container=self, position="l3"),
        #             onFalse=IntakeSequence(container=self, position="algae low"),
        #             condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_CORAL
        #         )
        # )
        #
        # self.co_trigger_y.onTrue( # when trigger Y is pressed, if we have coral, go to l4; else if we have algae, go to net; else go to intake algae high
        #         commands2.ConditionalCommand(
        #             onTrue=GoToPosition(container=self, position="l4"),
        #
        #             onFalse=commands2.ConditionalCommand(
        #                 onTrue=GoToPosition(container=self, position="barge"),
        #                 onFalse=IntakeSequence(container=self, position="algae high"),
        #
        #                 condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_ALGAE
        #             ),
        #
        #             condition=lambda: self.get_robot_mode() == self.RobotMode.HAS_CORAL
        #         )
        # )
        #
        # self.co_trigger_lb.onTrue(commands2.PrintCommand("** Setting robot mode to empty **").andThen(commands2.InstantCommand(lambda: self.set_robot_mode(self.RobotMode.EMPTY))))
        #
        # self.co_trigger_rb.onTrue(Score(container=self))
        # self.co_trigger_rb.whileTrue(DriveByJoystickSubsystem(container=self, controller=self.co_pilot_command_controller, subsystem=self.intake, duty_cycle_coef=0.01))
        #
        # self.co_trigger_r_trigger.onTrue(commands2.PrintCommand("** Setting robot mode to has algae **").andThen(commands2.InstantCommand(lambda: self.set_robot_mode(self.RobotMode.HAS_ALGAE))))
        #
        # self.co_trigger_u.or_(self.co_trigger_r).onTrue(commands2.PrintCommand("** Setting robot mode to has coral **").andThen(commands2.InstantCommand(lambda: self.set_robot_mode(self.RobotMode.HAS_CORAL))))

        # self.co_trigger_d.or_(self.co_trigger_l).onTrue(IntakeSequence(container=self, position="coral station"))

    def bind_keyboard_buttons(self):
        # for convenience, and just in case a controller goes down

        # a, b, c ... k, l: reserved for driving to respective positions
        # w: wrist go left (korean left is wen chok, also position on the keyboard)
        # o: wrist go right (korean right is orin chok, also position on the keyboard)
        # see https://digitalwerk.gitlab.io/solutions/adtf_content/adtf_base/adtf_core/page_qt_key_event_runner.html for the codes for each key
        

        self.keys_pressed_entry = NetworkTableInstance.getDefault().getEntry("SmartDashboard/keys_pressed")  # for operator control via keyboard

        self.keyboard_trigger_p = commands2.button.Trigger(lambda: 80 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)

        self.keyboard_trigger_1 = commands2.button.Trigger(lambda: 49 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)
        self.keyboard_trigger_2 = commands2.button.Trigger(lambda: 50 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)
        self.keyboard_trigger_3 = commands2.button.Trigger(lambda: 51 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)
        self.keyboard_trigger_4 = commands2.button.Trigger(lambda: 52 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)

        self.keyboard_trigger_s = commands2.button.Trigger(lambda: 83 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)
        self.keyboard_trigger_t = commands2.button.Trigger(lambda: 84 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)

        self.keyboard_trigger_v = commands2.button.Trigger(lambda: 86 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)

        self.keyboard_trigger_w = commands2.button.Trigger(lambda: 87 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)
        self.keyboard_trigger_o = commands2.button.Trigger(lambda: 79 in self.keys_pressed_entry.getIntegerArray([])).debounce(0.06)

        # p: place (score)
        self.keyboard_trigger_p.onTrue(GoToStow(self))

        self.keyboard_trigger_1.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_target(RobotState.Target.L1)).ignoringDisable(True))
        self.keyboard_trigger_2.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_target(RobotState.Target.L2)).ignoringDisable(True).andThen(GoToReefPosition(self, 2, self.robot_state)))
        self.keyboard_trigger_3.onTrue(commands2.InstantCommand(lambda: self.robot_state.set_target(RobotState.Target.L3)).ignoringDisable(True).andThen(GoToReefPosition(self, 3, self.robot_state)))
        self.keyboard_trigger_4.onTrue(commands2.InstantCommand(lambda: self.robot_state.set_target(RobotState.Target.L4)).ignoringDisable(True).andThen(GoToReefPosition(self, 4, self.robot_state)))

        self.keyboard_trigger_s.onTrue(Score(self))

        # t: human player (mnemonic: celeste Tarula, sean Toda, Take a piece)
        self.keyboard_trigger_t.whileTrue(GoToCoralStation(container=self).andThen(
            RunIntake(container=self, intake=self.intake, value=-3, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False)))
        self.keyboard_trigger_t.onFalse(RunIntake(container=self, intake=self.intake, value=0, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False).andThen(
            GoToStow(container=self)))

        # v: intake on (mnemonic: vacuum up the piece)
        self.keyboard_trigger_v.whileTrue(RunIntake(self, self.intake, -3, stop_on_end=True))

        # w: wrist go left (korean left is wen chok, also position on the keyboard)
        self.keyboard_trigger_o.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_side(side=RobotState.Side.RIGHT)).ignoringDisable(True))

        # o: wrist go right (korean right is orin chok, also position on the keyboard)
        self.keyboard_trigger_w.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_side(side=RobotState.Side.LEFT)).ignoringDisable(True))

    def register_commands(self):

        NamedCommands.registerCommand('robot state left', commands2.cmd.runOnce(lambda: self.robot_state.set_side(side=RobotState.Side.RIGHT)).ignoringDisable(True))
        NamedCommands.registerCommand('go to l4', GoToReefPosition(self, 4, self.robot_state))
        NamedCommands.registerCommand('score', Score(self))


    def get_autonomous_command(self):
        # return DriveByVelocitySwerve(self, self.swerve, Pose2d(0.1, 0, 0), 2)
        return AutoBuilder.buildAuto('1+0')
        # return AutoBuilder.followPath(PathPlannerPath.fromPathFile("new patth"))
        # return self.autonomous_chooser.getSelected()

    def bind_button_box(self):
        """
        Remember - buttons arre 1-indexed, no zero
        """
        # The driver's controller
        self.bbox_1 = commands2.button.CommandJoystick(constants.k_bbox_1_port)
        self.bbox_2 = commands2.button.CommandJoystick(constants.k_bbox_2_port)

        self.bbox_TBD1 = self.bbox_1.button(3)  # top left red 1
        self.bbox_TBD2 = self.bbox_1.button(4)  # top left red 2

        self.bbox_right = self.bbox_1.button(1)  # true when selected
        self.bbox_left = self.bbox_1.button(2)  #  and true when selected
        self.bbox_human_left = self.bbox_1.button(5)
        self.bbox_human_right = self.bbox_1.button(6)

        # reef  stuff
        self.bbox_AB = self.bbox_1.button(7)
        self.bbox_CD = self.bbox_1.button(8)
        self.bbox_EF = self.bbox_1.button(9)
        self.bbox_GH = self.bbox_1.button(10)
        self.bbox_IJ = self.bbox_1.button(11)
        self.bbox_KL = self.bbox_1.button(12)

        self.bbox_L1 = self.bbox_2.button(1)
        self.bbox_L2 = self.bbox_2.button(2)
        self.bbox_L3 = self.bbox_2.button(3)
        self.bbox_L4 = self.bbox_2.button(4)
        self.bbox_reef_alga_high = self.bbox_2.button(5)
        self.bbox_reef_alga_low = self.bbox_2.button(7)
        self.bbox_net = self.bbox_2.button(6)
        self.bbox_processor = self.bbox_2.button(8)

        # actual bindings

        self.bbox_TBD1.onTrue(Score(self))
        self.bbox_TBD2.onTrue(GoToStow(self))
        self.bbox_right.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_side(side=RobotState.Side.RIGHT)).ignoringDisable(True))
        self.bbox_left.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_side(side=RobotState.Side.LEFT)).ignoringDisable(True))

        self.bbox_human_right.whileTrue(GoToCoralStation(container=self).andThen(
            RunIntake(container=self, intake=self.intake, value=constants.IntakeConstants.k_coral_intaking_voltage, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False)))
        self.bbox_human_right.onFalse(RunIntake(container=self, intake=self.intake, value=0, control_type=rev.SparkMax.ControlType.kVoltage, stop_on_end=False).andThen(
            GoToStow(container=self)))

        self.bbox_human_left.onTrue(RunIntake(self, self.intake, constants.IntakeConstants.k_coral_scoring_voltage, stop_on_end=True)) # TODO: make these all use the one in intakeconstants

        self.bbox_human_right.onTrue(commands2.PrintCommand("Pushed BBox Human right"))

        # while held:
            # if we're being told to go left:
                # if we're going to a far side:
                    # go to our right
                # else:
                    # go to our left
        # the issue is communicating this to the wrist.
        # we want MoveWristByJoystick to go left if our target-- wait but not really,
        # i think we only care about whether the bot is pointing there or no

        self.bbox_AB.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_left
                )
        )

        self.bbox_CD.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_left
                )
        )

        # we swap the condition because for these ones, the driver's left is the robot's right
        self.bbox_EF.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_right
                )
        )

        self.bbox_GH.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_right
                )
        )

        self.bbox_IJ.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_right
                )
        )

        self.bbox_KL.whileTrue(
                commands2.ConditionalCommand(
                    onTrue=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["a"], swerve_constants.AutoConstants.pathfinding_constraints),
                    onFalse=AutoBuilder.pathfindToPoseFlipped(constants.k_useful_robot_poses_blue["b"], swerve_constants.AutoConstants.pathfinding_constraints),
                    condition=self.robot_state.is_left
                )
        )

        self.bbox_L1.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_target(RobotState.Target.L1)).ignoringDisable(True))
        self.bbox_L2.onTrue(commands2.cmd.runOnce(lambda: self.robot_state.set_target(RobotState.Target.L2)).ignoringDisable(True).andThen(GoToReefPosition(self, 2, self.robot_state)))
        self.bbox_L3.onTrue(commands2.InstantCommand(lambda: self.robot_state.set_target(RobotState.Target.L3)).ignoringDisable(True).andThen(GoToReefPosition(self, 3, self.robot_state)))
        self.bbox_L4.onTrue(commands2.InstantCommand(lambda: self.robot_state.set_target(RobotState.Target.L4)).ignoringDisable(True).andThen(GoToReefPosition(self, 4, self.robot_state)))

        self.bbox_reef_alga_high.onTrue(GoToPosition(self, "algae high").andThen(RunIntake(self, self.intake, constants.IntakeConstants.k_algae_intaking_voltage)))
        self.bbox_reef_alga_high.onFalse(RunIntake(self, self.intake, 0).andThen(GoToPosition(self, "stow")))

        self.bbox_reef_alga_low.onTrue(GoToPosition(self, "algae low").andThen(RunIntake(self, self.intake, constants.IntakeConstants.k_algae_intaking_voltage)))
        self.bbox_reef_alga_low.onFalse(RunIntake(self, self.intake, 0).andThen(GoToPosition(self, "stow")))

        self.bbox_net.onTrue(commands2.InstantCommand(lambda: self.climber.set_duty_cycle(0.1), self.climber))
        self.bbox_net.onFalse(commands2.InstantCommand(lambda: self.climber.set_duty_cycle(0), self.climber))
        self.bbox_processor.onTrue(commands2.InstantCommand(lambda: self.climber.set_duty_cycle(-0.1), self.climber))
        self.bbox_processor.onFalse(commands2.InstantCommand(lambda: self.climber.set_duty_cycle(0), self.climber))

        self.bbox_net.onTrue(commands2.PrintCommand("Pushed BBox Net"))
        self.bbox_processor.onTrue(commands2.PrintCommand("Pushed BBox Processor"))




